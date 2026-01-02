/**
 * 密钥缓存工具
 * 将文件加密密钥存储在浏览器 localStorage 中
 * 以文件哈希为键，包含密钥和过期时间
 */

const CACHE_PREFIX = 'quick-share-key-cache-';
const PICKUP_CODE_CACHE_PREFIX = 'quick-share-pickup-code-cache-';
const CACHE_EXPIRY_HOURS = 24 * 7; // 7天过期

/**
 * 获取缓存键
 * @param {string} fileHash - 文件哈希
 * @returns {string} 缓存键
 */
function getCacheKey(fileHash) {
    return `${CACHE_PREFIX}${fileHash}`;
}

/**
 * 存储密钥到缓存
 * @param {string} fileHash - 文件哈希
 * @param {string} keyBase64 - Base64编码的密钥
 * @param {number} expireHours - 过期时间（小时），默认7天
 */
export function storeKeyInCache(fileHash, keyBase64, expireHours = CACHE_EXPIRY_HOURS) {
    if (!fileHash || !keyBase64) {
        console.warn('[KeyCache] 无效的缓存参数');
        return;
    }

    try {
        const expireAt = Date.now() + (expireHours * 60 * 60 * 1000);
        const cacheData = {
            key: keyBase64,
            expireAt: expireAt,
            createdAt: Date.now()
        };

        const cacheKey = getCacheKey(fileHash);
        localStorage.setItem(cacheKey, JSON.stringify(cacheData));
        console.log(`[KeyCache] 密钥已缓存: ${fileHash.substring(0, 16)}... (过期时间: ${new Date(expireAt).toLocaleString()})`);
    } catch (error) {
        console.error('[KeyCache] 存储密钥失败:', error);
    }
}

/**
 * 从缓存获取密钥
 * @param {string} fileHash - 文件哈希
 * @returns {string|null} Base64编码的密钥，如果不存在或已过期则返回null
 */
export function getKeyFromCache(fileHash) {
    if (!fileHash) {
        return null;
    }

    try {
        const cacheKey = getCacheKey(fileHash);
        const cachedData = localStorage.getItem(cacheKey);
        
        if (!cachedData) {
            return null;
        }

        const cacheData = JSON.parse(cachedData);
        
        // 检查是否过期（使用绝对时间）
        if (Date.now() > cacheData.expireAt) {
            console.log(`[KeyCache] 密钥已过期: ${fileHash.substring(0, 16)}...`);
            localStorage.removeItem(cacheKey);
            return null;
        }

        console.log(`[KeyCache] 从缓存获取密钥: ${fileHash.substring(0, 16)}...`);
        return cacheData.key;
    } catch (error) {
        console.error('[KeyCache] 获取密钥失败:', error);
        return null;
    }
}

/**
 * 从缓存删除密钥
 * @param {string} fileHash - 文件哈希
 */
export function removeKeyFromCache(fileHash) {
    if (!fileHash) {
        return;
    }

    try {
        const cacheKey = getCacheKey(fileHash);
        localStorage.removeItem(cacheKey);
        console.log(`[KeyCache] 密钥已删除: ${fileHash.substring(0, 16)}...`);
    } catch (error) {
        console.error('[KeyCache] 删除密钥失败:', error);
    }
}

/**
 * 清理所有过期的密钥缓存和取件码缓存
 * 每次进入网站时调用
 */
export function cleanupExpiredKeys() {
    try {
        const now = Date.now();
        let cleanedCount = 0;

        // 遍历所有 localStorage 项
        for (let i = localStorage.length - 1; i >= 0; i--) {
            const key = localStorage.key(i);
            
            if (key && (key.startsWith(CACHE_PREFIX) || key.startsWith(PICKUP_CODE_CACHE_PREFIX))) {
                try {
                    const cachedData = JSON.parse(localStorage.getItem(key));
                    
                    // 检查是否过期
                    if (cachedData.expireAt && now > cachedData.expireAt) {
                        localStorage.removeItem(key);
                        cleanedCount++;
                    }
                } catch (error) {
                    // 如果解析失败，删除无效的缓存项
                    console.warn(`[KeyCache] 删除无效缓存项: ${key}`);
                    localStorage.removeItem(key);
                    cleanedCount++;
                }
            }
        }

        if (cleanedCount > 0) {
            console.log(`[KeyCache] 已清理 ${cleanedCount} 个过期的缓存项`);
        }
    } catch (error) {
        console.error('[KeyCache] 清理过期缓存失败:', error);
    }
}

/**
 * 获取所有缓存的密钥哈希列表（用于调试）
 * @returns {string[]} 文件哈希列表
 */
export function getAllCachedKeyHashes() {
    const hashes = [];
    
    try {
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith(CACHE_PREFIX)) {
                const hash = key.substring(CACHE_PREFIX.length);
                hashes.push(hash);
            }
        }
    } catch (error) {
        console.error('[KeyCache] 获取缓存列表失败:', error);
    }
    
    return hashes;
}

/**
 * 存储完整的12位取件码到缓存（以文件哈希为键）
 * @param {string} fileHash - 文件哈希
 * @param {string} fullPickupCode - 完整的12位取件码
 * @param {number} expireHours - 过期时间（小时）
 */
export function storePickupCodeInCache(fileHash, fullPickupCode, expireHours = CACHE_EXPIRY_HOURS) {
    if (!fileHash || !fullPickupCode) {
        console.warn('[KeyCache] 无效的取件码缓存参数');
        return;
    }

    try {
        const expireAt = Date.now() + (expireHours * 60 * 60 * 1000);
        const cacheData = {
            pickupCode: fullPickupCode,
            expireAt: expireAt,
            createdAt: Date.now()
        };

        const cacheKey = `${PICKUP_CODE_CACHE_PREFIX}${fileHash}`;
        localStorage.setItem(cacheKey, JSON.stringify(cacheData));
        console.log(`[KeyCache] 取件码已缓存: ${fileHash.substring(0, 16)}... (过期时间: ${new Date(expireAt).toLocaleString()})`);
    } catch (error) {
        console.error('[KeyCache] 存储取件码失败:', error);
    }
}

/**
 * 从缓存获取完整的12位取件码
 * @param {string} fileHash - 文件哈希
 * @returns {string|null} 完整的12位取件码，如果不存在或已过期则返回null
 */
export function getPickupCodeFromCache(fileHash) {
    if (!fileHash) {
        return null;
    }

    try {
        const cacheKey = `${PICKUP_CODE_CACHE_PREFIX}${fileHash}`;
        const cachedData = localStorage.getItem(cacheKey);
        
        if (!cachedData) {
            return null;
        }

        const cacheData = JSON.parse(cachedData);
        
        // 检查是否过期（使用绝对时间）
        if (Date.now() > cacheData.expireAt) {
            console.log(`[KeyCache] 取件码已过期: ${fileHash.substring(0, 16)}...`);
            localStorage.removeItem(cacheKey);
            return null;
        }

        console.log(`[KeyCache] 从缓存获取取件码: ${fileHash.substring(0, 16)}...`);
        return cacheData.pickupCode;
    } catch (error) {
        console.error('[KeyCache] 获取取件码失败:', error);
        return null;
    }
}

/**
 * 从缓存删除取件码
 * @param {string} fileHash - 文件哈希
 */
export function removePickupCodeFromCache(fileHash) {
    if (!fileHash) {
        return;
    }

    try {
        const cacheKey = `${PICKUP_CODE_CACHE_PREFIX}${fileHash}`;
        localStorage.removeItem(cacheKey);
        console.log(`[KeyCache] 取件码已删除: ${fileHash.substring(0, 16)}...`);
    } catch (error) {
        console.error('[KeyCache] 删除取件码失败:', error);
    }
}

