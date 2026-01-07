from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.models.pickup_code import PickupCode
from app.utils.cache import cache_manager
from app.utils.pickup_code import ensure_aware_datetime
from app.services.cache_service import chunk_cache, file_info_cache, encrypted_key_cache
import logging

logger = logging.getLogger(__name__)
# 临时上传池（用于优化性能）
# 格式：{original_lookup_code: {chunk_index: chunk_data, ...}}
# 上传时先写入临时池（内存操作，快速），完成后再批量写入主缓存
upload_pool = {}

# 下载池（用于优化下载性能）
# 格式：{original_lookup_code: {
#   session_id: {
#     'chunks': {chunk_index: chunk_data, ...},  # 预读取的块
#     'last_access': datetime,  # 最后访问时间
#     'access_count': int,  # 访问次数
#     'total_chunks': int,  # 总块数
#     'loaded_chunks': set,  # 已加载的块索引
#   },
#   ...
# }}
# 每个会话拥有独立的下载池，避免多个Receiver之间的竞争
download_pool = {}

def cleanup_upload_pool():
    """
    清理临时上传池中过期的数据
    临时池中的数据如果超过一定时间未完成上传，应该清理
    """
    now = datetime.now(timezone.utc)
    expired_keys = []
    
    # 清理超过1小时未完成的临时池数据
    for lookup_code, chunks in list(upload_pool.items()):
        if not chunks:
            expired_keys.append(lookup_code)
            continue
        
        # 检查第一个块的创建时间
        first_chunk = next(iter(chunks.values()))
        created_at = first_chunk.get('created_at')
        if created_at:
            created_at = ensure_aware_datetime(created_at)
            # 如果超过1小时未完成，清理
            if (now - created_at).total_seconds() > 3600:
                expired_keys.append(lookup_code)
                logger.info(f"清理过期的临时上传池: lookup_code={lookup_code}, 创建时间={created_at}")
    
    for key in expired_keys:
        if key in upload_pool:
            del upload_pool[key]


async def preload_next_chunks(original_lookup_code: str, session_id: str, current_index: int, total_chunks: int, preload_count: int = 10, user_id: Optional[int] = None):
    """
    预读取后续块到下载池（异步，不阻塞）
    
    参数:
    - original_lookup_code: 标识码（用于访问文件块缓存）
    - session_id: 会话ID（用于隔离不同Receiver的下载池）
    - current_index: 当前块索引（或最大索引，用于批量下载）
    - total_chunks: 总块数
    - preload_count: 预读取的块数量（默认10个）
    - user_id: 用户ID（用于缓存隔离，如果为None则尝试从文件信息缓存获取）
    """
    try:
        if original_lookup_code not in download_pool:
            return
        
        if session_id not in download_pool[original_lookup_code]:
            return
        
        pool = download_pool[original_lookup_code][session_id]
        
        # 计算需要预读取的块索引
        start_index = current_index + 1
        end_index = min(start_index + preload_count, total_chunks)
        
        if start_index >= end_index:
            return  # 没有需要预读取的块
        
        # 从主缓存读取并存入下载池（一次性读取整个字典，避免重复反序列化）
        # 注意：original_lookup_code 是标识码，使用标识码访问文件块缓存
        # 如果 user_id 为 None，尝试从文件信息缓存获取（先尝试 None，再尝试其他可能的 user_id）
        chunks_dict = None
        used_user_id = user_id
        
        if used_user_id is not None:
            # 使用提供的 user_id
            if chunk_cache.exists(original_lookup_code, used_user_id):
                chunks_dict = chunk_cache.get(original_lookup_code, used_user_id)
        else:
            # 尝试 None（匿名用户）
            if chunk_cache.exists(original_lookup_code, None):
                chunks_dict = chunk_cache.get(original_lookup_code, None)
                used_user_id = None
            else:
                # 尝试从文件信息缓存获取 user_id（通过查找所有可能的 user_id）
                # 注意：这需要遍历所有可能的 user_id，但为了性能，我们只尝试常见的
                # 实际上，如果 user_id 为 None，说明可能是匿名用户，我们已经尝试过了
                # 如果还是找不到，可能是缓存不存在或已过期
                pass
        
        if chunks_dict:
            chunks_to_add = {}
            for idx in range(start_index, end_index):
                if idx in chunks_dict and idx not in pool['chunks']:
                    chunks_to_add[idx] = chunks_dict[idx]
            
            # 批量添加到下载池（优化：一次性更新，而不是逐个更新）
            if chunks_to_add:
                pool['chunks'].update(chunks_to_add)
                pool['loaded_chunks'].update(chunks_to_add.keys())
                logger.debug(f"[preload] 预读取 {len(chunks_to_add)} 个块到下载池 (session={session_id[:8]}..., user_id={used_user_id}): {list(chunks_to_add.keys())[:5]}...")
    except Exception as e:
        logger.warning(f"预读取块失败: {e}")


def cleanup_download_pool():
    """
    清理下载池中未使用的数据
    下载池中的数据如果超过一定时间未访问，应该清理
    """
    now = datetime.now(timezone.utc)
    expired_sessions = []  # [(lookup_code, session_id), ...]
    empty_lookup_codes = []  # 如果某个lookup_code的所有会话都被清理，也清理这个lookup_code
    
    # 清理超过10分钟未访问的下载池数据
    for lookup_code, sessions_dict in list(download_pool.items()):
        if not isinstance(sessions_dict, dict):
            # 兼容旧格式（如果存在）
            empty_lookup_codes.append(lookup_code)
            continue
        
        for session_id, pool_data in list(sessions_dict.items()):
            last_access = pool_data.get('last_access')
            if last_access:
                last_access = ensure_aware_datetime(last_access)
                # 如果超过10分钟未访问，清理
                if (now - last_access).total_seconds() > 600:
                    expired_sessions.append((lookup_code, session_id))
                    logger.debug(f"清理过期的下载池会话: lookup_code={lookup_code}, session_id={session_id[:8]}..., 最后访问={last_access}")
        
        # 检查是否所有会话都被清理
        if lookup_code in download_pool:
            remaining_sessions = [s for s in download_pool[lookup_code].keys() if (lookup_code, s) not in expired_sessions]
            if not remaining_sessions:
                empty_lookup_codes.append(lookup_code)
    
    # 删除过期的会话
    for lookup_code, session_id in expired_sessions:
        if lookup_code in download_pool and session_id in download_pool[lookup_code]:
            del download_pool[lookup_code][session_id]
    
    # 删除空的lookup_code
    for lookup_code in empty_lookup_codes:
        if lookup_code in download_pool:
            del download_pool[lookup_code]


