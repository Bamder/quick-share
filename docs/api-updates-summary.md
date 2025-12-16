# API文档更新总结

## 更新日期
2024年（根据实现逻辑更新）

## 更新内容

### 1. 角色定义统一 ✅

**更新前：**
- API文档描述：分享方创建offer，下载方获取offer
- 实现：Receiver创建offer，Sender获取offer

**更新后：**
- 统一为：**Receiver（接收方）创建offer，Sender（发送方）获取offer并创建answer**
- 所有接口描述已更新以匹配实现

### 2. 新增Sender注册接口 ✅

**接口：** `POST /api/codes/{code}/webrtc/sender/register`

**功能：**
- Sender向信令服务器注册，等待Receiver的Offer
- 信令服务器临时存储Sender信息
- 当Receiver创建Offer时，服务器会将Offer转发给已注册的Sender

**请求体：**
```json
{
  "senderInfo": {
    "userAgent": "...",
    "ipAddress": "..."
  },
  "callbackUrl": "..." // 可选
}
```

**响应：**
```json
{
  "code": 201,
  "msg": "Sender注册成功，等待Offer",
  "data": {
    "registeredAt": "2023-12-01T10:00:00.000Z",
    "expiresIn": 300
  }
}
```

### 3. 更新Offer创建接口 ✅

**接口：** `POST /api/codes/{code}/webrtc/offer`

**更新内容：**
- 明确说明是Receiver创建Offer
- 添加了Offer转发逻辑：当Receiver创建Offer时，如果存在已注册的Sender，服务器会立即将Offer转发给Sender
- 响应中添加了 `senderFound` 和 `forwarded` 字段

**响应示例：**
```json
{
  "code": 201,
  "msg": "WebRTC Offer创建成功",
  "data": {
    "sessionId": "sess_abc123",
    "expiresIn": 300,
    "senderFound": true,
    "forwarded": true
  }
}
```

### 4. 更新Offer获取接口 ✅

**接口：** `GET /api/codes/{code}/webrtc/offer/{session_id}`

**更新内容：**
- 明确说明是Sender获取Receiver创建的Offer
- 添加了说明：如果Sender已注册，服务器会立即将Offer推送给Sender（通过注册时的回调或WebSocket）

### 5. 新增Answer获取接口 ✅

**接口：** `GET /api/codes/{code}/webrtc/answer/{session_id}`

**功能：**
- Receiver通过此接口获取Sender创建的Answer
- Receiver通过轮询此接口来获取Answer

**响应示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "answer": "v=0\r\no=- 654321 2 IN IP4 127.0.0.1...",
    "createdAt": "2023-12-01T10:00:05.000Z",
    "status": "answer_received"
  }
}
```

**404响应（Answer未创建）：**
```json
{
  "code": 404,
  "msg": "WebRTC Answer不存在或未创建",
  "data": {
    "status": "offer_created",
    "message": "等待Sender创建Answer"
  }
}
```

### 6. 更新Answer提交接口 ✅

**接口：** `POST /api/codes/{code}/webrtc/answer`

**更新内容：**
- 明确说明是Sender提交Answer
- 添加了说明：服务器保存Answer后，Receiver可以通过Answer获取接口获取Answer

### 7. Schema更新 ✅

**新增：**
- `SenderRegisterRequest` - Sender注册请求Schema

**修改：**
- `WebRTCOfferRequest` - 将 `senderInfo` 改为 `receiverInfo`（因为Receiver创建offer）

## 客户端代码更新

### receiver-service.js
- ✅ 更新了 `waitForAnswer()` 方法，使用新的Answer获取接口
- ✅ 更新了 `sendOfferToServer()` 方法，使用 `receiverInfo` 字段

### sender-service.js
- ✅ 新增了 `registerSender()` 方法，用于注册Sender
- ✅ 新增了 `waitForOffer()` 方法，用于等待并获取Offer
- ✅ 更新了 `receiveOfferAndCreateAnswer()` 方法，支持直接传入offer对象

## 工作流程

### 完整流程

1. **Sender注册**
   ```
   Sender → POST /api/codes/{code}/webrtc/sender/register
   ```

2. **Receiver创建Offer**
   ```
   Receiver → POST /api/codes/{code}/webrtc/offer
   ```
   - 服务器查找已注册的Sender
   - 如果找到，立即将Offer转发给Sender

3. **Sender获取Offer**
   ```
   Sender → GET /api/codes/{code}/webrtc/offer/{session_id}
   ```
   - 如果已转发，立即返回Offer
   - 否则，Sender轮询等待

4. **Sender创建并提交Answer**
   ```
   Sender → POST /api/codes/{code}/webrtc/answer
   ```

5. **Receiver获取Answer**
   ```
   Receiver → GET /api/codes/{code}/webrtc/answer/{session_id}
   ```
   - Receiver轮询此接口获取Answer

6. **建立WebRTC连接**
   - 双方完成SDP交换后，建立P2P连接
   - Sender创建数据通道，开始传输文件

## 注意事项

1. **SessionId获取**
   - SessionId由Receiver创建Offer时生成
   - Sender需要知道SessionId才能获取Offer
   - 建议：Receiver创建Offer后，通过其他渠道（如WebSocket、回调URL）通知Sender

2. **轮询机制**
   - 当前使用HTTP轮询方式
   - 建议未来考虑使用WebSocket实现实时推送

3. **临时存储**
   - Sender注册信息存储在服务器内存或Redis中
   - 需要设置合理的过期时间（建议5分钟）

4. **错误处理**
   - 所有接口都包含完整的错误响应
   - 客户端应实现重试和错误处理机制

## 后续优化建议

1. **WebSocket支持**
   - 实现WebSocket信令通道，替代HTTP轮询
   - 提高实时性和效率

2. **Session列表接口**
   - 考虑添加 `GET /api/codes/{code}/webrtc/sessions` 接口
   - 方便查询所有活跃会话

3. **ICE候选处理**
   - 明确ICE候选的发送机制
   - 考虑单独发送ICE候选以提高连接成功率

