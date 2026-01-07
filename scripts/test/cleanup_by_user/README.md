# 清理服务测试说明

## 测试脚本

`test_cleanup_by_user.py` - 测试清理服务按用户ID正确清理缓存

## 使用方法

### Windows (推荐)

**方法1: 使用批处理脚本（最简单）**
```cmd
scripts\test\cleanup_by_user\run_cleanup_test.bat
```

**方法2: 使用 PowerShell 脚本**
```powershell
scripts\test\cleanup_by_user\run_cleanup_test.ps1
```

**方法3: 手动运行**
```cmd
# 激活虚拟环境
venv\Scripts\activate

# 运行测试
python scripts\test\cleanup_by_user\test_cleanup_by_user.py
```

### Linux/Mac

```bash
# 确保在项目根目录
cd /path/to/quick-share

# 激活虚拟环境
source venv/bin/activate

# 运行测试
python scripts/test/cleanup_by_user/test_cleanup_by_user.py
```

## 测试内容

测试脚本会：

1. **创建测试数据**
   - 创建两个测试用户（test_user_1 和 test_user_2）
   - 为每个用户创建两个取件码：
     - 一个已过期的（1小时前）
     - 一个未过期的（1小时后）

2. **设置测试缓存**
   - 为每个取件码设置：
     - 文件块缓存（chunk_cache）
     - 文件信息缓存（file_info_cache）
     - 加密密钥缓存（encrypted_key_cache）
   - 使用正确的用户ID和过期时间

3. **验证清理前状态**
   - 确认所有缓存数据都存在

4. **执行清理服务**
   - 调用 `cleanup_expired_chunks(db)`

5. **验证清理后状态**
   - 确认已过期的缓存被清理
   - 确认未过期的缓存被保留
   - 验证用户隔离（用户1的数据不影响用户2）

6. **清理测试数据**
   - 删除测试用户、文件、取件码和缓存

## 预期结果

清理后：
- ✓ 用户1的已过期数据（TEST01）被清理
- ✓ 用户1的未过期数据（TEST02）保留
- ✓ 用户2的已过期数据（TEST03）被清理
- ✓ 用户2的未过期数据（TEST04）保留
- ✓ 用户1的缓存键只包含 TEST02
- ✓ 用户2的缓存键只包含 TEST04

## 手动测试步骤

如果你想手动测试清理服务：

### 1. 准备测试数据

```python
from app.extensions import SessionLocal
from app.services.cleanup_service import cleanup_expired_chunks

db = SessionLocal()
cleanup_expired_chunks(db)
db.close()
```

### 2. 检查缓存状态

```python
from app.services.cache_service import chunk_cache, file_info_cache, encrypted_key_cache

# 查看所有缓存键
print("文件块缓存键:", chunk_cache.keys())
print("文件信息缓存键:", file_info_cache.keys())
print("加密密钥缓存键:", encrypted_key_cache.keys())

# 按用户ID查看
print("用户1的文件块:", chunk_cache.keys(user_id=1))
print("用户2的文件块:", chunk_cache.keys(user_id=2))
```

### 3. 验证清理结果

- 检查日志输出，确认清理了正确的数据
- 验证不同用户的缓存被正确隔离
- 确认只有过期的数据被清理

## 注意事项

1. **数据库连接**：确保数据库服务正在运行
2. **Redis连接**：如果使用Redis，确保Redis服务正在运行
3. **测试数据**：测试脚本会自动清理测试数据，但如果有错误可能需要手动清理
4. **时间设置**：测试使用UTC时间，确保系统时间正确

## 故障排查

如果测试失败：

1. **检查日志**：查看详细的日志输出
2. **检查数据库**：确认测试数据是否正确创建
3. **检查缓存**：使用上面的手动检查方法验证缓存状态
4. **检查时间**：确认系统时间和时区设置正确

