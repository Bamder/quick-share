/**
 * Sender服务 - 发送方服务
 * 使用服务器中转模式，支持端到端加密
 */

import { splitFileIntoChunks } from '../utils/file-utils.js';
import { generateSessionId } from '../utils/common-utils.js';
import { 
  generateEncryptionKey, 
  exportKeyToBase64, 
  encryptChunk, 
  calculateChunkHash,
  encryptKeyWithPickupCode
} from '../utils/encryption-utils.js';

class SenderService {
  constructor() {
    // 服务器中转相关
    this.pickupCode = null;              // 十二位取件码（前6位查找码+后6位密钥码）
    this.apiBase = '';                   // API服务器基础URL
    this.encryptionKey = null;           // 加密密钥（客户端生成）
    this.encryptionKeyBase64 = null;     // 加密密钥Base64（已废弃，不再使用）
    
    // 回调函数
    this.onProgress = null;              // 发送进度
    this.onComplete = null;              // 发送完成
    this.onError = null;                 // 错误
    
    // 文件传输相关
    this.currentFile = null;             // 当前待发送文件
    this.fileChunks = [];                // 分片后的文件块列表
    this.currentChunkIndex = 0;          // 已发送分片索引
    this.isSending = false;              // 是否正在发送中
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

  // ========== 服务器中转模式 ==========
  
  /**
   * 通过服务器中转上传文件（使用端到端加密）
   * @param {string} pickupCode - 取件码
   * @param {File} file - 要上传的文件
   * @returns {Promise<string>} 返回加密密钥的Base64（用于分享给接收者）
   */
  async uploadFileViaRelay(pickupCode, file) {
    if (!this.apiBase) {
      throw new Error('API基础URL未设置，请先调用init()方法');
    }

    if (!pickupCode || !/^[A-Z0-9]{12}$/.test(pickupCode)) {
      throw new Error('无效的取件码，必须是12位大写字母或数字');
    }

    if (!file) {
      throw new Error('文件不能为空');
    }

    if (this.isSending) {
      throw new Error('文件正在上传中，请等待完成');
    }

    this.pickupCode = pickupCode.toUpperCase();
    this.currentFile = file;
    this.isSending = true;
    this.currentChunkIndex = 0;

    try {
      // 1. 生成加密密钥（客户端生成，不发送到服务器）
      console.log('[Sender] 生成加密密钥...');
      this.encryptionKey = await generateEncryptionKey();
      this.encryptionKeyBase64 = await exportKeyToBase64(this.encryptionKey);
      console.log('[Sender] ✓ 加密密钥已生成');

      // 2. 将文件分割成块
      console.log('[Sender] 分割文件为块...');
      const chunks = splitFileIntoChunks(file, 64 * 1024); // 64KB每块
      this.fileChunks = chunks;
      console.log(`[Sender] ✓ 文件已分割为 ${chunks.length} 个块`);

      // 3. 上传每个加密块
      console.log('[Sender] 开始上传加密文件块...');
      for (let i = 0; i < chunks.length; i++) {
        const chunk = chunks[i];
        
        // 加密文件块
        const encryptedChunk = await encryptChunk(chunk, this.encryptionKey);
        
        // 计算哈希（用于验证完整性）
        const chunkHash = await calculateChunkHash(encryptedChunk);
        
        // 上传到服务器
        const formData = new FormData();
        formData.append('chunk_data', encryptedChunk, `chunk_${i}.encrypted`);
        
        const response = await fetch(
          `${this.apiBase}/relay/codes/${this.pickupCode}/upload-chunk?chunk_index=${i}`,
          {
            method: 'POST',
            body: formData
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.msg || `上传块 ${i} 失败: HTTP ${response.status}`);
        }

        const result = await response.json();
        if (result.code !== 200) {
          throw new Error(result.msg || `上传块 ${i} 失败`);
        }

        // 验证服务器返回的哈希
        if (result.data.chunkHash !== chunkHash) {
          throw new Error(`块 ${i} 哈希验证失败，数据可能损坏`);
        }

        this.currentChunkIndex = i + 1;
        
        // 更新进度
        const progress = ((i + 1) / chunks.length) * 100;
        if (this.onProgress) {
          this.onProgress(progress, i + 1, chunks.length);
        }

        console.log(`[Sender] ✓ 块 ${i + 1}/${chunks.length} 上传成功 (${progress.toFixed(1)}%)`);
      }

      console.log('[Sender] ✓ 所有文件块上传完成');

      // 4. 使用取件码加密文件加密密钥，并存储到服务器
      console.log('[Sender] 使用取件码加密文件密钥...');
      const encryptedKey = await encryptKeyWithPickupCode(this.encryptionKey, this.pickupCode);
      await this.storeEncryptedKey(encryptedKey);
      console.log('[Sender] ✓ 加密密钥已存储到服务器');

      // 5. 通知服务器上传完成
      await this.notifyUploadComplete();

      // 6. 完成回调（不再需要返回密钥，用户只需分享取件码）
      if (this.onComplete) {
        this.onComplete();
      }

      this.isSending = false;
      // 不再返回密钥，用户只需分享取件码
      return null;
    } catch (error) {
      this.isSending = false;
      console.error('[Sender] 上传文件失败:', error);
      if (this.onError) {
        this.onError(error);
      }
      throw error;
    }
  }

  /**
   * 存储加密后的密钥到服务器
   * @param {string} encryptedKeyBase64 用取件码加密后的密钥
   * @returns {Promise<void>}
   */
  async storeEncryptedKey(encryptedKeyBase64) {
    try {
      const response = await fetch(
        `${this.apiBase}/relay/codes/${this.pickupCode}/store-encrypted-key`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            encryptedKey: encryptedKeyBase64
          })
        }
      );

      if (!response.ok) {
        throw new Error(`存储加密密钥失败: HTTP ${response.status}`);
      }

      console.log('[Sender] ✓ 加密密钥已存储到服务器');
    } catch (error) {
      console.warn('[Sender] 存储加密密钥失败:', error);
      // 不抛出错误，因为文件已经上传完成
    }
  }

  /**
   * 通知服务器上传完成
   * @returns {Promise<void>}
   */
  async notifyUploadComplete() {
    try {
      const response = await fetch(
        `${this.apiBase}/relay/codes/${this.pickupCode}/upload-complete`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            totalChunks: this.fileChunks.length,
            fileSize: this.currentFile.size,
            fileName: this.currentFile.name,
            mimeType: this.currentFile.type
          })
        }
      );

      if (!response.ok) {
        throw new Error(`通知上传完成失败: HTTP ${response.status}`);
      }

      console.log('[Sender] ✓ 已通知服务器上传完成');
    } catch (error) {
      console.warn('[Sender] 通知上传完成失败:', error);
      // 不抛出错误，因为文件已经上传完成
    }
  }

  /**
   * 获取加密密钥（已废弃，不再需要）
   * @deprecated 现在用户只需分享取件码，密钥会自动从服务器获取
   * @returns {string|null} 加密密钥的Base64字符串
   */
  getEncryptionKey() {
    return null; // 不再返回密钥
  }

}

// 导出单例实例
export const senderService = new SenderService();

