from app.utils.cache import cache_manager
from typing import Optional
from datetime import datetime

def _make_cache_key(user_id: Optional[int], lookup_code: str) -> str:
    """
    生成包含用户ID的缓存键
    
    参数:
    - user_id: 用户ID（如果为None，使用 'anonymous'）
    - lookup_code: 查找码（6位）
    
    返回:
    - 缓存键格式: {user_id}:{lookup_code}
    """
    if user_id is None:
        user_id = 'anonymous'
    return f"{user_id}:{lookup_code}"

def _parse_cache_key(cache_key: str) -> tuple[Optional[int], str]:
    """
    解析缓存键，提取用户ID和查找码
    
    参数:
    - cache_key: 缓存键（格式: {user_id}:{lookup_code} 或旧格式 {lookup_code}）
    
    返回:
    - (user_id, lookup_code) 元组
    """
    if ':' in cache_key:
        parts = cache_key.split(':', 1)
        user_id_str = parts[0]
        lookup_code = parts[1]
        # 尝试将用户ID转换为整数
        try:
            user_id = int(user_id_str) if user_id_str != 'anonymous' else None
        except ValueError:
            user_id = None
        return user_id, lookup_code
    else:
        # 旧格式（向后兼容）：只有 lookup_code
        return None, cache_key

# 文件块缓存包装类（支持嵌套结构：{user_id:lookup_code: {chunk_index: {...}}}）
class ChunkCache:
    """文件块缓存包装类（支持用户隔离）"""
    
    def get(self, lookup_code: str, user_id: Optional[int] = None) -> dict:
        """获取指定 lookup_code 的所有块"""
        cache_key = _make_cache_key(user_id, lookup_code)
        chunks = cache_manager.get('chunk', cache_key)
        if chunks is None:
            chunks = {}
            cache_manager.set('chunk', cache_key, chunks)
        else:
            # 兼容处理：老版本使用 JSON 序列化会把数字索引转换为字符串
            if isinstance(chunks, dict):
                normalized_chunks = {}
                converted = False
                for key, value in chunks.items():
                    if isinstance(key, str) and key.isdigit():
                        # 将 "0" 这类字符串索引恢复为整数，避免下载时 miss
                        normalized_key = int(key)
                        converted = True if normalized_key != key else converted
                        normalized_chunks[normalized_key] = value
                    else:
                        normalized_chunks[key] = value
                if converted:
                    # 重新写回缓存以保持一致的键类型，并带上原有过期时间
                    self.set(lookup_code, normalized_chunks, user_id)
                    chunks = normalized_chunks
        return chunks
    
    def set(self, lookup_code: str, chunks: dict, user_id: Optional[int] = None):
        """设置指定 lookup_code 的所有块"""
        cache_key = _make_cache_key(user_id, lookup_code)
        # 获取现有的过期时间（从第一个块中获取）
        expire_at = None
        if chunks:
            first_chunk = next(iter(chunks.values()))
            expire_at = first_chunk.get('pickup_expire_at') or first_chunk.get('expires_at')
        
        cache_manager.set('chunk', cache_key, chunks, expire_at)
    
    def exists(self, lookup_code: str, user_id: Optional[int] = None) -> bool:
        """检查 lookup_code 是否存在"""
        cache_key = _make_cache_key(user_id, lookup_code)
        return cache_manager.exists('chunk', cache_key)
    
    def delete(self, lookup_code: str, user_id: Optional[int] = None):
        """删除指定 lookup_code 的所有块"""
        cache_key = _make_cache_key(user_id, lookup_code)
        cache_manager.delete('chunk', cache_key)
    
    def keys(self, user_id: Optional[int] = None):
        """获取所有 lookup_code（可选：按用户ID过滤）"""
        all_keys = cache_manager.get_all_keys('chunk')
        if user_id is None:
            # 返回所有键（解析后只返回 lookup_code）
            return [_parse_cache_key(key)[1] for key in all_keys]
        else:
            # 只返回指定用户的键
            cache_key_prefix = f"{user_id}:"
            return [_parse_cache_key(key)[1] for key in all_keys if key.startswith(cache_key_prefix)]
    
    def items(self, user_id: Optional[int] = None):
        """获取所有 (lookup_code, chunks) 对（可选：按用户ID过滤）"""
        for lookup_code in self.keys(user_id):
            chunks = self.get(lookup_code, user_id)
            if chunks:
                yield lookup_code, chunks
    
    # 向后兼容：支持旧接口
    def __getitem__(self, lookup_code: str) -> dict:
        """向后兼容：获取指定 lookup_code 的所有块（使用 None 作为用户ID）"""
        return self.get(lookup_code, None)
    
    def __setitem__(self, lookup_code: str, chunks: dict):
        """向后兼容：设置指定 lookup_code 的所有块（使用 None 作为用户ID）"""
        self.set(lookup_code, chunks, None)
    
    def __contains__(self, lookup_code: str) -> bool:
        """向后兼容：检查 lookup_code 是否存在（使用 None 作为用户ID）"""
        return self.exists(lookup_code, None)
    
    def __delitem__(self, lookup_code: str):
        """向后兼容：删除指定 lookup_code 的所有块（使用 None 作为用户ID）"""
        self.delete(lookup_code, None)
    
    def __iter__(self):
        """支持迭代（向后兼容：使用 None 作为用户ID）"""
        return iter(self.keys(None))

chunk_cache = ChunkCache()

# 文件信息缓存包装类
class FileInfoCache:
    """文件信息缓存包装类（支持用户隔离）"""
    
    def get(self, lookup_code: str, user_id: Optional[int] = None, default=None):
        """获取文件信息，如果不存在则返回默认值"""
        cache_key = _make_cache_key(user_id, lookup_code)
        value = cache_manager.get('file_info', cache_key)
        return value if value is not None else default
    
    def set(self, lookup_code: str, file_info: dict, user_id: Optional[int] = None):
        """设置文件信息"""
        cache_key = _make_cache_key(user_id, lookup_code)
        expire_at = file_info.get('pickup_expire_at')
        cache_manager.set('file_info', cache_key, file_info, expire_at)
    
    def exists(self, lookup_code: str, user_id: Optional[int] = None) -> bool:
        """检查 lookup_code 是否存在"""
        cache_key = _make_cache_key(user_id, lookup_code)
        return cache_manager.exists('file_info', cache_key)
    
    def delete(self, lookup_code: str, user_id: Optional[int] = None):
        """删除文件信息"""
        cache_key = _make_cache_key(user_id, lookup_code)
        cache_manager.delete('file_info', cache_key)
    
    def keys(self, user_id: Optional[int] = None):
        """获取所有 lookup_code（可选：按用户ID过滤）"""
        all_keys = cache_manager.get_all_keys('file_info')
        if user_id is None:
            # 返回所有键（解析后只返回 lookup_code）
            return [_parse_cache_key(key)[1] for key in all_keys]
        else:
            # 只返回指定用户的键
            cache_key_prefix = f"{user_id}:"
            return [_parse_cache_key(key)[1] for key in all_keys if key.startswith(cache_key_prefix)]
    
    # 向后兼容：支持旧接口
    def __getitem__(self, lookup_code: str) -> dict:
        """向后兼容：获取文件信息（使用 None 作为用户ID）"""
        return self.get(lookup_code, None)
    
    def __setitem__(self, lookup_code: str, file_info: dict):
        """向后兼容：设置文件信息（使用 None 作为用户ID）"""
        self.set(lookup_code, file_info, None)
    
    def __contains__(self, lookup_code: str) -> bool:
        """向后兼容：检查 lookup_code 是否存在（使用 None 作为用户ID）"""
        return self.exists(lookup_code, None)
    
    def __delitem__(self, lookup_code: str):
        """向后兼容：删除文件信息（使用 None 作为用户ID）"""
        self.delete(lookup_code, None)

file_info_cache = FileInfoCache()

# 加密密钥缓存包装类
class EncryptedKeyCache:
    """加密密钥缓存包装类（支持用户隔离）"""
    
    def get(self, lookup_code: str, user_id: Optional[int] = None) -> Optional[str]:
        """获取加密密钥"""
        cache_key = _make_cache_key(user_id, lookup_code)
        return cache_manager.get('encrypted_key', cache_key)
    
    def set(self, lookup_code: str, encrypted_key: str, user_id: Optional[int] = None, expire_at: Optional[datetime] = None):
        """设置加密密钥"""
        cache_key = _make_cache_key(user_id, lookup_code)
        # 如果未提供过期时间，尝试从 file_info_cache 或 chunk_cache 中获取
        # 注意：文件缓存使用标识码作为键，需要先获取标识码
        if expire_at is None:
            try:
                from app.services.mapping_service import get_identifier_code
                # 获取标识码（需要数据库会话，但这里没有，所以只能尝试从缓存获取）
                # 如果无法获取标识码，则跳过从文件缓存获取过期时间
                identifier_code = None
                # 尝试从文件信息缓存获取标识码（使用 lookup_code 作为键，因为可能还没有映射）
                if file_info_cache.exists(lookup_code, user_id):
                    file_info = file_info_cache.get(lookup_code, user_id)
                    identifier_code = file_info.get('identifier_code') if file_info else None
                
                # 如果找到了标识码，使用标识码查找文件缓存
                if identifier_code:
                    if file_info_cache.exists(identifier_code, user_id):
                        file_info = file_info_cache.get(identifier_code, user_id)
                        expire_at = file_info.get('pickup_expire_at') if file_info else None
                    elif chunk_cache.exists(identifier_code, user_id):
                        chunks = chunk_cache.get(identifier_code, user_id)
                        if chunks:
                            first_chunk = next(iter(chunks.values()))
                            expire_at = first_chunk.get('pickup_expire_at') or first_chunk.get('expires_at')
            except Exception as e:
                # 如果获取标识码失败，跳过从文件缓存获取过期时间
                pass
        
        cache_manager.set('encrypted_key', cache_key, encrypted_key, expire_at)
    
    def exists(self, lookup_code: str, user_id: Optional[int] = None) -> bool:
        """检查 lookup_code 是否存在"""
        cache_key = _make_cache_key(user_id, lookup_code)
        return cache_manager.exists('encrypted_key', cache_key)
    
    def delete(self, lookup_code: str, user_id: Optional[int] = None):
        """删除加密密钥"""
        cache_key = _make_cache_key(user_id, lookup_code)
        cache_manager.delete('encrypted_key', cache_key)
    
    def keys(self, user_id: Optional[int] = None):
        """获取所有 lookup_code（可选：按用户ID过滤）"""
        all_keys = cache_manager.get_all_keys('encrypted_key')
        if user_id is None:
            # 返回所有键（解析后只返回 lookup_code）
            return [_parse_cache_key(key)[1] for key in all_keys]
        else:
            # 只返回指定用户的键
            cache_key_prefix = f"{user_id}:"
            return [_parse_cache_key(key)[1] for key in all_keys if key.startswith(cache_key_prefix)]
    
    # 向后兼容：支持旧接口
    def __getitem__(self, lookup_code: str) -> str:
        """向后兼容：获取加密密钥（使用 None 作为用户ID）"""
        return self.get(lookup_code, None)
    
    def __setitem__(self, lookup_code: str, encrypted_key: str):
        """向后兼容：设置加密密钥（使用 None 作为用户ID）"""
        self.set(lookup_code, encrypted_key, None)
    
    def __contains__(self, lookup_code: str) -> bool:
        """向后兼容：检查 lookup_code 是否存在（使用 None 作为用户ID）"""
        return self.exists(lookup_code, None)
    
    def __delitem__(self, lookup_code: str):
        """向后兼容：删除加密密钥（使用 None 作为用户ID）"""
        self.delete(lookup_code, None)

encrypted_key_cache = EncryptedKeyCache()

# 加密密钥缓存（格式: {lookup_code: encryptedKeyBase64}）
# 
# ============================================================================
# 密钥概念体系（4个密钥相关概念及其关系）
# ============================================================================
# 
# 1. 文件加密密钥（原始密钥 / File Encryption Key）
#    - 类型：CryptoKey（AES-GCM，256位）
#    - 生成方式：随机生成（客户端）
#    - 用途：直接加密/解密文件块
#    - 存储位置：客户端浏览器缓存（以文件哈希为键）
#    - 是否传输到服务器：否（只传输加密后的版本）
# 
# 2. 密钥码（6位密钥码 / Key Code）
#    - 类型：字符串（6位大写字母+数字）
#    - 来源：取件码的后6位（如 "ABC123DEF456" 中的 "DEF456"）
#    - 用途：作为材料派生密钥，用于加密/解密文件加密密钥
#    - 是否传输到服务器：否（服务器只接收前6位查找码）
# 
# 3. 派生密钥（Derived Key）
#    - 类型：CryptoKey（AES-GCM，256位）
#    - 生成方式：从密钥码通过PBKDF2派生（100000次迭代，SHA-256）
#    - 用途：加密/解密文件加密密钥（原始密钥）
#    - 存储位置：不存储，每次使用时临时派生（客户端）
#    - 是否传输到服务器：否（只在客户端使用）
# 
# 4. 加密后的文件加密密钥（Encrypted File Encryption Key）
#    - 类型：字符串（Base64编码）
#    - 生成方式：用派生密钥加密文件加密密钥（原始密钥）
#    - 用途：安全存储到服务器，供接收者下载
#    - 存储位置：服务器内存缓存（本变量 encrypted_key_cache）
#    - 是否传输到服务器：是（这是唯一传输到服务器的密钥相关数据）
# 
# ============================================================================
# 密钥关系链（加密流程）
# ============================================================================
# 
# 取件码（12位）
# ├── 查找码（前6位）→ 用于服务器查询和缓存键
# └── 密钥码（后6位）→ 派生密钥 → 加密 → 文件加密密钥（原始密钥）→ 加密文件块
# 
# 详细流程：
# 1. Sender生成文件加密密钥（原始密钥）→ 随机生成，256位AES-GCM
# 2. Sender提取密钥码（后6位）→ 从取件码提取
# 3. Sender派生密钥 → 从密钥码通过PBKDF2派生256位AES-GCM密钥
# 4. Sender加密文件加密密钥 → 用派生密钥加密原始密钥
# 5. Sender存储到服务器 → 只存储加密后的密钥（Base64编码）← 存储在此缓存中
# 6. Receiver从服务器获取 → 获取加密后的密钥（从本缓存获取）
# 7. Receiver派生密钥 → 从密钥码通过PBKDF2派生相同的密钥
# 8. Receiver解密文件加密密钥 → 用派生密钥解密，得到原始密钥
# 9. Receiver解密文件块 → 用原始密钥解密文件块
# 
# ============================================================================
# 服务器可见性
# ============================================================================
# 
# 服务器可以看到（本缓存存储的内容）：
# - 查找码（前6位）：用于查询和缓存键
# - 加密后的文件加密密钥：Base64编码的加密数据（本缓存的值）
# - 加密后的文件块：加密后的文件数据
# 
# 服务器无法看到：
# - 密钥码（后6位）：不传输到服务器
# - 派生密钥：只在客户端生成和使用
# - 文件加密密钥（原始密钥）：不传输到服务器
# - 文件内容：已加密，无法解密
# 
# 因此，即使服务器被完全攻破，攻击者也无法：
# - 解密文件内容（缺少密钥码和原始密钥）
# - 获取原始密钥（缺少密钥码来派生密钥）
# - 解密文件块（缺少原始密钥）