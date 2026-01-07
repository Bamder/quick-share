"""
查看缓存内容脚本

功能：
- 查看文件块缓存（chunk_cache）
- 查看文件信息缓存（file_info_cache）
- 查看加密密钥缓存（encrypted_key_cache）
- 查看映射关系缓存（lookup_mapping）
- 查看上传池（upload_pool）和下载池（download_pool）

使用方法：
1. 直接运行：python scripts/inspect/view_cache.py
2. 或使用批处理：scripts/inspect/view_cache.bat
"""

import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import datetime, timezone
from app.extensions import SessionLocal
from app.services.cache_service import chunk_cache, file_info_cache, encrypted_key_cache
from app.services.pool_service import upload_pool, download_pool
from app.services.mapping_service import lookup_code_mapping
from app.utils.cache import cache_manager
from app.utils.pickup_code import ensure_aware_datetime
from app.config import settings
import logging
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def show_chunk_cache():
    """显示文件块缓存"""
    print("\n" + "=" * 80)
    print("文件块缓存 (chunk_cache)")
    print("=" * 80)
    
    try:
        all_keys = chunk_cache.keys()
        if not all_keys:
            print("  无文件块缓存")
            return
        
        print(f"  总缓存条目数: {len(all_keys)}")
        print()
        
        for lookup_code in all_keys[:20]:  # 只显示前20个
            # 尝试获取缓存（需要 user_id，但这里我们不知道，先尝试 None）
            chunks = chunk_cache.get(lookup_code, None)
            if chunks:
                chunk_count = len(chunks)
                total_size = sum(len(chunk.get('data', b'')) for chunk in chunks.values())
                first_chunk = next(iter(chunks.values()))
                expire_at = first_chunk.get('pickup_expire_at') or first_chunk.get('expires_at')
                
                print(f"  标识码: {lookup_code}")
                print(f"    块数量: {chunk_count}")
                print(f"    总大小: {format_size(total_size)}")
                if expire_at:
                    expire_at = ensure_aware_datetime(expire_at)
                    now = datetime.now(timezone.utc)
                    status = "未过期" if now < expire_at else "已过期"
                    print(f"    过期时间: {expire_at} ({status})")
                print()
        
        if len(all_keys) > 20:
            print(f"  ... 还有 {len(all_keys) - 20} 个缓存条目未显示")
    except Exception as e:
        print(f"  获取文件块缓存失败: {e}")


def show_file_info_cache():
    """显示文件信息缓存"""
    print("\n" + "=" * 80)
    print("文件信息缓存 (file_info_cache)")
    print("=" * 80)
    
    try:
        all_keys = file_info_cache.keys()
        if not all_keys:
            print("  无文件信息缓存")
            return
        
        print(f"  总缓存条目数: {len(all_keys)}")
        print()
        
        for lookup_code in all_keys[:20]:  # 只显示前20个
            file_info = file_info_cache.get(lookup_code, None)
            if file_info:
                print(f"  标识码: {lookup_code}")
                print(f"    文件名: {file_info.get('fileName', 'N/A')}")
                print(f"    文件大小: {format_size(file_info.get('fileSize', 0))}")
                print(f"    总块数: {file_info.get('totalChunks', 'N/A')}")
                print(f"    MIME类型: {file_info.get('mimeType', 'N/A')}")
                identifier_code = file_info.get('identifier_code')
                if identifier_code:
                    print(f"    标识码: {identifier_code}")
                expire_at = file_info.get('pickup_expire_at')
                if expire_at:
                    expire_at = ensure_aware_datetime(expire_at)
                    now = datetime.now(timezone.utc)
                    status = "未过期" if now < expire_at else "已过期"
                    print(f"    过期时间: {expire_at} ({status})")
                print()
        
        if len(all_keys) > 20:
            print(f"  ... 还有 {len(all_keys) - 20} 个缓存条目未显示")
    except Exception as e:
        print(f"  获取文件信息缓存失败: {e}")


def show_encrypted_key_cache():
    """显示加密密钥缓存"""
    print("\n" + "=" * 80)
    print("加密密钥缓存 (encrypted_key_cache)")
    print("=" * 80)
    
    try:
        all_keys = encrypted_key_cache.keys()
        if not all_keys:
            print("  无加密密钥缓存")
            return
        
        print(f"  总缓存条目数: {len(all_keys)}")
        print()
        
        for lookup_code in all_keys[:20]:  # 只显示前20个
            key = encrypted_key_cache.get(lookup_code, None)
            if key:
                print(f"  取件码: {lookup_code}")
                print(f"    密钥长度: {len(key)} 字符")
                print(f"    密钥预览: {key[:50]}..." if len(key) > 50 else f"    密钥: {key}")
                print()
        
        if len(all_keys) > 20:
            print(f"  ... 还有 {len(all_keys) - 20} 个缓存条目未显示")
    except Exception as e:
        print(f"  获取加密密钥缓存失败: {e}")


def show_mapping_cache():
    """显示映射关系缓存"""
    print("\n" + "=" * 80)
    print("映射关系缓存 (lookup_mapping)")
    print("=" * 80)
    
    try:
        # 内存映射
        print("  内存映射:")
        if lookup_code_mapping:
            print(f"    总映射数: {len(lookup_code_mapping)}")
            for lookup_code, identifier_code in list(lookup_code_mapping.items())[:20]:
                print(f"    {lookup_code} -> {identifier_code}")
            if len(lookup_code_mapping) > 20:
                print(f"    ... 还有 {len(lookup_code_mapping) - 20} 个映射未显示")
        else:
            print("    无内存映射")
        
        # Redis 映射
        print()
        print("  Redis 映射:")
        try:
            all_mapping_keys = cache_manager.get_all_keys('lookup_mapping')
            if all_mapping_keys:
                print(f"    总映射数: {len(all_mapping_keys)}")
                for mapping_key in all_mapping_keys[:20]:
                    identifier_code = cache_manager.get('lookup_mapping', mapping_key)
                    if identifier_code:
                        print(f"    {mapping_key} -> {identifier_code}")
                if len(all_mapping_keys) > 20:
                    print(f"    ... 还有 {len(all_mapping_keys) - 20} 个映射未显示")
            else:
                print("    无 Redis 映射")
        except Exception as e:
            print(f"    获取 Redis 映射失败: {e}")
    except Exception as e:
        print(f"  获取映射关系缓存失败: {e}")


def show_pools():
    """显示上传池和下载池"""
    print("\n" + "=" * 80)
    print("上传池和下载池")
    print("=" * 80)
    
    # 上传池
    print("  上传池 (upload_pool):")
    if upload_pool:
        print(f"    总条目数: {len(upload_pool)}")
        for identifier_code, chunks in list(upload_pool.items())[:10]:
            chunk_count = len(chunks) if chunks else 0
            print(f"    标识码: {identifier_code}, 块数量: {chunk_count}")
        if len(upload_pool) > 10:
            print(f"    ... 还有 {len(upload_pool) - 10} 个条目未显示")
    else:
        print("    无上传池数据")
    
    # 下载池
    print()
    print("  下载池 (download_pool):")
    if download_pool:
        total_sessions = sum(len(sessions) for sessions in download_pool.values())
        print(f"    总标识码数: {len(download_pool)}")
        print(f"    总会话数: {total_sessions}")
        for identifier_code, sessions in list(download_pool.items())[:10]:
            print(f"    标识码: {identifier_code}, 会话数: {len(sessions)}")
        if len(download_pool) > 10:
            print(f"    ... 还有 {len(download_pool) - 10} 个条目未显示")
    else:
        print("    无下载池数据")


def show_cache_config():
    """显示缓存配置"""
    print("\n" + "=" * 80)
    print("缓存配置")
    print("=" * 80)
    print(f"  Redis 启用: {settings.REDIS_ENABLED}")
    if settings.REDIS_ENABLED:
        print(f"  Redis 主机: {settings.REDIS_HOST}")
        print(f"  Redis 端口: {settings.REDIS_PORT}")
        print(f"  Redis 数据库: {settings.REDIS_DB}")
        print(f"  Redis 连接状态: {'已连接' if cache_manager._redis_client else '未连接'}")
    else:
        print("  使用内存缓存（回退模式）")


def main():
    """主函数"""
    print("=" * 80)
    print("缓存内容查看工具")
    print("=" * 80)
    print(f"查看时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # 显示缓存配置
    show_cache_config()
    
    # 显示各种缓存
    show_chunk_cache()
    show_file_info_cache()
    show_encrypted_key_cache()
    show_mapping_cache()
    show_pools()
    
    print("\n" + "=" * 80)
    print("查看完成")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        print(f"\n执行失败: {e}")

