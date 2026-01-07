#!/usr/bin/env python3
"""测试重构后的服务"""

from app.extensions import SessionLocal
from app.services.file_reuse_service import FileReuseService
from app.models.file import File

def test_file_reuse_service():
    print('测试文件复用服务...')

    db = SessionLocal()

    try:
        # 查找一个未废弃的文件
        test_file = db.query(File).filter(File.is_invalidated == False).first()
        if test_file:
            print(f'找到测试文件: id={test_file.id}, name={test_file.original_name}, hash={test_file.hash[:16]}...')

            # 手动测试哈希查找
            if test_file.hash:
                from app.utils.dedupe import derive_dedupe_fingerprint

                # 计算去重指纹
                fingerprint = derive_dedupe_fingerprint(
                    user_id=test_file.uploader_id,
                    plaintext_file_hash=test_file.hash
                )
                print(f'计算的指纹: {fingerprint}')
                print(f'数据库哈希: {test_file.hash}')
                print(f'指纹匹配: {fingerprint == test_file.hash}')

                # 直接查询数据库
                existing_by_hash = db.query(File).filter(
                    File.hash == fingerprint,
                    File.uploader_id == test_file.uploader_id
                ).first()
                print(f'哈希查询结果: {existing_by_hash.id if existing_by_hash else None}')

            # 测试1：使用哈希查找（模拟前端发送明文哈希）
            print('测试1：使用哈希查找...')
            # 注意：这里我们使用数据库哈希作为模拟的明文哈希
            # 实际使用中，前端发送的是真实的明文SHA-256
            existing_file, file_unchanged = FileReuseService.check_file_exists(
                hash_value="mock_frontend_hash",  # 模拟前端明文哈希
                original_name=test_file.original_name,
                size=test_file.size,
                uploader_id=test_file.uploader_id,
                db=db
            )
            print(f'哈希查找结果: {existing_file.id if existing_file else None}, unchanged={file_unchanged}')

            # 测试2：使用文件名+大小查找（无哈希）
            print('\\n测试2：使用文件名+大小查找...')
            existing_file2, file_unchanged2 = FileReuseService.check_file_exists(
                hash_value=None,  # 无哈希
                original_name=test_file.original_name,
                size=test_file.size,
                uploader_id=test_file.uploader_id,
                db=db
            )
            print(f'文件名查找结果: {existing_file2.id if existing_file2 else None}, unchanged={file_unchanged2}')

            existing_file = existing_file2  # 使用第二种查找的结果

            if existing_file:
                print(f'✅ 文件存在性检查成功: file_id={existing_file.id}, file_unchanged={file_unchanged}')

                # 测试活跃取件码检查
                has_active, active_code = FileReuseService.check_active_pickup_code(existing_file, db)
                print(f'✅ 活跃取件码检查: has_active={has_active}, code={active_code.code if active_code else None}')

            else:
                print('❌ 文件存在性检查失败')

        print('✅ 服务测试完成')

    except Exception as e:
        print(f'❌ 测试失败: {e}')
        import traceback
        traceback.print_exc()

    finally:
        db.close()

if __name__ == "__main__":
    test_file_reuse_service()
