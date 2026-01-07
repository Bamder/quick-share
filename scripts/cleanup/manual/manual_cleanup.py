"""
手动清理过期缓存脚本

功能：
- 清理所有已过期的取件码的缓存（文件块、文件信息、加密密钥）
- 清理所有已过期的映射关系
- 显示清理前后的缓存状态

使用方法：
1. 直接运行：python scripts/cleanup/manual/manual_cleanup.py
2. 或使用批处理：scripts/cleanup/manual/manual_cleanup.bat
"""

import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 添加 scripts 目录到 Python 路径
scripts_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from datetime import datetime, timezone
from app.extensions import SessionLocal
from app.services.cleanup_service import cleanup_expired_chunks
from app.services.cache_service import chunk_cache, file_info_cache, encrypted_key_cache
from app.models.pickup_code import PickupCode
from app.models.file import File
from app.utils.pickup_code import check_and_update_expired_pickup_code, ensure_aware_datetime
from app.utils.cache import cache_manager
from app.config import settings
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def show_cache_stats(db):
    """显示缓存统计信息"""
    print("\n" + "=" * 60)
    print("缓存统计信息")
    print("=" * 60)
    
    # 显示缓存配置信息
    print("\n缓存配置信息:")
    print(f"  • REDIS_ENABLED: {settings.REDIS_ENABLED}")
    if settings.REDIS_ENABLED:
        print(f"  • REDIS_HOST: {settings.REDIS_HOST}")
        print(f"  • REDIS_PORT: {settings.REDIS_PORT}")
        print(f"  • REDIS_DB: {settings.REDIS_DB}")
        print(f"  • REDIS_PASSWORD: {'***' if settings.REDIS_PASSWORD else 'None'}")
    print(f"  • 实际使用: {'Redis' if cache_manager._use_redis else '内存字典'}")
    
    # 显示缓存管理器状态
    print(f"\n缓存管理器状态:")
    print(f"  • 使用 Redis: {cache_manager._use_redis}")
    if cache_manager._use_redis:
        try:
            redis_info = cache_manager._redis_client.info('server')
            print(f"  • Redis 版本: {redis_info.get('redis_version', 'unknown')}")
        except:
            print(f"  • Redis 连接状态: 未知")
    else:
        print(f"  • 使用内存字典缓存")
        print(f"  • 内存字典前缀数量: {len(cache_manager._fallback_cache)}")
        for prefix in cache_manager._fallback_cache:
            print(f"    - {prefix}: {len(cache_manager._fallback_cache[prefix])} 个键")
    
    # 直接查询所有键（调试用）
    print(f"\n直接查询缓存键（调试）:")
    raw_chunk_keys = cache_manager.get_all_keys('chunk')
    raw_file_info_keys = cache_manager.get_all_keys('file_info')
    raw_key_keys = cache_manager.get_all_keys('encrypted_key')
    print(f"  • chunk 原始键数量: {len(raw_chunk_keys)}")
    if raw_chunk_keys:
        print(f"  • chunk 原始键示例: {raw_chunk_keys[:5]}")
    print(f"  • file_info 原始键数量: {len(raw_file_info_keys)}")
    if raw_file_info_keys:
        print(f"  • file_info 原始键示例: {raw_file_info_keys[:5]}")
    print(f"  • encrypted_key 原始键数量: {len(raw_key_keys)}")
    if raw_key_keys:
        print(f"  • encrypted_key 原始键示例: {raw_key_keys[:5]}")
    
    # 如果使用 Redis，直接查询 Redis 的所有键（调试用）
    if cache_manager._use_redis and cache_manager._redis_client:
        print(f"\nRedis 直接查询（调试）:")
        try:
            # 查询所有 quickshare:* 键
            all_redis_keys = []
            for key in cache_manager._redis_client.scan_iter(match="quickshare:*"):
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                all_redis_keys.append(key_str)
            print(f"  • Redis 中所有 quickshare:* 键数量: {len(all_redis_keys)}")
            if all_redis_keys:
                print(f"  • Redis 键示例: {all_redis_keys[:10]}")
            
            # 按前缀分类统计
            chunk_count = sum(1 for k in all_redis_keys if k.startswith('quickshare:chunk:'))
            file_info_count = sum(1 for k in all_redis_keys if k.startswith('quickshare:file_info:'))
            key_count = sum(1 for k in all_redis_keys if k.startswith('quickshare:encrypted_key:'))
            print(f"  • quickshare:chunk:* 键数量: {chunk_count}")
            print(f"  • quickshare:file_info:* 键数量: {file_info_count}")
            print(f"  • quickshare:encrypted_key:* 键数量: {key_count}")
        except Exception as e:
            print(f"  • Redis 查询失败: {e}")
            logger.exception("Redis 查询异常")
    
    # 统计文件块缓存
    chunk_keys = chunk_cache.keys()
    print(f"\n文件块缓存:")
    print(f"  • 总数量: {len(chunk_keys)}")
    if chunk_keys:
        print(f"  • 查找码列表: {sorted(chunk_keys)[:10]}{'...' if len(chunk_keys) > 10 else ''}")
    
    # 统计文件信息缓存
    file_info_keys = file_info_cache.keys()
    print(f"\n文件信息缓存:")
    print(f"  • 总数量: {len(file_info_keys)}")
    if file_info_keys:
        print(f"  • 查找码列表: {sorted(file_info_keys)[:10]}{'...' if len(file_info_keys) > 10 else ''}")
        # 展示前3个的标识码字段（identifier_code / identifier_expire_at），便于确认绑定关系
        sample_info = []
        for code in sorted(file_info_keys)[:3]:
            try:
                fi = file_info_cache.get(code, None) or {}
                sample_info.append((code, fi.get('identifier_code'), fi.get('identifier_expire_at')))
            except Exception:
                sample_info.append((code, None, None))
        if sample_info:
            print("  • 示例标识码:")
            for code, ident, ident_exp in sample_info:
                print(f"    - lookup_code={code}, identifier_code={ident}, identifier_expire_at={ident_exp}")
    
    # 统计加密密钥缓存
    key_keys = encrypted_key_cache.keys()
    print(f"\n加密密钥缓存:")
    print(f"  • 总数量: {len(key_keys)}")
    if key_keys:
        print(f"  • 查找码列表: {sorted(key_keys)[:10]}{'...' if len(key_keys) > 10 else ''}")
    
    # 统计数据库中的取件码
    now = datetime.now(timezone.utc)
    all_pickup_codes = db.query(PickupCode).all()
    expired_pickup_codes = []
    valid_pickup_codes = []
    
    for pickup_code in all_pickup_codes:
        # 检查并更新过期状态
        check_and_update_expired_pickup_code(pickup_code, db)
        db.refresh(pickup_code)
        
        if pickup_code.status == "expired":
            expired_pickup_codes.append(pickup_code)
        else:
            valid_pickup_codes.append(pickup_code)
    
    db.commit()
    
    print(f"\n数据库取件码:")
    print(f"  • 总数: {len(all_pickup_codes)}")
    print(f"  • 有效（未过期）: {len(valid_pickup_codes)}")
    print(f"  • 已过期: {len(expired_pickup_codes)}")
    
    if expired_pickup_codes:
        print(f"\n已过期的取件码（前10个）:")
        for pickup_code in expired_pickup_codes[:10]:
            expire_at = ensure_aware_datetime(pickup_code.expire_at) if pickup_code.expire_at else None
            age = (now - expire_at).total_seconds() / 3600 if expire_at else 0
            print(f"    - {pickup_code.code} (过期于: {expire_at}, {age:.1f}小时前)")
        if len(expired_pickup_codes) > 10:
            print(f"    ... 还有 {len(expired_pickup_codes) - 10} 个已过期的取件码")
    
    print("=" * 60)


def main():
    """主函数"""
    print("=" * 60)
    print("手动清理过期缓存")
    print("=" * 60)
    print()
    
    # 创建数据库会话
    db = SessionLocal()
    
    try:
        # 显示清理前的状态
        print("清理前的状态:")
        show_cache_stats(db)
        
        # 确认是否继续
        print("\n是否继续清理？(y/n): ", end="")
        try:
            confirm = input().strip().lower()
            if confirm not in ['y', 'yes', '是']:
                print("已取消清理")
                return
        except KeyboardInterrupt:
            print("\n已取消清理")
            return
        
        # 执行清理
        print("\n" + "=" * 60)
        print("开始清理...")
        print("=" * 60)
        
        cleanup_expired_chunks(db)
        
        print("\n" + "=" * 60)
        print("清理完成！")
        print("=" * 60)
        
        # 显示清理后的状态
        print("\n清理后的状态:")
        show_cache_stats(db)
        
    except Exception as e:
        logger.error(f"清理失败: {e}", exc_info=True)
        print(f"\n❌ 清理失败: {e}")
        print("请查看日志获取详细信息")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()

