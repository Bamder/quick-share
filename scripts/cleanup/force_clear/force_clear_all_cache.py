"""
强制清理所有缓存脚本

⚠️ 警告：此脚本会强制清理所有缓存（包括未过期的），请谨慎使用！

功能：
- 强制清理所有文件块缓存
- 强制清理所有文件信息缓存
- 强制清理所有加密密钥缓存
- 清理所有映射关系（内存和Redis）
- 显示清理前后的缓存状态

使用场景：
- 测试环境重置
- 开发调试
- 紧急情况下的缓存清理

使用方法：
1. 直接运行：python scripts/cleanup/force_clear/force_clear_all_cache.py
2. 或使用批处理：scripts/cleanup/force_clear/force_clear_all_cache.bat
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
from app.services.cache_service import chunk_cache, file_info_cache, encrypted_key_cache
from app.services.mapping_service import lookup_code_mapping
from app.services.pool_service import upload_pool, download_pool
from app.utils.cache import cache_manager
from app.models.pickup_code import PickupCode
from app.config import settings
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 显示缓存配置信息
def show_cache_config():
    """显示缓存配置信息"""
    print("\n缓存配置信息:")
    print(f"  • REDIS_ENABLED: {settings.REDIS_ENABLED}")
    if settings.REDIS_ENABLED:
        print(f"  • REDIS_HOST: {settings.REDIS_HOST}")
        print(f"  • REDIS_PORT: {settings.REDIS_PORT}")
        print(f"  • REDIS_DB: {settings.REDIS_DB}")
        print(f"  • REDIS_PASSWORD: {'***' if settings.REDIS_PASSWORD else 'None'}")
    print(f"  • 实际使用: {'Redis' if cache_manager._use_redis else '内存字典'}")


def show_cache_stats():
    """显示缓存统计信息"""
    print("\n" + "=" * 60)
    print("缓存统计信息")
    print("=" * 60)
    
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
        # 展示前3个的标识码字段，便于确认标识码与文件缓存绑定
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
    
    # 统计映射关系
    mapping_count = len(lookup_code_mapping)
    print(f"\n映射关系:")
    print(f"  • 内存中的映射数量: {mapping_count}")
    if mapping_count > 0:
        print(f"  • 映射列表: {list(lookup_code_mapping.items())[:10]}{'...' if mapping_count > 10 else ''}")
    
    # 统计上传池
    upload_pool_count = len(upload_pool)
    print(f"\n上传池:")
    print(f"  • 查找码数量: {upload_pool_count}")
    if upload_pool_count > 0:
        print(f"  • 查找码列表: {list(upload_pool.keys())[:10]}{'...' if upload_pool_count > 10 else ''}")
    
    # 统计下载池
    download_pool_count = len(download_pool)
    print(f"\n下载池:")
    print(f"  • 查找码数量: {download_pool_count}")
    if download_pool_count > 0:
        print(f"  • 查找码列表: {list(download_pool.keys())[:10]}{'...' if download_pool_count > 10 else ''}")
    
    # 统计数据库中的取件码
    try:
        db = SessionLocal()
        try:
            from app.utils.pickup_code import check_and_update_expired_pickup_code
            from datetime import datetime, timezone
            
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
                    from app.utils.pickup_code import ensure_aware_datetime
                    expire_at = ensure_aware_datetime(pickup_code.expire_at) if pickup_code.expire_at else None
                    age = (now - expire_at).total_seconds() / 3600 if expire_at else 0
                    print(f"    - {pickup_code.code} (过期于: {expire_at}, {age:.1f}小时前)")
                if len(expired_pickup_codes) > 10:
                    print(f"    ... 还有 {len(expired_pickup_codes) - 10} 个已过期的取件码")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"查询数据库取件码失败: {e}")
    
    print("=" * 60)


def clear_all_cache():
    """强制清理所有缓存"""
    print("\n" + "=" * 60)
    print("开始强制清理所有缓存...")
    print("=" * 60)
    
    cleared_count = {
        'chunk': 0,
        'file_info': 0,
        'encrypted_key': 0,
        'mapping': 0,
        'upload_pool': 0,
        'download_pool': 0,
        'registered_senders': 0,
        'pickup_codes': 0
    }
    
    # 1. 清理文件块缓存（所有用户）
    print("\n[1/6] 清理文件块缓存...")
    from app.services.cache_service import _parse_cache_key
    try:
        all_chunk_cache_keys = cache_manager.get_all_keys('chunk')
        for cache_key in all_chunk_cache_keys:
            user_id, lookup_code = _parse_cache_key(cache_key)
            if chunk_cache.exists(lookup_code, user_id):
                chunk_cache.delete(lookup_code, user_id)
                cleared_count['chunk'] += 1
                logger.info(f"删除文件块缓存: lookup_code={lookup_code}, user_id={user_id}")
    except Exception as e:
        logger.warning(f"清理文件块缓存失败: {e}")
        # 回退：从 chunk_cache.keys() 获取
        all_chunk_keys = list(chunk_cache.keys())
        for lookup_code in all_chunk_keys:
            # 尝试删除 None 和所有可能的用户ID
            for user_id in [None]:  # 简单回退，只尝试 None
                if chunk_cache.exists(lookup_code, user_id):
                    chunk_cache.delete(lookup_code, user_id)
                    cleared_count['chunk'] += 1
    
    # 2. 清理文件信息缓存（所有用户）
    print("[2/6] 清理文件信息缓存...")
    try:
        all_file_info_cache_keys = cache_manager.get_all_keys('file_info')
        for cache_key in all_file_info_cache_keys:
            user_id, lookup_code = _parse_cache_key(cache_key)
            if file_info_cache.exists(lookup_code, user_id):
                file_info_cache.delete(lookup_code, user_id)
                cleared_count['file_info'] += 1
                logger.info(f"删除文件信息缓存: lookup_code={lookup_code}, user_id={user_id}")
    except Exception as e:
        logger.warning(f"清理文件信息缓存失败: {e}")
        # 回退：从 file_info_cache.keys() 获取
        all_file_info_keys = list(file_info_cache.keys())
        for lookup_code in all_file_info_keys:
            for user_id in [None]:
                if file_info_cache.exists(lookup_code, user_id):
                    file_info_cache.delete(lookup_code, user_id)
                    cleared_count['file_info'] += 1
    
    # 3. 清理加密密钥缓存（所有用户）
    print("[3/6] 清理加密密钥缓存...")
    try:
        all_key_cache_keys = cache_manager.get_all_keys('encrypted_key')
        for cache_key in all_key_cache_keys:
            user_id, lookup_code = _parse_cache_key(cache_key)
            if encrypted_key_cache.exists(lookup_code, user_id):
                encrypted_key_cache.delete(lookup_code, user_id)
                cleared_count['encrypted_key'] += 1
                logger.info(f"删除加密密钥缓存: lookup_code={lookup_code}, user_id={user_id}")
    except Exception as e:
        logger.warning(f"清理加密密钥缓存失败: {e}")
        # 回退：从 encrypted_key_cache.keys() 获取
        all_key_keys = list(encrypted_key_cache.keys())
        for lookup_code in all_key_keys:
            for user_id in [None]:
                if encrypted_key_cache.exists(lookup_code, user_id):
                    encrypted_key_cache.delete(lookup_code, user_id)
                    cleared_count['encrypted_key'] += 1
    
    # 4. 清理映射关系（内存）
    print("[4/6] 清理内存中的映射关系...")
    mapping_keys = list(lookup_code_mapping.keys())
    for lookup_code in mapping_keys:
        if lookup_code in lookup_code_mapping:
            del lookup_code_mapping[lookup_code]
            cleared_count['mapping'] += 1
            logger.info(f"删除内存映射关系: lookup_code={lookup_code}")
    
    # 5. 清理映射关系（Redis）
    print("[5/6] 清理Redis中的映射关系...")
    try:
        all_mapping_keys = cache_manager.get_all_keys('lookup_mapping')
        for mapping_key in all_mapping_keys:
            cache_manager.delete('lookup_mapping', mapping_key)
            cleared_count['mapping'] += 1
            logger.debug(f"删除Redis映射关系: lookup_code={mapping_key}")
    except Exception as e:
        logger.warning(f"清理Redis映射关系失败: {e}")
    
    # 6. 清理上传池和下载池
    print("[6/7] 清理上传池和下载池...")
    upload_pool_keys = list(upload_pool.keys())
    for lookup_code in upload_pool_keys:
        if lookup_code in upload_pool:
            del upload_pool[lookup_code]
            cleared_count['upload_pool'] += 1
            logger.info(f"删除上传池: lookup_code={lookup_code}")
    
    download_pool_keys = list(download_pool.keys())
    for lookup_code in download_pool_keys:
        if lookup_code in download_pool:
            del download_pool[lookup_code]
            cleared_count['download_pool'] += 1
            logger.info(f"删除下载池: lookup_code={lookup_code}")
    
    # 7. 删除数据库中所有取件码记录（包括未过期的）
    print("[7/7] 删除数据库中所有取件码记录...")
    db = SessionLocal()
    try:
        from sqlalchemy import text
        
        # 查询所有取件码
        all_pickup_codes = db.query(PickupCode).all()
        all_codes = [pc.code for pc in all_pickup_codes]
        
        if not all_codes:
            logger.info("数据库中没有任何取件码记录")
        else:
            # 7.1 先删除引用这些取件码的其他表中的记录（解决外键约束）
            # 删除 registered_senders 表中的相关记录
            try:
                # 检查表是否存在
                result = db.execute(text("SHOW TABLES LIKE 'registered_senders'"))
                if result.fetchone():
                    # 删除 registered_senders 表中引用所有取件码的记录
                    deleted_senders = db.execute(
                        text("DELETE FROM registered_senders WHERE code IN :codes"),
                        {"codes": tuple(all_codes)}
                    )
                    cleared_count['registered_senders'] = deleted_senders.rowcount
                    logger.info(f"删除 registered_senders 表中的 {deleted_senders.rowcount} 条记录")
            except Exception as e:
                logger.warning(f"清理 registered_senders 表失败（可能表不存在）: {e}")
                cleared_count['registered_senders'] = 0
            
            # 7.2 删除所有取件码记录
            deleted_count = 0
            for code in all_codes:
                try:
                    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
                    if pickup_code:
                        lookup_code = code[:6] if len(code) >= 6 else None
                        db.delete(pickup_code)
                        deleted_count += 1
                        
                        if lookup_code:
                            logger.debug(f"删除取件码记录: code={code}, lookup_code={lookup_code}")
                        else:
                            logger.debug(f"删除取件码记录: code={code}")
                except Exception as e:
                    logger.warning(f"删除取件码 {code} 失败: {e}")
            
            if deleted_count > 0:
                db.commit()
                cleared_count['pickup_codes'] = deleted_count
                logger.info(f"共删除 {deleted_count} 个取件码记录")
            else:
                db.commit()
                cleared_count['pickup_codes'] = 0
                logger.info("没有成功删除任何取件码记录")
    except Exception as e:
        logger.error(f"删除取件码记录失败: {e}", exc_info=True)
        if db:
            db.rollback()
        cleared_count['pickup_codes'] = 0
        cleared_count['registered_senders'] = 0
    finally:
        db.close()
    
    print("\n" + "=" * 60)
    print("强制清理完成！")
    print("=" * 60)
    print(f"\n清理统计:")
    print(f"  • 文件块缓存: {cleared_count['chunk']} 个")
    print(f"  • 文件信息缓存: {cleared_count['file_info']} 个")
    print(f"  • 加密密钥缓存: {cleared_count['encrypted_key']} 个")
    print(f"  • 映射关系: {cleared_count['mapping']} 个")
    print(f"  • 上传池: {cleared_count['upload_pool']} 个")
    print(f"  • 下载池: {cleared_count['download_pool']} 个")
    if 'registered_senders' in cleared_count:
        print(f"  • registered_senders 记录: {cleared_count['registered_senders']} 个")
    if 'pickup_codes' in cleared_count:
        print(f"  • 取件码记录: {cleared_count['pickup_codes']} 个")
    print("=" * 60)


def main():
    """主函数"""
    print("=" * 60)
    print("⚠️  强制清理所有缓存")
    print("=" * 60)
    print()
    print("警告：此脚本会强制清理所有缓存和数据库记录，包括：")
    print("  • 所有文件块缓存（包括未过期的）")
    print("  • 所有文件信息缓存（包括未过期的）")
    print("  • 所有加密密钥缓存（包括未过期的）")
    print("  • 所有映射关系（内存和Redis）")
    print("  • 所有上传池和下载池")
    print("  • 所有数据库取件码记录（包括未过期的）")
    print("  • 所有 registered_senders 记录（如果存在）")
    print()
    print("⚠️  此操作不可逆！")
    print()
    
    # 显示缓存配置
    show_cache_config()
    
    # 显示清理前的状态
    print("\n清理前的状态:")
    show_cache_stats()
    
    # 二次确认
    print("\n" + "=" * 60)
    print("⚠️  二次确认")
    print("=" * 60)
    print("请输入 'CLEAR ALL' 以确认清理所有缓存: ", end="")
    try:
        confirm = input().strip()
        if confirm != "CLEAR ALL":
            print("确认失败，已取消清理")
            return
    except KeyboardInterrupt:
        print("\n已取消清理")
        return
    
    # 执行清理
    try:
        clear_all_cache()
        
        # 显示清理后的状态
        print("\n清理后的状态:")
        show_cache_stats()
        
        print("\n✅ 所有缓存已清理完成！")
        
    except Exception as e:
        logger.error(f"清理失败: {e}", exc_info=True)
        print(f"\n❌ 清理失败: {e}")
        print("请查看日志获取详细信息")


if __name__ == "__main__":
    main()

