# Python 3.12 测试环境设置指南

## 背景

由于Python 3.13.5与某些依赖包（如pydantic-core）的兼容性问题，我们为测试环境单独配置Python 3.12，以获得更好的稳定性和兼容性。

## 环境架构

```
quick-share/
├── venv/                    # 项目主环境 (Python 3.13.5)
│   └── 用于实际运行项目
├── venv-test/              # 测试专用环境 (Python 3.12)
│   └── 用于运行测试套件
└── scripts/test/           # 测试脚本目录
    └── 所有测试模块
```

## 设置步骤

### 1. 安装Python 3.12

**方法1：官方安装包（推荐）**
```bash
# 下载并安装Python 3.12.0
# https://www.python.org/downloads/release/python-3120/
# 安装时勾选 "Add Python to PATH"
```

**方法2：使用pyenv（支持多版本管理）**
```bash
# 安装pyenv-win
# https://github.com/pyenv-win/pyenv-win

pyenv install 3.12.0
pyenv versions  # 查看已安装版本
```

### 2. 创建测试环境

运行自动设置脚本：
```bash
scripts\test\setup_python312_env.bat
```

或者手动创建：
```bash
# 确保使用Python 3.12
python --version  # 应该显示 3.12.x

# 创建测试环境
python -m venv venv-test

# 激活环境
venv-test\Scripts\activate

# 安装依赖
pip install -r requirements.txt
pip install -r scripts/test/test-requirements.txt
```

### 3. 验证环境

```bash
# 激活测试环境
venv-test\Scripts\activate

# 检查Python版本
python --version  # 应该显示 3.12.x

# 测试依赖导入
python -c "import pydantic, sqlalchemy, fastapi; print('✅ 依赖正常')"
```

## 运行测试

### 方法1：使用批处理脚本（推荐）
```bash
# 运行单个测试模块
scripts\test\auth\run_auth_test.bat
scripts\test\file_operations\run_file_test.bat
scripts\test\pickup_code\run_pickup_test.bat
# ... 其他测试模块
```

### 方法2：直接运行Python脚本
```bash
# 激活测试环境
venv-test\Scripts\activate

# 运行测试
python scripts/test/auth/test_auth.py
python scripts/test/file_operations/test_file_operations.py
```

## 环境说明

| 环境 | Python版本 | 用途 | 位置 |
|------|-----------|------|------|
| 项目主环境 | 3.13.5 | 实际运行项目 | `venv/` |
| 测试环境 | 3.12 | 运行测试套件 | `venv-test/` |

## 注意事项

1. **不要混淆两个环境**：
   - `venv/` 用于生产环境
   - `venv-test/` 仅用于测试

2. **测试环境独立性**：
   - 测试环境有自己的依赖副本
   - 修改测试环境不会影响项目主环境

3. **版本兼容性**：
   - Python 3.12 对大多数包的支持更成熟
   - 避免了Python 3.13的新特性可能带来的兼容性问题

4. **CI/CD建议**：
   - 在CI环境中也使用Python 3.12
   - 确保测试环境与CI环境一致

## 故障排除

### 问题1：Python版本检测失败
```bash
# 检查Python路径
where python

# 如果有多个Python版本，确保3.12在PATH前面
# 或者使用完整路径
C:\Python312\python.exe --version
```

### 问题2：依赖安装失败
```bash
# 清除缓存重新安装
pip cache purge
pip install --no-cache-dir -r requirements.txt

# 使用国内源
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

### 问题3：测试运行失败
```bash
# 检查测试环境是否正确激活
venv-test\Scripts\activate
python --version  # 应该是3.12.x

# 检查依赖是否完整
python -c "import app.main; print('项目模块导入成功')"
```

## 迁移说明

如果之前使用过测试环境的旧版本：

1. 备份重要数据（如测试数据库）
2. 删除旧的测试虚拟环境：`rmdir /s venv-test`
3. 重新运行设置脚本：`scripts\test\setup_python312_env.bat`
4. 重新配置测试数据库（如需要）

这样就能确保测试环境使用稳定的Python 3.12版本，避免兼容性问题。
