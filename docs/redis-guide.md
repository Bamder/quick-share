# WSL2 和 Redis 安装脚本

此目录包含用于在 Windows 上通过 WSL2 安装和配置 Redis 的自动化脚本。

## 文件说明

### ⭐ 用户入口脚本（直接运行）
- **`install_wsl2_redis.bat`** - Windows 批处理脚本，**这是用户应该运行的入口脚本**
  - 检查并安装 WSL2（如果未安装）
  - 在 WSL2 中安装和配置 Redis
  - 自动调用 `wsl_install_redis.sh`

### 内部脚本（自动调用，无需手动运行）
- `wsl_install_redis.sh` - WSL2 中的 Bash 脚本，由 `install_wsl2_redis.bat` 自动调用
  - 在 WSL2 环境中安装和配置 Redis
  - **用户不应直接运行此脚本**

### 辅助脚本
- `start_redis.bat` - 启动 Redis 服务
- `stop_redis.bat` - 停止 Redis 服务
- `test_redis_connection.bat` - 测试 Redis 连接（命令行）
- `test_redis_connection.py` - 测试 Redis 连接（Python）

## 使用方法

### 方法 1: 直接运行（推荐）

1. **以管理员身份运行** `install_wsl2_redis.bat` ⭐ **（这是入口脚本）**
   - 右键点击脚本
   - 选择"以管理员身份运行"
   - 注意：此脚本会自动调用 `wsl_install_redis.sh`，无需手动运行

2. 按照提示完成安装：
   - 如果 WSL2 未安装，脚本会自动安装并提示重启
   - 重启后再次运行脚本，完成 Redis 安装

### 方法 2: 手动步骤

如果自动脚本遇到问题，可以手动执行：

#### 步骤 1: 安装 WSL2

```powershell
# 以管理员身份运行 PowerShell
wsl --install
# 或
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

重启计算机后：

```powershell
wsl --set-default-version 2
wsl --install -d Ubuntu
```

#### 步骤 2: 在 WSL2 中安装 Redis

```bash
# 在 WSL2 中运行
sudo apt-get update
sudo apt-get install -y redis-server
sudo service redis-server start
sudo systemctl enable redis-server
redis-cli ping  # 应该返回 PONG
```

## 配置说明

### Redis 配置

Redis 安装后会自动配置为：
- **监听地址**: `127.0.0.1`（仅本地访问）
- **端口**: `6379`（默认端口）
- **密码**: 无（仅本地访问，安全）
- **持久化**: 启用 RDB 快照
- **最大内存**: 256MB（可根据需要调整）

### 配置文件位置

- WSL2 中: `/etc/redis/redis.conf`
- 备份文件: `/etc/redis/redis.conf.backup.YYYYMMDD_HHMMSS`

### 修改配置

如果需要修改 Redis 配置：

```bash
# 在 WSL2 中编辑配置文件
wsl sudo nano /etc/redis/redis.conf

# 修改后重启服务
wsl sudo service redis-server restart
```

## 从 Windows 访问 Redis

### 使用 Python 连接

```python
import redis

# 连接到 Redis（通过 WSL2）
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# 测试连接
r.ping()  # 应该返回 True
```

### 使用命令行工具

```powershell
# 在 WSL2 中运行 redis-cli
wsl redis-cli ping

# 进入交互式 CLI
wsl redis-cli
```

## 常用命令

### 服务管理

```powershell
# 启动 Redis 服务
wsl sudo service redis-server start

# 停止 Redis 服务
wsl sudo service redis-server stop

# 重启 Redis 服务
wsl sudo service redis-server restart

# 查看服务状态
wsl sudo service redis-server status
```

### 测试连接

```powershell
# 测试连接
wsl redis-cli ping

# 应该返回: PONG
```

### 查看信息

```powershell
# 进入 Redis CLI
wsl redis-cli

# 在 CLI 中执行：
# INFO          # 查看服务器信息
# CONFIG GET *  # 查看所有配置
# DBSIZE        # 查看数据库大小
# KEYS *        # 查看所有键（谨慎使用，可能很慢）
```

## 故障排除

### 问题 1: WSL2 安装失败

**症状**: 提示需要重启或安装失败

**解决方案**:
1. 确保已启用虚拟化（在 BIOS 中）
2. 确保 Windows 版本支持 WSL2（Windows 10 版本 2004 或更高）
3. 手动下载并安装 WSL2 内核更新: https://aka.ms/wsl2kernel

### 问题 2: Redis 服务无法启动

**症状**: `sudo service redis-server start` 失败

**解决方案**:
```bash
# 查看错误日志
wsl sudo tail -f /var/log/redis/redis-server.log

# 检查配置文件语法
wsl sudo redis-server /etc/redis/redis.conf --test-memory 1

# 检查端口是否被占用
wsl sudo netstat -tlnp | grep 6379
```

### 问题 3: 无法从 Windows 连接 Redis

**症状**: Python 连接 Redis 失败

**解决方案**:
1. 确保 Redis 服务正在运行: `wsl sudo service redis-server status`
2. 检查 Redis 配置中的 `bind` 设置: `wsl sudo grep "^bind" /etc/redis/redis.conf`
3. 确保 `protected-mode` 设置为 `no`（仅本地访问时）
4. 检查防火墙设置（WSL2 通常不需要额外配置）

### 问题 4: Redis 内存不足

**症状**: Redis 报错或性能下降

**解决方案**:
```bash
# 编辑配置文件，增加最大内存
wsl sudo nano /etc/redis/redis.conf

# 修改 maxmemory 设置（例如改为 512mb）
# maxmemory 512mb
# maxmemory-policy allkeys-lru

# 重启服务
wsl sudo service redis-server restart
```

## 安全建议

1. **生产环境**: 如果 Redis 需要从外部访问，请设置密码：
   ```bash
   # 在 redis.conf 中设置
   requirepass your_strong_password
   ```

2. **防火墙**: 确保防火墙规则正确配置，只允许必要的访问

3. **定期备份**: Redis 数据会持久化到磁盘，但建议定期备份 RDB 文件

## 卸载

如果需要卸载 Redis：

```bash
# 在 WSL2 中运行
wsl sudo service redis-server stop
wsl sudo apt-get remove --purge redis-server
wsl sudo apt-get autoremove
```

## 相关资源

- [WSL2 官方文档](https://docs.microsoft.com/zh-cn/windows/wsl/)
- [Redis 官方文档](https://redis.io/documentation)
- [Redis Python 客户端](https://redis-py.readthedocs.io/)

