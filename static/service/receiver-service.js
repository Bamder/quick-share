/**
 * Receiver服务 - 接收方服务
 * 使用服务器中转模式，支持端到端加密
 */

import { formatFileSize, reconstructFileFromChunks } from '../utils/file-utils.js';
import { 
  decryptChunk,
  decryptKeyWithPickupCode,
  extractLookupCode
} from '../utils/encryption-utils.js';
import { getAuthHeaders } from '../utils/api-client.js';

class ReceiverService {
  constructor() {
    // 服务器中转相关
    this.pickupCode = null;               // 十二位取件码（前6位查找码+后6位密钥码）
    this.apiBase = '';                    // API服务器基础URL
    this.encryptionKey = null;             // 文件加密密钥（原始密钥，用于解密文件块，不是密钥码）
    this.fileInfo = null;                 // 文件元信息
    this.sessionId = null;                // 下载会话ID（从获取加密密钥接口返回）
    
    // 回调函数
    this.onProgress = null;               // 下载进度
    this.onComplete = null;               // 下载完成
    this.onError = null;                  // 错误
    
    // 文件传输相关
    this.receivedChunks = [];             // 已接收的分片列表
    this.isDownloading = false;          // 是否正在下载中
  }

  /**
   * 初始化配置
   * @param {string} apiBase - API基础URL
   * @param {Object} callbacks - 回调函数对象
   */
  init(apiBase, callbacks = {}) {
    this.apiBase = apiBase;
    this.onProgress = callbacks.onProgress || null;
    this.onComplete = callbacks.onComplete || null;
    this.onError = callbacks.onError || null;
  }
  
  /**
   * 通过服务器中转下载文件（使用端到端解密）
   * @param {string} pickupCode - 取件码（用于解密文件加密密钥）
   * @returns {Promise<Blob>} 解密后的文件Blob
   */
  async downloadFileViaRelay(pickupCode) {
    if (!this.apiBase) {
      throw new Error('API基础URL未设置，请先调用init()方法');
    }

    if (!pickupCode || !/^[A-Z0-9]{12}$/.test(pickupCode)) {
      throw new Error('无效的取件码，必须是12位大写字母或数字');
    }

    if (this.isDownloading) {
      throw new Error('文件正在下载中，请等待完成');
    }

    // 保存完整的12位取件码（用于解密）
    this.pickupCode = pickupCode.toUpperCase();
    
    // 提取前6位查找码（只发送查找码到服务器，不暴露后6位密钥码）
    this.lookupCode = extractLookupCode(this.pickupCode);
    
    this.isDownloading = true;
    this.receivedChunks = [];

    try {
      // 1. 从服务器获取加密后的文件加密密钥（带重试机制）
      // 注意：这是用取件码的密钥码派生密钥加密后的文件加密密钥，不是密钥码本身
      console.log('[Receiver] 从服务器获取加密后的文件加密密钥...');
      const encryptedKey = await this.getEncryptedKeyWithRetry();
      
      // 2. 使用取件码的密钥码（后6位）派生密钥，解密文件加密密钥（原始密钥）
      console.log('[Receiver] 使用取件码的密钥码派生密钥，解密文件加密密钥（原始密钥）...');
      this.encryptionKey = await decryptKeyWithPickupCode(encryptedKey, this.pickupCode);
      console.log('[Receiver] ✓ 文件加密密钥（原始密钥）已解密，可用于解密文件块');

      // 2. 获取文件信息
      console.log('[Receiver] 获取文件信息...');
      const fileInfo = await this.getFileInfo();
      this.fileInfo = fileInfo;
      console.log('[Receiver] ✓ 文件信息:', {
        fileName: fileInfo.fileName,
        fileSize: fileInfo.fileSize,
        totalChunks: fileInfo.totalChunks
      });

      // 3. 初始化接收数组
      this.receivedChunks = new Array(fileInfo.totalChunks);

      // 3.5. 连接建立完成，通知前端关闭连接遮罩
      // 此时进度为0，但连接已建立，可以开始下载
      if (this.onProgress) {
        this.onProgress(0, 0, fileInfo.totalChunks, null); // 传递null表示连接完成，开始下载
      }

      // 4. 批量下载所有加密块（优化性能）
      console.log('[Receiver] 开始批量下载加密文件块...');
      const batchSize = 25; // 每批下载25个块（根据64KB块大小优化）
      const allChunkIndices = Array.from({ length: fileInfo.totalChunks }, (_, i) => i);
      
      // 分批下载
      for (let i = 0; i < allChunkIndices.length; i += batchSize) {
        const batchIndices = allChunkIndices.slice(i, i + batchSize);
        await this.downloadChunksBatch(batchIndices);
        
        // 更新进度
        const downloadedCount = Math.min(i + batchSize, fileInfo.totalChunks);
        const progress = (downloadedCount / fileInfo.totalChunks) * 100;
        if (this.onProgress) {
          this.onProgress(progress, downloadedCount, fileInfo.totalChunks, null);
        }
      }
      console.log('[Receiver] ✓ 所有文件块下载完成');

      // 5. 解密并重组文件
      console.log('[Receiver] 解密并重组文件...');
      console.log('[Receiver] 加密密钥状态:', this.encryptionKey ? '已设置' : '未设置');
      console.log('[Receiver] 接收到的块数量:', this.receivedChunks.length);
      console.log('[Receiver] 接收到的块详情:', this.receivedChunks.map((chunk, idx) => ({
        index: idx,
        exists: !!chunk,
        size: chunk ? chunk.size : 0,
        type: chunk ? chunk.constructor.name : 'null'
      })));
      
      const decryptedChunks = await Promise.all(
        this.receivedChunks.map((encryptedChunk, index) => {
          if (!encryptedChunk) {
            throw new Error(`块 ${index} 缺失`);
          }
          console.log(`[Receiver] 开始解密块 ${index}...`);
          return decryptChunk(encryptedChunk, this.encryptionKey).then(decrypted => {
            console.log(`[Receiver] ✓ 块 ${index} 解密成功`);
            return decrypted;
          }).catch(error => {
            console.error(`[Receiver] ✗ 块 ${index} 解密失败:`, error);
            throw error;
          });
        })
      );

      const fileBlob = reconstructFileFromChunks(
        decryptedChunks,
        fileInfo.fileName,
        fileInfo.mimeType
      );
      console.log('[Receiver] ✓ 文件解密和重组完成');

      // 6. 通知服务器下载完成
      await this.notifyDownloadComplete();

      if (this.onComplete) {
        this.onComplete(fileBlob);
      }

      this.isDownloading = false;
      return fileBlob;
    } catch (error) {
      this.isDownloading = false;
      console.error('[Receiver] 下载文件失败:', error);
      if (this.onError) {
        this.onError(error);
      }
      throw error;
    }
  }

  /**
   * 从服务器获取加密后的文件加密密钥（带重试机制）
   * 
   * 注意：这是用取件码的密钥码派生密钥加密后的文件加密密钥（原始密钥）
   * 不是密钥码本身，也不是未加密的文件加密密钥
   * 
   * 如果密钥尚未上传完成，会等待并重试
   * 
   * @param {number} maxRetries - 最大重试次数（默认30次，约30秒）
   * @param {number} retryInterval - 重试间隔（毫秒，默认1000ms）
   * @returns {Promise<string>} 加密后的文件加密密钥（Base64编码）
   */
  async getEncryptedKeyWithRetry(maxRetries = 30, retryInterval = 1000) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        const encryptedKey = await this.getEncryptedKey();
        if (attempt > 1) {
          console.log(`[Receiver] ✓ 加密密钥已可用（第 ${attempt} 次尝试）`);
        }
        return encryptedKey;
      } catch (error) {
        // 如果是"加密密钥不存在"错误，继续重试
        if (error.message && error.message.includes('加密密钥不存在')) {
          if (attempt < maxRetries) {
            console.log(`[Receiver] 等待加密密钥上传完成... (${attempt}/${maxRetries})`);
            // 通知进度回调（如果有）
            if (this.onProgress) {
              this.onProgress(0, 0, 0, `等待上传完成... (${attempt}/${maxRetries})`);
            }
            await new Promise(resolve => setTimeout(resolve, retryInterval));
            continue;
          } else {
            throw new Error('等待加密密钥超时，发送方可能尚未完成上传');
          }
        } else {
          // 其他错误直接抛出
          throw error;
        }
      }
    }
    throw new Error('获取加密密钥失败：超过最大重试次数');
  }

  /**
   * 从服务器获取加密后的文件加密密钥
   * 
   * 注意：这是用取件码的密钥码派生密钥加密后的文件加密密钥（原始密钥）
   * 
   * @returns {Promise<string>} 加密后的文件加密密钥（Base64编码）
   */
  async getEncryptedKey() {
    const response = await fetch(
      `${this.apiBase}/relay/codes/${this.lookupCode}/encrypted-key`,
      {
        headers: getAuthHeaders()
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.msg || `获取加密密钥失败: HTTP ${response.status}`);
    }

    const result = await response.json();
    if (result.code !== 200 || !result.data || !result.data.encryptedKey) {
      throw new Error(result.msg || '获取加密密钥失败');
    }

    const encryptedKey = result.data.encryptedKey;
    console.log('[Receiver] 获取到的加密密钥长度:', encryptedKey ? encryptedKey.length : 0);
    console.log('[Receiver] 加密密钥前50个字符:', encryptedKey ? encryptedKey.substring(0, 50) : 'null');

    // 保存会话ID（如果返回了）
    if (result.data.sessionId) {
      this.sessionId = result.data.sessionId;
      console.log('[Receiver] 下载会话ID已保存:', this.sessionId);
    }

    return encryptedKey;
  }

  /**
   * 获取文件信息
   * @returns {Promise<Object>} 文件信息
   */
  async getFileInfo() {
    const response = await fetch(
      `${this.apiBase}/relay/codes/${this.lookupCode}/file-info`,
      {
        headers: getAuthHeaders()
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.msg || `获取文件信息失败: HTTP ${response.status}`);
    }

    const result = await response.json();
    if (result.code !== 200 || !result.data) {
      throw new Error(result.msg || '获取文件信息失败');
    }

    return {
      fileName: result.data.fileName,
      fileSize: result.data.fileSize,
      mimeType: result.data.mimeType,
      totalChunks: result.data.totalChunks
    };
  }

  /**
   * 批量下载加密块（优化性能）
   * @param {Array<number>} chunkIndices - 块索引数组
   * @returns {Promise<void>}
   */
  async downloadChunksBatch(chunkIndices) {
    const requestBody = {
      chunkIndices: chunkIndices
    };
    if (this.sessionId) {
      requestBody.sessionId = this.sessionId;
    }
    
    console.log(`[Receiver] 批量下载块: [${chunkIndices.join(', ')}]`);
    const response = await fetch(
      `${this.apiBase}/relay/codes/${this.lookupCode}/download-chunks`,
      {
        method: 'POST',
        headers: getAuthHeaders({
          'Content-Type': 'application/json'
        }),
        body: JSON.stringify(requestBody)
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.msg || `批量下载块失败: HTTP ${response.status}`);
    }

    const result = await response.json();
    if (result.code !== 200 || !result.data) {
      throw new Error(result.msg || '批量下载块失败');
    }

    const { chunks, missing, expired } = result.data;
    
    // 处理缺失的块
    if (missing && missing.length > 0) {
      console.warn(`[Receiver] ⚠️ 缺失的块: [${missing.join(', ')}]`);
      // 尝试单独下载缺失的块
      for (const missingIndex of missing) {
        try {
          await this.downloadChunk(missingIndex);
        } catch (error) {
          console.error(`[Receiver] ✗ 下载缺失块 ${missingIndex} 失败:`, error);
          throw new Error(`块 ${missingIndex} 不存在或已过期`);
        }
      }
    }
    
    // 处理过期的块
    if (expired && expired.length > 0) {
      console.warn(`[Receiver] ⚠️ 过期的块: [${expired.join(', ')}]`);
      throw new Error(`块 [${expired.join(', ')}] 已过期`);
    }
    
    // 解码并存储块数据
    for (const [indexStr, chunkData] of Object.entries(chunks)) {
      const chunkIndex = parseInt(indexStr);
      try {
        // 解码 base64 数据
        const base64Data = chunkData.data;
        const binaryString = atob(base64Data);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }
        const blob = new Blob([bytes], { type: 'application/octet-stream' });
        
        // 存储块
        this.receivedChunks[chunkIndex] = blob;
        console.log(`[Receiver] ✓ 块 ${chunkIndex} 下载成功`);
      } catch (error) {
        console.error(`[Receiver] ✗ 处理块 ${chunkIndex} 失败:`, error);
        throw new Error(`处理块 ${chunkIndex} 失败: ${error.message}`);
      }
    }
  }

  /**
   * 下载单个加密块（用于补充缺失的块）
   * @param {number} chunkIndex - 块索引
   * @returns {Promise<void>}
   */
  async downloadChunk(chunkIndex) {
    // 如果有会话ID，在URL参数中传递
    let url = `${this.apiBase}/relay/codes/${this.lookupCode}/download-chunk/${chunkIndex}`;
    if (this.sessionId) {
      url += `?session_id=${encodeURIComponent(this.sessionId)}`;
    }
    
    console.log(`[Receiver] 下载块 ${chunkIndex}...`);
    const response = await fetch(url, {
      headers: getAuthHeaders()
    });

    console.log(`[Receiver] 块 ${chunkIndex} 响应状态: ${response.status} ${response.statusText}`);
    console.log(`[Receiver] 块 ${chunkIndex} Content-Type: ${response.headers.get('content-type')}`);

    if (!response.ok) {
      // 尝试解析错误响应
      const contentType = response.headers.get('content-type') || '';
      let errorData = {};
      if (contentType.includes('application/json')) {
        errorData = await response.json().catch(() => ({}));
      } else {
        // 如果不是 JSON，尝试读取文本
        const errorText = await response.text().catch(() => '');
        console.error(`[Receiver] 块 ${chunkIndex} 错误响应:`, errorText);
      }
      throw new Error(errorData.msg || `下载块 ${chunkIndex} 失败: HTTP ${response.status}`);
    }

    // 检查 Content-Type，确保是二进制数据而不是 JSON
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      // 如果返回的是 JSON，说明是错误响应
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.msg || `下载块 ${chunkIndex} 失败: 服务器返回了 JSON 错误响应`);
    }

    // 读取加密块
    const encryptedChunk = await response.blob();
    console.log(`[Receiver] 块 ${chunkIndex} 下载成功，大小: ${encryptedChunk.size} 字节`);
    
    // 检查块大小是否合理（至少应该有12字节IV + 一些加密数据）
    if (encryptedChunk.size < 12) {
      // 可能是错误响应，尝试读取为文本
      const text = await encryptedChunk.text();
      console.error(`[Receiver] 块 ${chunkIndex} 数据异常，可能是错误响应:`, text.substring(0, 100));
      throw new Error(`下载块 ${chunkIndex} 失败: 数据异常（大小: ${encryptedChunk.size} 字节）`);
    }
    
    this.receivedChunks[chunkIndex] = encryptedChunk;

    // 更新进度（确保进度值有效）
    const receivedCount = this.receivedChunks.filter(chunk => chunk !== undefined && chunk !== null).length;
    const totalChunks = this.receivedChunks.length;
    const progress = totalChunks > 0 ? (receivedCount / totalChunks) * 100 : 0;
    
    // 调用进度回调（不传递message，表示正常下载进度）
    if (this.onProgress) {
      this.onProgress(progress, receivedCount, totalChunks, null);
    }

    console.log(`[Receiver] ✓ 块 ${chunkIndex + 1}/${totalChunks} 下载成功 (${progress.toFixed(1)}%)`);
  }

  /**
   * 通知服务器下载完成
   * 此接口会自动增加使用次数，并在达到上限时更新状态为completed
   * @returns {Promise<void>}
   */
  async notifyDownloadComplete() {
    try {
      const requestBody = {};
      if (this.sessionId) {
        requestBody.session_id = this.sessionId;
      }
      
      const response = await fetch(
        `${this.apiBase}/relay/codes/${this.lookupCode}/download-complete`,
        {
          method: 'POST',
          headers: getAuthHeaders({
            'Content-Type': 'application/json'
          }),
          body: JSON.stringify(requestBody)
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        // 如果是因为达到上限，记录日志但不抛出错误（文件已下载完成）
        if (errorData.data && errorData.data.code === 'LIMIT_REACHED') {
          console.log('[Receiver] ⚠️ 取件码已达到使用上限:', errorData.data);
        } else {
          throw new Error(errorData.msg || `通知下载完成失败: HTTP ${response.status}`);
        }
      } else {
        const result = await response.json();
        if (result.data) {
          console.log('[Receiver] ✓ 下载完成，使用次数已更新:', {
            usedCount: result.data.usedCount,
            limitCount: result.data.limitCount,
            remaining: result.data.remaining,
            status: result.data.status
          });
        }
      }
    } catch (error) {
      console.warn('[Receiver] 通知下载完成失败:', error);
      // 不抛出错误，因为文件已经下载完成
    }
  }

}

// 导出单例实例
export const receiverService = new ReceiverService();

