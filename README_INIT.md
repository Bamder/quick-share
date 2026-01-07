# Quick Share 初始化指南

## 4步完成初始化

### 1️⃣ 安装依赖
运行：`scripts\setup\install_dependencies\install_dependencies.bat`

### 2️⃣ 配置环境
创建 `.env` 文件并填写：
```bash
# 数据库配置（必需）
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的密码
DB_NAME=quick_share_datagrip

# 去重指纹哈希盐（必需，生产环境必须设置随机值至少）
DEDUPE_PEPPER=你的随机盐值

# Redis配置（可选）
REDIS_ENABLED=true
REDIS_PASSWORD=你的Redis密码
```

### 3️⃣ 准备服务
```bash
# 安装Redis
scripts\setup\install_wsl2_redis\install_wsl2_redis.bat

# 初始化数据库
scripts\setup\migrate_database\migrate_database.bat
```

### 4️⃣ 启动应用
```bash
# 启动服务（会自动检查并启动Redis）
scripts\run\start_server.py
```

## ✅ 验证成功

浏览器访问：http://localhost:8000 或 https://localhost:8000
看到"Quick Share"页面即成功！

## 🔒 SSL证书说明

- **开发环境**：运行`scripts\setup\generate_ssl_cert\generate_ssl_cert.bat`生成自签名证书，支持HTTPS但浏览器显示"不安全"警告，点击"继续访问"即可
- **生产环境**：部署前需配置正式SSL证书（如Let's Encrypt），确保用户数据传输安全

## ⚠️ 注意

- 数据库脚本需要输入MySQL账号密码
- Redis安装需要管理员权限
- 确保MySQL服务已启动
