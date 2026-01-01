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

class ReceiverService {
  constructor() {
    // 服务器中转相关
    this.pickupCode = null;               // 十二位取件码（前6位查找码+后6位密钥码）
    this.apiBase = '';                    // API服务器基础URL
    this.encryptionKey = null;             // 解密密钥
    this.fileInfo = null;                 // 文件元信息
    
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
      // 1. 从服务器获取加密后的文件加密密钥
      console.log('[Receiver] 从服务器获取加密密钥...');
      const encryptedKey = await this.getEncryptedKey();
      
      // 2. 使用取件码解密文件加密密钥
      console.log('[Receiver] 使用取件码解密文件密钥...');
      this.encryptionKey = await decryptKeyWithPickupCode(encryptedKey, this.pickupCode);
      console.log('[Receiver] ✓ 文件加密密钥已解密');

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

      // 4. 下载所有加密块
      console.log('[Receiver] 开始下载加密文件块...');
      const downloadPromises = [];
      for (let i = 0; i < fileInfo.totalChunks; i++) {
        downloadPromises.push(this.downloadChunk(i));
      }

      // 并行下载所有块
      await Promise.all(downloadPromises);
      console.log('[Receiver] ✓ 所有文件块下载完成');

      // 5. 解密并重组文件
      console.log('[Receiver] 解密并重组文件...');
      const decryptedChunks = await Promise.all(
        this.receivedChunks.map((encryptedChunk, index) => {
          if (!encryptedChunk) {
            throw new Error(`块 ${index} 缺失`);
          }
          return decryptChunk(encryptedChunk, this.encryptionKey);
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
   * 从服务器获取加密后的文件加密密钥
   * @returns {Promise<string>} 加密后的密钥（Base64）
   */
  async getEncryptedKey() {
    const response = await fetch(
      `${this.apiBase}/relay/codes/${this.lookupCode}/encrypted-key`
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.msg || `获取加密密钥失败: HTTP ${response.status}`);
    }

    const result = await response.json();
    if (result.code !== 200 || !result.data || !result.data.encryptedKey) {
      throw new Error(result.msg || '获取加密密钥失败');
    }

    return result.data.encryptedKey;
  }

  /**
   * 获取文件信息
   * @returns {Promise<Object>} 文件信息
   */
  async getFileInfo() {
    const response = await fetch(
      `${this.apiBase}/relay/codes/${this.lookupCode}/file-info`
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
   * 下载单个加密块
   * @param {number} chunkIndex - 块索引
   * @returns {Promise<void>}
   */
  async downloadChunk(chunkIndex) {
    const response = await fetch(
      `${this.apiBase}/relay/codes/${this.lookupCode}/download-chunk/${chunkIndex}`
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.msg || `下载块 ${chunkIndex} 失败: HTTP ${response.status}`);
    }

    // 读取加密块
    const encryptedChunk = await response.blob();
    this.receivedChunks[chunkIndex] = encryptedChunk;

    // 更新进度
    const receivedCount = this.receivedChunks.filter(chunk => chunk !== undefined).length;
    const progress = (receivedCount / this.receivedChunks.length) * 100;
    
    if (this.onProgress) {
      this.onProgress(progress, receivedCount, this.receivedChunks.length);
    }

    console.log(`[Receiver] ✓ 块 ${chunkIndex + 1}/${this.receivedChunks.length} 下载成功 (${progress.toFixed(1)}%)`);
  }

  /**
   * 通知服务器下载完成
   * @returns {Promise<void>}
   */
  async notifyDownloadComplete() {
    try {
      const response = await fetch(
        `${this.apiBase}/relay/codes/${this.lookupCode}/download-complete`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) {
        throw new Error(`通知下载完成失败: HTTP ${response.status}`);
      }

      console.log('[Receiver] ✓ 已通知服务器下载完成');
    } catch (error) {
      console.warn('[Receiver] 通知下载完成失败:', error);
      // 不抛出错误，因为文件已经下载完成
    }
  }

}

// 导出单例实例
export const receiverService = new ReceiverService();

