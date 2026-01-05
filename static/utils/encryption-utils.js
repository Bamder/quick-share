/**
 * 加密工具函数
 * 使用 Web Crypto API 实现端到端加密
 * 服务器无法查看文件内容，降低法律义务
 * 
 * ============================================================================
 * 密钥概念体系（4个密钥相关概念及其关系）
 * ============================================================================
 * 
 * 1. 文件加密密钥（原始密钥 / File Encryption Key）
 *    - 类型：CryptoKey（AES-GCM，256位）
 *    - 生成方式：随机生成（generateEncryptionKey()）
 *    - 用途：直接加密/解密文件块
 *    - 存储位置：客户端浏览器缓存（以文件哈希为键）
 *    - 是否传输到服务器：否（只传输加密后的版本）
 *    - 代码位置：this.encryptionKey（Sender/Receiver）
 * 
 * 2. 密钥码（6位密钥码 / Key Code）
 *    - 类型：字符串（6位大写字母+数字）
 *    - 来源：取件码的后6位（如 "ABC123DEF456" 中的 "DEF456"）
 *    - 用途：作为材料派生密钥，用于加密/解密文件加密密钥
 *    - 是否传输到服务器：否（服务器只接收前6位查找码）
 *    - 代码位置：extractKeyCode(fullPickupCode)
 * 
 * 3. 派生密钥（Derived Key）
 *    - 类型：CryptoKey（AES-GCM，256位）
 *    - 生成方式：从密钥码通过PBKDF2派生（100000次迭代，SHA-256）
 *    - 用途：加密/解密文件加密密钥（原始密钥）
 *    - 存储位置：不存储，每次使用时临时派生
 *    - 是否传输到服务器：否（只在客户端使用）
 *    - 代码位置：deriveKeyFromPickupCode(fullPickupCode)
 * 
 * 4. 加密后的文件加密密钥（Encrypted File Encryption Key）
 *    - 类型：字符串（Base64编码）
 *    - 生成方式：用派生密钥加密文件加密密钥（原始密钥）
 *    - 用途：安全存储到服务器，供接收者下载
 *    - 存储位置：服务器内存缓存（encrypted_key_cache）
 *    - 是否传输到服务器：是（这是唯一传输到服务器的密钥相关数据）
 *    - 代码位置：encryptedKey（存储时）、encrypted_key_cache（服务器端）
 * 
 * ============================================================================
 * 密钥关系链（加密流程）
 * ============================================================================
 * 
 * 取件码（12位）
 * ├── 查找码（前6位）→ 用于服务器查询和缓存键
 * └── 密钥码（后6位）→ 派生密钥 → 加密 → 文件加密密钥（原始密钥）→ 加密文件块
 * 
 * 详细流程：
 * 1. Sender生成文件加密密钥（原始密钥）→ 随机生成，256位AES-GCM
 * 2. Sender提取密钥码（后6位）→ 从取件码提取
 * 3. Sender派生密钥 → 从密钥码通过PBKDF2派生256位AES-GCM密钥
 * 4. Sender加密文件加密密钥 → 用派生密钥加密原始密钥
 * 5. Sender存储到服务器 → 只存储加密后的密钥（Base64编码）
 * 6. Receiver从服务器获取 → 获取加密后的密钥
 * 7. Receiver派生密钥 → 从密钥码通过PBKDF2派生相同的密钥
 * 8. Receiver解密文件加密密钥 → 用派生密钥解密，得到原始密钥
 * 9. Receiver解密文件块 → 用原始密钥解密文件块
 * 
 * ============================================================================
 * 安全层级（多层加密保护）
 * ============================================================================
 * 
 * 第1层：文件块加密
 *   - 使用：文件加密密钥（原始密钥）
 *   - 算法：AES-GCM（256位）
 *   - 保护：文件内容
 * 
 * 第2层：文件加密密钥加密
 *   - 使用：派生密钥（从密钥码派生）
 *   - 算法：AES-GCM（256位）+ PBKDF2（100000次迭代）
 *   - 保护：文件加密密钥（原始密钥）
 * 
 * 第3层：密钥码保护
 *   - 方式：不传输到服务器，只在客户端使用
 *   - 保护：派生密钥的生成材料
 * 
 * ============================================================================
 * 服务器可见性
 * ============================================================================
 * 
 * 服务器可以看到：
 * - 查找码（前6位）：用于查询和缓存键
 * - 加密后的文件加密密钥：Base64编码的加密数据
 * - 加密后的文件块：加密后的文件数据
 * 
 * 服务器无法看到：
 * - 密钥码（后6位）：不传输到服务器
 * - 派生密钥：只在客户端生成和使用
 * - 文件加密密钥（原始密钥）：不传输到服务器
 * - 文件内容：已加密，无法解密
 * 
 * 因此，即使服务器被完全攻破，攻击者也无法：
 * - 解密文件内容（缺少密钥码和原始密钥）
 * - 获取原始密钥（缺少密钥码来派生密钥）
 * - 解密文件块（缺少原始密钥）
 */

/**
 * 生成文件加密密钥（原始密钥）
 * 
 * 这是密钥关系链中的第1个概念：文件加密密钥（File Encryption Key）
 * 
 * 关系说明：
 * - 这是用于直接加密文件块的随机密钥，不是取件码的一部分
 * - 不会以明文形式传输到服务器，而是用派生密钥加密后存储
 * - 存储在客户端浏览器缓存中（以文件哈希为键）
 * 
 * 密钥关系链：
 * 文件加密密钥（原始密钥）→ 用派生密钥加密 → 加密后的文件加密密钥 → 存储到服务器
 * 
 * 用途：
 * - 直接加密/解密文件块
 * - 不传输到服务器（只传输加密后的版本）
 * 
 * @returns {Promise<CryptoKey>} 文件加密密钥（第1个概念，AES-GCM，256位，随机生成）
 */
/**
 * 检查是否在安全上下文中（HTTPS或localhost）
 * @returns {boolean} 是否在安全上下文中
 */
function isSecureContext() {
    // 检查是否为安全上下文
    if (typeof window !== 'undefined' && window.isSecureContext !== undefined) {
        return window.isSecureContext;
    }
    
    // 降级检查：检查协议和主机名
    if (typeof location !== 'undefined') {
        const protocol = location.protocol;
        const hostname = location.hostname;
        
        // HTTPS 协议
        if (protocol === 'https:') {
            return true;
        }
        
        // localhost 或 127.0.0.1（开发环境）
        if (protocol === 'http:' && (hostname === 'localhost' || hostname === '127.0.0.1')) {
            return true;
        }
    }
    
    return false;
}

export async function generateEncryptionKey() {
    // 检查安全上下文
    if (!isSecureContext()) {
        const protocol = typeof location !== 'undefined' ? location.protocol : 'unknown';
        const hostname = typeof location !== 'undefined' ? location.hostname : 'unknown';
        const errorMsg = `无法生成加密密钥：Web Crypto API 需要安全上下文（HTTPS或localhost）

当前访问方式: ${protocol}//${hostname}

解决方案：
1. 使用 HTTPS 访问（推荐）
   - 服务器已支持 HTTPS，请使用 https:// 开头访问
   - 如果是自签名证书，浏览器会显示警告，点击"高级" -> "继续访问"即可

2. 如果使用 IP 地址，需要配置 HTTPS
   - 运行脚本生成SSL证书: scripts\\setup\\generate_ssl_cert\\generate_ssl_cert.bat
   - 然后使用 https://[您的IP]:8000 访问

3. 开发环境可以使用 localhost
   - 使用 http://localhost:8000 访问（仅限本机）`;
        
        console.error('[Encryption]', errorMsg);
        throw new Error(errorMsg);
    }
    
    try {
        const key = await crypto.subtle.generateKey(
            {
                name: "AES-GCM",
                length: 256
            },
            true, // 可导出
            ["encrypt", "decrypt"]
        );
        return key;
    } catch (error) {
        console.error('[Encryption] 生成加密密钥失败:', error);
        
        // 如果是因为安全上下文问题，提供更详细的错误信息
        if (!isSecureContext()) {
            throw new Error('无法生成加密密钥，请确保使用HTTPS连接或localhost');
        }
        
        throw new Error(`无法生成加密密钥: ${error.message}`);
    }
}

/**
 * 导出文件加密密钥为Base64字符串（用于浏览器缓存）
 * 
 * @param {CryptoKey} key 文件加密密钥（原始密钥）
 * @returns {Promise<string>} Base64编码的密钥
 */
export async function exportKeyToBase64(key) {
    try {
        const exported = await crypto.subtle.exportKey('raw', key);
        const base64 = btoa(String.fromCharCode(...new Uint8Array(exported)));
        return base64;
    } catch (error) {
        console.error('[Encryption] 导出密钥失败:', error);
        throw new Error('无法导出加密密钥');
    }
}

/**
 * 从Base64字符串导入文件加密密钥
 * 
 * @param {string} base64Key Base64编码的文件加密密钥（原始密钥）
 * @returns {Promise<CryptoKey>} 文件加密密钥
 */
export async function importKeyFromBase64(base64Key) {
    try {
        const binaryString = atob(base64Key);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        
        const key = await crypto.subtle.importKey(
            'raw',
            bytes,
            {
                name: "AES-GCM",
                length: 256
            },
            true,
            ["encrypt", "decrypt"]
        );
        return key;
    } catch (error) {
        console.error('[Encryption] 导入密钥失败:', error);
        throw new Error('无法导入加密密钥');
    }
}

/**
 * 加密文件块
 * 
 * 使用文件加密密钥（原始密钥）直接加密文件块
 * 
 * @param {Blob} chunk 原始文件块
 * @param {CryptoKey} key 文件加密密钥（原始密钥，不是密钥码）
 * @returns {Promise<Blob>} 加密后的文件块（包含IV）
 */
export async function encryptChunk(chunk, key) {
    try {
        // 生成随机IV（12字节，AES-GCM要求）
        const iv = crypto.getRandomValues(new Uint8Array(12));
        
        // 读取文件块数据
        const arrayBuffer = await chunk.arrayBuffer();
        
        // 加密数据
        const encrypted = await crypto.subtle.encrypt(
            {
                name: "AES-GCM",
                iv: iv
            },
            key,
            arrayBuffer
        );
        
        // 组合IV和加密数据：IV(12字节) + 加密数据
        const combined = new Uint8Array(12 + encrypted.byteLength);
        combined.set(new Uint8Array(iv), 0);
        combined.set(new Uint8Array(encrypted), 12);
        
        return new Blob([combined], { type: 'application/octet-stream' });
    } catch (error) {
        console.error('[Encryption] 加密文件块失败:', error);
        throw new Error('文件块加密失败');
    }
}

/**
 * 解密文件块
 * 
 * 使用文件加密密钥（原始密钥）直接解密文件块
 * 
 * @param {Blob} encryptedChunk 加密的文件块（包含IV）
 * @param {CryptoKey} key 文件加密密钥（原始密钥，不是密钥码）
 * @returns {Promise<Blob>} 解密后的原始文件块
 */
export async function decryptChunk(encryptedChunk, key) {
    try {
        // 读取加密数据
        const arrayBuffer = await encryptedChunk.arrayBuffer();
        
        // 提取IV（前12字节）和加密数据
        const iv = new Uint8Array(arrayBuffer, 0, 12);
        const encrypted = new Uint8Array(arrayBuffer, 12);
        
        // 解密数据
        const decrypted = await crypto.subtle.decrypt(
            {
                name: "AES-GCM",
                iv: iv
            },
            key,
            encrypted
        );
        
        return new Blob([decrypted]);
    } catch (error) {
        console.error('[Encryption] 解密文件块失败:', error);
        throw new Error('文件块解密失败，可能是密钥错误或数据损坏');
    }
}

/**
 * 计算数据块的哈希值（用于验证完整性）
 * @param {Blob} chunk 文件块
 * @returns {Promise<string>} SHA-256哈希值（十六进制）
 */
export async function calculateChunkHash(chunk) {
    try {
        const arrayBuffer = await chunk.arrayBuffer();
        const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        return hashHex;
    } catch (error) {
        console.error('[Encryption] 计算哈希失败:', error);
        throw new Error('无法计算文件块哈希');
    }
}

/**
 * 计算整个文件的SHA-256哈希值（用于文件去重）
 * @param {File|Blob} file 文件对象
 * @returns {Promise<string>} SHA-256哈希值（十六进制，小写）
 */
export async function calculateFileHash(file) {
    try {
        const arrayBuffer = await file.arrayBuffer();
        const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        return hashHex;
    } catch (error) {
        console.error('[Encryption] 计算文件哈希失败:', error);
        throw new Error('无法计算文件哈希');
    }
}

/**
 * 从完整取件码中提取密钥码（后6位）
 * 
 * 这是密钥关系链中的第2个概念：密钥码（Key Code）
 * 
 * 关系说明：
 * - 密钥码是取件码的一部分（后6位），不是文件加密密钥本身
 * - 密钥码用于派生密钥（第3个概念），派生密钥用于加密/解密文件加密密钥（第1个概念）
 * 
 * 密钥关系链：
 * 取件码 → 密钥码（后6位）→ 派生密钥 → 加密/解密 → 文件加密密钥（原始密钥）
 * 
 * 重要区别：
 * - 密钥码（6位字符串）≠ 文件加密密钥（256位CryptoKey）
 * - 密钥码是派生密钥的材料，不是密钥本身
 * 
 * @param {string} fullPickupCode 完整的12位取件码（前6位查找码+后6位密钥码）
 * @returns {string} 后6位密钥码（第2个概念，如 "ABC123DEF456" 中的 "DEF456"）
 */
export function extractKeyCode(fullPickupCode) {
    if (fullPickupCode.length !== 12) {
        throw new Error(`取件码长度错误，应为12位，实际为${fullPickupCode.length}位`);
    }
    return fullPickupCode.substring(6).toUpperCase();
}

/**
 * 从完整取件码中提取查找码（前6位）
 * @param {string} fullPickupCode 完整的12位取件码
 * @returns {string} 前6位查找码
 */
export function extractLookupCode(fullPickupCode) {
    if (fullPickupCode.length !== 12) {
        throw new Error(`取件码长度错误，应为12位，实际为${fullPickupCode.length}位`);
    }
    return fullPickupCode.substring(0, 6).toUpperCase();
}

/**
 * 从取件码派生密钥（用于加密/解密文件加密密钥）
 * 
 * 这是密钥关系链中的第3个概念：派生密钥（Derived Key）
 * 
 * 关系说明：
 * - 输入：取件码（包含密钥码后6位）
 * - 过程：从密钥码通过PBKDF2派生256位AES-GCM密钥
 * - 输出：派生密钥（用于加密/解密文件加密密钥）
 * 
 * 重要区别：
 * - 密钥码（后6位）≠ 文件加密密钥（原始密钥）
 * - 密钥码（后6位）→ 派生密钥 → 加密/解密 → 文件加密密钥（原始密钥）
 * 
 * 流程：
 * 1. 提取密钥码（后6位）← 从取件码提取
 * 2. 使用PBKDF2派生为256位AES-GCM密钥 ← 派生密钥（本函数返回）
 * 3. 用派生密钥加密/解密文件加密密钥（原始密钥）← 在其他函数中使用
 * 
 * @param {string} fullPickupCode 完整的12位取件码（用于提取密钥码）
 * @returns {Promise<CryptoKey>} 派生密钥（用于加密/解密文件加密密钥，不是文件加密密钥本身）
 */
export async function deriveKeyFromPickupCode(fullPickupCode) {
    try {
        // 提取密钥码（后6位）
        const keyCode = extractKeyCode(fullPickupCode);
        
        // 将密钥码转换为 ArrayBuffer
        const codeBuffer = new TextEncoder().encode(keyCode);
        
        // 使用 PBKDF2 派生密钥（使用固定的 salt，因为密钥码本身已经足够唯一）
        // 注意：这里使用密钥码作为 salt 的一部分，增加安全性
        const salt = new TextEncoder().encode(`quick-share-salt-${keyCode}`);
        
        // 导入取件码作为基础密钥材料
        const baseKey = await crypto.subtle.importKey(
            'raw',
            codeBuffer,
            'PBKDF2',
            false,
            ['deriveBits', 'deriveKey']
        );
        
        // 派生 AES-GCM 密钥
        const derivedKey = await crypto.subtle.deriveKey(
            {
                name: 'PBKDF2',
                salt: salt,
                iterations: 100000, // 足够的迭代次数确保安全性
                hash: 'SHA-256'
            },
            baseKey,
            {
                name: 'AES-GCM',
                length: 256
            },
            true,
            ['encrypt', 'decrypt']
        );
        
        return derivedKey;
    } catch (error) {
        console.error('[Encryption] 从取件码派生密钥失败:', error);
        throw new Error('无法从取件码派生密钥');
    }
}

/**
 * 使用取件码加密文件加密密钥（原始密钥）
 * 
 * 这是密钥关系链中的加密流程，将第1个概念（文件加密密钥）加密为第4个概念（加密后的文件加密密钥）
 * 
 * 密钥关系链：
 * 取件码 → 密钥码（后6位）→ 派生密钥 → 加密 → 文件加密密钥（原始密钥）→ 加密后的文件加密密钥
 * 
 * 流程：
 * 1. 从取件码的密钥码（后6位）派生密钥 ← 调用 deriveKeyFromPickupCode()
 * 2. 使用派生密钥加密文件加密密钥（原始密钥）← 使用AES-GCM加密
 * 3. 返回加密后的密钥（Base64编码），存储到服务器 ← 这是唯一传输到服务器的密钥数据
 * 
 * 安全说明：
 * - 文件加密密钥（原始密钥）不会以明文形式传输到服务器
 * - 服务器只能看到加密后的密钥，无法解密（缺少密钥码）
 * - 只有拥有完整取件码（包括后6位密钥码）的用户才能解密
 * 
 * @param {CryptoKey} fileEncryptionKey 文件加密密钥（原始密钥，第1个概念，用于加密文件块）
 * @param {string} pickupCode 完整的12位取件码（用于提取密钥码并派生密钥）
 * @returns {Promise<string>} 加密后的文件加密密钥（第4个概念，Base64编码，可安全存储到服务器）
 */
export async function encryptKeyWithPickupCode(fileEncryptionKey, pickupCode) {
    try {
        // 从取件码派生密钥
        const derivedKey = await deriveKeyFromPickupCode(pickupCode);
        
        // 导出文件加密密钥为原始数据
        const keyData = await crypto.subtle.exportKey('raw', fileEncryptionKey);
        
        // 生成随机IV
        const iv = crypto.getRandomValues(new Uint8Array(12));
        
        // 使用派生密钥加密文件加密密钥
        const encrypted = await crypto.subtle.encrypt(
            {
                name: 'AES-GCM',
                iv: iv
            },
            derivedKey,
            keyData
        );
        
        // 组合IV和加密数据：IV(12字节) + 加密数据
        const combined = new Uint8Array(12 + encrypted.byteLength);
        combined.set(new Uint8Array(iv), 0);
        combined.set(new Uint8Array(encrypted), 12);
        
        // 转换为Base64
        const base64 = btoa(String.fromCharCode(...combined));
        return base64;
    } catch (error) {
        console.error('[Encryption] 使用取件码加密密钥失败:', error);
        throw new Error('无法使用取件码加密密钥');
    }
}

/**
 * 使用取件码解密文件加密密钥（原始密钥）
 * 
 * 这是密钥关系链中的解密流程，将第4个概念（加密后的文件加密密钥）解密为第1个概念（文件加密密钥）
 * 
 * 密钥关系链（反向）：
 * 加密后的文件加密密钥 → 派生密钥解密 → 文件加密密钥（原始密钥）→ 解密文件块
 * 
 * 流程：
 * 1. 从取件码的密钥码（后6位）派生密钥 ← 调用 deriveKeyFromPickupCode()
 * 2. 使用派生密钥解密从服务器获取的加密密钥 ← 使用AES-GCM解密
 * 3. 返回解密后的文件加密密钥（原始密钥），用于解密文件块 ← 得到第1个概念
 * 
 * 安全说明：
 * - 只有拥有完整取件码（包括后6位密钥码）的用户才能解密
 * - 服务器无法解密（缺少密钥码，无法派生密钥）
 * - 解密后的原始密钥只在客户端使用，不传输到服务器
 * 
 * @param {string} encryptedKeyBase64 加密后的文件加密密钥（第4个概念，Base64编码，从服务器获取）
 * @param {string} pickupCode 完整的12位取件码（用于提取密钥码并派生密钥）
 * @returns {Promise<CryptoKey>} 解密后的文件加密密钥（第1个概念，原始密钥，用于解密文件块）
 */
export async function decryptKeyWithPickupCode(encryptedKeyBase64, pickupCode) {
    try {
        // 从取件码派生密钥
        const derivedKey = await deriveKeyFromPickupCode(pickupCode);
        
        // 解码Base64
        const binaryString = atob(encryptedKeyBase64);
        const arrayBuffer = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            arrayBuffer[i] = binaryString.charCodeAt(i);
        }
        
        // 提取IV（前12字节）和加密数据
        const iv = new Uint8Array(arrayBuffer.buffer, 0, 12);
        const encrypted = new Uint8Array(arrayBuffer.buffer, 12);
        
        // 使用派生密钥解密
        const decrypted = await crypto.subtle.decrypt(
            {
                name: 'AES-GCM',
                iv: iv
            },
            derivedKey,
            encrypted
        );
        
        // 导入解密后的密钥
        const fileEncryptionKey = await crypto.subtle.importKey(
            'raw',
            decrypted,
            {
                name: 'AES-GCM',
                length: 256
            },
            true,
            ['encrypt', 'decrypt']
        );
        
        return fileEncryptionKey;
    } catch (error) {
        console.error('[Encryption] 使用取件码解密密钥失败:', error);
        throw new Error('无法使用取件码解密密钥，可能是取件码错误');
    }
}

