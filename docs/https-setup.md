# HTTPS 配置指南

## 问题说明

当使用IP地址通过HTTP访问时，浏览器的Web Crypto API（用于加密功能）会被阻止，因为Web Crypto API要求安全上下文（Secure Context），即必须使用HTTPS或localhost。

## 解决方案：配置HTTPS（使用自签名证书）

### 快速开始

1. **生成SSL证书**
   ```bash
   scripts\setup\generate_ssl_cert\generate_ssl_cert.bat
   ```

2. **启动服务器**
   ```bash
   start_server.bat
   ```
   服务器会自动检测证书并使用HTTPS模式

3. **访问系统**
   - 使用HTTPS访问：`https://[您的IP]:8000`
   - 浏览器会显示安全警告（自签名证书是正常的）
   - 点击"高级" -> "继续访问"（不安全网站）即可

---

## 详细步骤

### 步骤1：生成SSL证书

运行证书生成脚本：
```bash
scripts\setup\generate_ssl_cert\generate_ssl_cert.bat
```

脚本会：
- 自动检测您的本地IP地址
- 生成自签名SSL证书（包含IP、localhost、127.0.0.1）
- 将证书保存到 `certs/` 目录

**证书文件：**
- `certs/server.crt` - 证书文件
- `certs/server.key` - 私钥文件

### 步骤2：启动HTTPS服务器

运行启动脚本：
```bash
start_server.bat
```

如果检测到证书文件，服务器会自动使用HTTPS模式：
```
🔒 检测到SSL证书，将使用HTTPS模式
   证书: D:\...\certs\server.crt
   私钥: D:\...\certs\server.key
```

### 步骤3：访问系统

**本地访问：**
- HTTPS: `https://localhost:8000`
- HTTPS: `https://127.0.0.1:8000`

**其他机器访问：**
- HTTPS: `https://[服务器IP]:8000`
  - 例如：`https://192.168.1.100:8000`

**浏览器安全警告：**
- 由于是自签名证书，浏览器会显示"不安全"警告
- 这是正常的，点击"高级" -> "继续访问"（或"继续前往"）
- 仅用于开发环境，生产环境应使用正式证书

---

## 证书说明

### 自签名证书的特点

- ✅ 支持HTTPS加密传输
- ✅ 满足Web Crypto API的安全上下文要求
- ✅ 可以使用IP地址访问
- ⚠️ 浏览器会显示安全警告（正常现象）
- ⚠️ 仅用于开发环境

### 证书包含的域名/IP

生成的证书包含以下域名和IP：
- 您的本地IP地址（如果选择添加）
- `localhost`
- `127.0.0.1`

### 证书有效期

- 默认有效期：365天
- 过期后需要重新生成

---

## 故障排除

### 问题1：证书生成失败

**错误：** `未找到 cryptography 库`

**解决：**
```bash
pip install cryptography
```

### 问题2：服务器启动失败

**错误：** `SSL证书加载失败`

**检查：**
1. 确认 `certs/server.crt` 和 `certs/server.key` 文件存在
2. 重新运行证书生成脚本

### 问题3：浏览器无法访问

**症状：** 连接被拒绝或超时

**检查：**
1. 确认服务器已启动并显示"使用HTTPS模式"
2. 确认使用的是 `https://` 而不是 `http://`
3. 检查防火墙是否允许端口8000
4. 运行 `configure-firewall.bat` 配置防火墙

### 问题4：其他机器无法访问

**症状：** 可以本地访问，但其他机器无法访问

**检查：**
1. 确认使用服务器的实际IP地址（不是localhost）
2. 确认证书包含了服务器的IP地址
3. 如果IP地址变更，需要重新生成证书
4. 检查防火墙设置

---

## 使用场景

### 场景1：本地开发（单机）

**推荐：** 使用 `http://localhost:8000`
- 不需要证书
- Web Crypto API 在localhost上可用
- 最简单的方式

### 场景2：局域网内多机器访问（使用IP）

**推荐：** 使用HTTPS + 自签名证书
- 运行 `generate_ssl_cert.bat` 生成证书
- 使用 `https://[IP]:8000` 访问
- 支持加密功能

### 场景3：公网访问

**推荐：** 使用ngrok（自动提供HTTPS）
- 运行 `setup-ngrok-tunnel.bat`
- ngrok 提供HTTPS隧道
- 无需配置证书

---

## 重新生成证书

如果需要重新生成证书（例如IP地址变更）：

1. 删除旧证书（可选）
   ```bash
   del certs\server.crt
   del certs\server.key
   ```

2. 运行生成脚本
   ```bash
   scripts\setup\generate_ssl_cert\generate_ssl_cert.bat
   ```

3. 重启服务器

---

## 安全说明

⚠️ **重要：**

- 自签名证书仅用于开发环境
- 生产环境应使用正式的SSL证书（例如Let's Encrypt）
- 不要将私钥文件（`server.key`）提交到版本控制系统
- 证书文件已添加到 `.gitignore`

---

## 技术细节

### Web Crypto API 安全上下文要求

Web Crypto API 的 `crypto.subtle` 只能在安全上下文中使用：

**安全上下文包括：**
- HTTPS 协议（任何域名/IP）
- HTTP + localhost
- HTTP + 127.0.0.1

**非安全上下文：**
- HTTP + IP地址（例如：`http://192.168.1.100:8000`）
- HTTP + 域名（非localhost）

### 为什么需要安全上下文？

这是浏览器的安全策略，确保加密功能只在安全的环境中使用，防止中间人攻击。

