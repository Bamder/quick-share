/**
 * Receiver服务 - 接收方WebRTC连接管理
 * 负责创建SDP offer，发送到信令服务器，等待并处理sender的answer
 */

import { formatFileSize } from '../utils/file-utils.js';
import { generateSessionId } from '../utils/common-utils.js';

class ReceiverService {
  constructor() {
    this.peerConnection = null;           // WebRTC连接实例
    this.dataChannel = null;              // 接收端数据通道
    this.sessionId = null;                // 当前会话ID
    this.pickupCode = null;               // 六位取件码
    this.apiBase = '';                    // 信令服务器基础URL
    // 回调函数
    this.onConnectionStateChange = null;  // 连接状态变更
    this.onDataChannelOpen = null;        // 数据通道打开
    this.onDataChannelMessage = null;     // 数据通道消息
    this.onDataChannelClose = null;       // 数据通道关闭
    this.onError = null;                  // 错误
    // 文件传输相关
    this.receivedChunks = [];             // 已接收的分片列表
    this.fileInfo = null;                 // 接收的文件元信息
  }

  /**
   * 初始化配置
   * @param {string} apiBase - API基础URL
   * @param {Object} callbacks - 回调函数对象
   */
  init(apiBase, callbacks = {}) {
    this.apiBase = apiBase;
    this.onConnectionStateChange = callbacks.onConnectionStateChange || null;
    this.onDataChannelOpen = callbacks.onDataChannelOpen || null;
    this.onDataChannelMessage = callbacks.onDataChannelMessage || null;
    this.onDataChannelClose = callbacks.onDataChannelClose || null;
    this.onError = callbacks.onError || null;
  }

  // 主函数：创建WebRTC连接并发送offer
  /**
   * 创建WebRTC连接并发送offer
   * @param {string} pickupCode - 分享会话的唯一表示代码（取件码）
   * @returns {Promise<string>} 返回sessionId
   */
  async createOffer(pickupCode) { 
    if (!this.apiBase) {
      throw new Error('API基础URL未设置，请先调用init()方法');
    }

    if (!pickupCode || !/^[A-Z0-9]{6}$/.test(pickupCode)) {
      throw new Error('无效的取件码，必须是6位大写字母或数字');
    }

    this.pickupCode = pickupCode.toUpperCase();
    this.sessionId = generateSessionId();

    try {
      // 创建RTCPeerConnection
      this.peerConnection = new RTCPeerConnection({
        iceServers: [
          { urls: 'stun:stun.voip.aebc.com:3478' },
          { urls: 'stun:stun.freeswitch.org:3478' },
          { urls: 'stun:stun.voipbuster.com:3478' },
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun1.l.google.com:19302' }
        ]
      });

      // 设置事件处理函数：连接状态变更、ICE候选、数据通道
      // 1. 设置连接状态监听
      this.peerConnection.onconnectionstatechange = () => {
        // 连接状态变更
        const state = this.peerConnection.connectionState;
        if (this.onConnectionStateChange) {
          this.onConnectionStateChange(state);
        }
        console.log('连接状态变更:', state);
      };

      // 2. 监听ICE候选
      this.peerConnection.onicecandidate = (event) => {
        // 当有ICE候选时，打印日志
        if (event.candidate) {
          // ICE候选可以在这里发送到服务器，但通常包含在SDP中
          console.log('ICE candidate:', event.candidate);
        }
      };

      // 3. 监听数据通道（sender会创建数据通道）
      this.peerConnection.ondatachannel = (event) => {
        // 当sender创建数据通道时，设置数据通道
        this.dataChannel = event.channel; 
        console.log('创建数据通道:', event.channel);
        // 设置数据通道
        this.setupDataChannel();
      };

      // Receiver发起并建立P2P连接流程
      // 1. 创建offer
      const offer = await this.peerConnection.createOffer();
      await this.peerConnection.setLocalDescription(offer);

      // 2. 等待ICE收集完成
      await this.waitForICE();

      // 3. 发送offer到信令服务器
      await this.sendOfferToServer(offer);

      // 4. 开始轮询等待answer
      await this.waitForAnswer();

      return this.sessionId;
    } catch (error) {
      console.error('创建offer失败:', error);
      if (this.onError) {
        this.onError(error);
      }
      throw error;
    }
  }

  // 辅助函数：等待ICE收集完成、发送offer到信令服务器、轮询等待answer
  /**
   * 等待ICE收集完成
   * @returns {Promise<void>}
   */
  waitForICE() {
    return new Promise((resolve) => {
      if (this.peerConnection.iceGatheringState === 'complete') {
        resolve();
        return;
      }

      const checkState = () => {
        if (this.peerConnection.iceGatheringState === 'complete') {
          resolve();
        } else {
          setTimeout(checkState, 100);
        }
      };

      this.peerConnection.addEventListener('icegatheringstatechange', () => {
        if (this.peerConnection.iceGatheringState === 'complete') {
          resolve();
        }
      });

      // 超时保护（5秒）
      setTimeout(() => {
        if (this.peerConnection.iceGatheringState !== 'complete') {
          console.warn('ICE收集超时，继续执行');
          resolve();
        }
      }, 5000);
    });
  }

  /**
   * 发送offer到信令服务器
   * @param {RTCSessionDescription} offer - SDP offer
   * @returns {Promise<void>}
   */
  async sendOfferToServer(offer) {
    const url = `${this.apiBase}/codes/${this.pickupCode}/webrtc/offer`;
    
    const requestBody = {
      sessionId: this.sessionId,
      offer: offer.sdp,
      receiverInfo: {
        userAgent: navigator.userAgent
      }
    };

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.msg || `HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      console.log('Offer发送成功:', result);
    } catch (error) {
      console.error('发送offer失败:', error);
      throw error;
    }
  }

  /**
   * 轮询等待answer
   * @param {number} maxAttempts - 最大尝试次数，默认60次
   * @param {number} interval - 轮询间隔（毫秒），默认1000ms
   * @returns {Promise<void>}
   */
  async waitForAnswer(maxAttempts = 60, interval = 1000) {
    const url = `${this.apiBase}/codes/${this.pickupCode}/webrtc/answer/${this.sessionId}`;

    for (let i = 0; i < maxAttempts; i++) {
      try {
        const response = await fetch(url, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          const result = await response.json();
          
          // 检查是否有answer
          if (result.data && result.data.answer) {
            await this.handleAnswer(result.data.answer);
            return;
          }
        } else if (response.status === 404) {
          // Answer尚未创建，继续等待
          const result = await response.json().catch(() => ({}));
          console.log(`等待Answer中... (尝试 ${i + 1}/${maxAttempts})`);
        }

        // 等待后继续轮询
        await new Promise(resolve => setTimeout(resolve, interval));
      } catch (error) {
        console.error(`轮询answer失败 (尝试 ${i + 1}/${maxAttempts}):`, error);
        await new Promise(resolve => setTimeout(resolve, interval));
      }
    }

    throw new Error('等待answer超时');
  }

  /**
   * 处理接收到的answer
   * @param {string} answerSdp - SDP answer字符串
   * @returns {Promise<void>}
   */
  async handleAnswer(answerSdp) {
    try {
      const answer = new RTCSessionDescription({
        type: 'answer',
        sdp: answerSdp
      });

      await this.peerConnection.setRemoteDescription(answer);
      console.log('Answer设置成功，连接建立中...');
    } catch (error) {
      console.error('处理answer失败:', error);
      throw error;
    }
  }

  /**
   * 设置数据通道事件处理
   */
  setupDataChannel() {
    if (!this.dataChannel) return;

    this.dataChannel.onopen = () => {
      console.log('数据通道已打开');
      if (this.onDataChannelOpen) {
        this.onDataChannelOpen();
      }
    };

    this.dataChannel.onmessage = (event) => {
      this.handleDataChannelMessage(event);
    };

    this.dataChannel.onclose = () => {
      console.log('数据通道已关闭');
      if (this.onDataChannelClose) {
        this.onDataChannelClose();
      }
    };

    this.dataChannel.onerror = (error) => {
      console.error('数据通道错误:', error);
      if (this.onError) {
        this.onError(error);
      }
    };
  }

  /**
   * 处理数据通道消息
   * @param {MessageEvent} event - 消息事件
   */
  handleDataChannelMessage(event) {
    // 检查是否是字符串（JSON格式的元数据）
    if (typeof event.data === 'string') {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'fileMetadata') {
          this.handleFileMetadata(data);
        }
      } catch (error) {
        console.error('解析消息失败:', error);
      }
    } 
    // 处理二进制数据（文件块）
    else if (event.data instanceof ArrayBuffer) {
      this.handleFileChunk(event.data);
    }
    // 如果用户提供了自定义处理函数，也调用它
    if (this.onDataChannelMessage) {
      this.onDataChannelMessage(event);
    }
  }

  /**
   * 处理文件元数据
   * @param {Object} metadata - 文件元数据
   */
  handleFileMetadata(metadata) {
    this.fileInfo = {
      fileName: metadata.fileName,
      fileSize: metadata.fileSize,
      fileType: metadata.fileType,
      totalChunks: metadata.totalChunks
    };
    this.receivedChunks = new Array(metadata.totalChunks);
    console.log('收到文件元数据:', this.fileInfo);
  }

  /**
   * 处理文件块
   * @param {ArrayBuffer} buffer - 文件块数据
   */
  handleFileChunk(buffer) {
    if (!this.fileInfo) {
      console.warn('收到文件块但未收到元数据');
      return;
    }

    // 读取块索引（前4字节）
    const headerView = new DataView(buffer, 0, 4);
    const chunkIndex = headerView.getUint32(0, false); // big-endian
    
    // 提取实际数据（跳过4字节头部）
    const chunkData = buffer.slice(4);
    
    // 存储块
    this.receivedChunks[chunkIndex] = chunkData;
    
    // 检查是否所有块都已接收
    const receivedCount = this.receivedChunks.filter(chunk => chunk !== undefined).length;
    const progress = (receivedCount / this.fileInfo.totalChunks) * 100;
    
    console.log(`收到文件块 ${chunkIndex + 1}/${this.fileInfo.totalChunks} (${progress.toFixed(1)}%)`);
    
    // 如果所有块都已接收，重建文件
    if (receivedCount === this.fileInfo.totalChunks) {
      this.reconstructFile();
    }
  }

  /**
   * 重建文件
   */
  reconstructFile() {
    try {
      // 确保所有块都已按顺序接收
      const allChunksReceived = this.receivedChunks.every(chunk => chunk !== undefined);
      if (!allChunksReceived) {
        console.warn('部分文件块缺失，尝试重建...');
      }

      // 将ArrayBuffer转换为Blob
      const blobs = this.receivedChunks.map(chunk => new Blob([chunk]));
      const fileBlob = new Blob(blobs, { type: this.fileInfo.fileType });
      
      console.log('文件重建完成:', this.fileInfo.fileName, formatFileSize(fileBlob.size));
      
      // 触发文件接收完成事件
      if (this.onDataChannelMessage) {
        this.onDataChannelMessage({
          type: 'fileComplete',
          file: fileBlob,
          fileName: this.fileInfo.fileName,
          fileType: this.fileInfo.fileType
        });
      }
    } catch (error) {
      console.error('重建文件失败:', error);
      if (this.onError) {
        this.onError(error);
      }
    }
  }

  /**
   * 关闭连接
   */
  close() {
    if (this.dataChannel) {
      this.dataChannel.close();
      this.dataChannel = null;
    }

    if (this.peerConnection) {
      this.peerConnection.close();
      this.peerConnection = null;
    }

    this.receivedChunks = [];
    this.fileInfo = null;
  }

  /**
   * 获取连接状态
   * @returns {string} 连接状态
   */
  getConnectionState() {
    return this.peerConnection ? this.peerConnection.connectionState : 'closed';
  }
}

// 导出单例实例
export const receiverService = new ReceiverService();

