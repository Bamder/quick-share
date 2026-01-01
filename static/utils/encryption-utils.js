/**
 * 加密工具函数
 * 使用 Web Crypto API 实现端到端加密
 * 服务器无法查看文件内容，降低法律义务
 */

/**
 * 生成加密密钥（客户端生成，不发送到服务器）
 * @returns {Promise<CryptoKey>} AES-GCM 加密密钥
 */
export async function generateEncryptionKey() {
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
        throw new Error('无法生成加密密钥，请确保使用HTTPS连接');
    }
}

/**
 * 导出密钥为Base64字符串（用于安全传输）
 * @param {CryptoKey} key 加密密钥
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
 * 从Base64字符串导入密钥
 * @param {string} base64Key Base64编码的密钥
 * @returns {Promise<CryptoKey>} 加密密钥
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
 * @param {Blob} chunk 原始文件块
 * @param {CryptoKey} key 加密密钥
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
 * @param {Blob} encryptedChunk 加密的文件块（包含IV）
 * @param {CryptoKey} key 解密密钥
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
 * 从完整取件码中提取密钥码（后6位）
 * @param {string} fullPickupCode 完整的12位取件码
 * @returns {string} 后6位密钥码
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
 * 从取件码派生密钥（用于加密文件加密密钥）
 * 使用 PBKDF2 从密钥码（后6位）派生一个稳定的密钥
 * @param {string} fullPickupCode 完整的12位取件码
 * @returns {Promise<CryptoKey>} 派生出的密钥
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
 * 使用取件码加密文件加密密钥
 * @param {CryptoKey} fileEncryptionKey 文件加密密钥
 * @param {string} pickupCode 取件码
 * @returns {Promise<string>} 加密后的密钥（Base64编码）
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
 * 使用取件码解密文件加密密钥
 * @param {string} encryptedKeyBase64 加密后的密钥（Base64编码）
 * @param {string} pickupCode 取件码
 * @returns {Promise<CryptoKey>} 解密后的文件加密密钥
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

