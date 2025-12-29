/**
 * Sender服务 - 发送方WebRTC连接管理
 * 负责接收receiver的offer，创建answer，建立连接，并发送文件
 */

import { splitFileIntoChunks } from '../utils/file-utils.js';
import { generateSessionId } from '../utils/common-utils.js';

class SenderService {
  constructor() {
    this.peerConnection = null;          // WebRTC连接实例
    this.dataChannel = null;             // 文件传输用数据通道
    this.sessionId = null;               // 当前会话ID
    this.pickupCode = null;              // 六位取件码
    this.apiBase = '';                   // 信令服务器基础URL
    // 回调函数
    this.onConnectionStateChange = null; // 连接状态变更
    this.onDataChannelOpen = null;       // 数据通道打开
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
    this.onConnectionStateChange = callbacks.onConnectionStateChange || null;
    this.onDataChannelOpen = callbacks.onDataChannelOpen || null;
    this.onProgress = callbacks.onProgress || null;
    this.onComplete = callbacks.onComplete || null;
    this.onError = callbacks.onError || null;
  }

  /**
   * 注册Sender，等待Receiver的Offer
   * @param {string} pickupCode - 分享会话的唯一表示代码（取件码）
   * @returns {Promise<void>}
   */
  async registerSender(pickupCode) {
    if (!this.apiBase) {
      throw new Error('API基础URL未设置，请先调用init()方法');
    }

    if (!pickupCode || !/^[A-Z0-9]{6}$/.test(pickupCode)) {
      throw new Error('无效的取件码，必须是6位大写字母或数字');
    }

    this.pickupCode = pickupCode.toUpperCase();

    try {
      const url = `${this.apiBase}/codes/${this.pickupCode}/webrtc/sender/register`;
      
      const requestBody = {
        senderInfo: {
          userAgent: navigator.userAgent
        }
      };

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
      console.log('Sender注册成功:', result);
    } catch (error) {
      console.error('Sender注册失败:', error);
      throw error;
    }
  }

  /**
   * 等待并获取Receiver的Offer（需要知道sessionId）
   * 注意：根据API设计，Sender需要知道sessionId才能获取offer
   * sessionId由Receiver创建offer时生成，可以通过以下方式获取：
   * 1. Receiver创建offer后，通过其他渠道（如WebSocket、回调）通知Sender
   * 2. 或者使用已知的sessionId（如果Receiver提前告知）
   * 
   * @param {string} sessionId - 会话ID（由Receiver创建offer时生成）
   * @param {number} maxAttempts - 最大尝试次数，默认60次
   * @param {number} interval - 轮询间隔（毫秒），默认1000ms
   * @returns {Promise<RTCSessionDescription>} 返回offer
   */
  async waitForOffer(sessionId, maxAttempts = 60, interval = 1000) {
    if (!this.pickupCode) {
      throw new Error('请先调用registerSender()注册');
    }

    this.sessionId = sessionId;
    const url = `${this.apiBase}/codes/${this.pickupCode}/webrtc/offer/${sessionId}`;

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
          
          if (result.data && result.data.offer) {
            return new RTCSessionDescription({
              type: 'offer',
              sdp: result.data.offer
            });
          }
        } else if (response.status === 404) {
          // Offer尚未创建，继续等待
          console.log(`等待Offer中... (尝试 ${i + 1}/${maxAttempts})`);
        }

        // 等待后继续轮询
        await new Promise(resolve => setTimeout(resolve, interval));
      } catch (error) {
        console.error(`轮询offer失败 (尝试 ${i + 1}/${maxAttempts}):`, error);
        await new Promise(resolve => setTimeout(resolve, interval));
      }
    }

    throw new Error('等待offer超时');
  }

  /**
   * 接收offer并创建answer
   * @param {string} pickupCode - 分享会话的唯一表示代码（取件码）
   * @param {string} sessionId - 会话ID（Receiver创建offer时生成）
   * @param {RTCSessionDescription} offer - 可选的offer对象，如果提供则直接使用，否则从服务器获取
   * @returns {Promise<void>}
   */
  async receiveOfferAndCreateAnswer(pickupCode, sessionId, offer = null) {
    if (!this.apiBase) {
      throw new Error('API基础URL未设置，请先调用init()方法');
    }

    if (!pickupCode || !/^[A-Z0-9]{6}$/.test(pickupCode)) {
      throw new Error('无效的取件码，必须是6位大写字母或数字');
    }

    this.pickupCode = pickupCode.toUpperCase();
    this.sessionId = sessionId;

    try {
      // 如果没有提供offer，从信令服务器获取
      if (!offer) {
        offer = await this.getOfferFromServer();
      }

      // 创建RTCPeerConnection
      this.peerConnection = new RTCPeerConnection({
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun1.l.google.com:19302' }
        ]
      });

      // 设置连接状态监听
      this.peerConnection.onconnectionstatechange = () => {
        const state = this.peerConnection.connectionState;
        if (this.onConnectionStateChange) {
          this.onConnectionStateChange(state);
        }
      };

      // 监听ICE候选
      this.peerConnection.onicecandidate = (event) => {
        if (event.candidate) {
          console.log('ICE candidate:', event.candidate);
        }
      };

      // 设置远程描述（offer）
      await this.peerConnection.setRemoteDescription(offer);

      // 创建数据通道
      this.dataChannel = this.peerConnection.createDataChannel('fileTransfer', {
        ordered: true
      });
      this.setupDataChannel();

      // 创建answer
      const answer = await this.peerConnection.createAnswer();
      await this.peerConnection.setLocalDescription(answer);

      // 等待ICE收集完成
      await this.waitForICE();

      // 发送answer到信令服务器
      await this.sendAnswerToServer(answer);

      console.log('Answer已发送，等待连接建立...');
    } catch (error) {
      console.error('接收offer并创建answer失败:', error);
      if (this.onError) {
        this.onError(error);
      }
      throw error;
    }
  }

  /**
   * 从信令服务器获取offer
   * @returns {Promise<RTCSessionDescription>}
   */
  async getOfferFromServer() {
    const url = `${this.apiBase}/codes/${this.pickupCode}/webrtc/offer/${this.sessionId}`;

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.msg || `HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      
      if (!result.data || !result.data.offer) {
        throw new Error('服务器返回的offer数据无效');
      }

      return new RTCSessionDescription({
        type: 'offer',
        sdp: result.data.offer
      });
    } catch (error) {
      console.error('获取offer失败:', error);
      throw error;
    }
  }

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
   * 发送answer到信令服务器
   * @param {RTCSessionDescription} answer - SDP answer
   * @returns {Promise<void>}
   */
  async sendAnswerToServer(answer) {
    const url = `${this.apiBase}/codes/${this.pickupCode}/webrtc/answer`;
    
    const requestBody = {
      sessionId: this.sessionId,
      answer: answer.sdp
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
      console.log('Answer发送成功:', result);
    } catch (error) {
      console.error('发送answer失败:', error);
      throw error;
    }
  }

  /**
   * 设置数据通道事件处理
   */
  setupDataChannel() {
    if (!this.dataChannel) return;

    this.dataChannel.onopen = () => {
      console.log('数据通道已打开，可以开始发送文件');
      if (this.onDataChannelOpen) {
        this.onDataChannelOpen();
      }
    };

    this.dataChannel.onclose = () => {
      console.log('数据通道已关闭');
    };

    this.dataChannel.onerror = (error) => {
      console.error('数据通道错误:', error);
      if (this.onError) {
        this.onError(error);
      }
    };
  }

  /**
   * 开始向receiver发送文件
   * @param {File} file - 要发送的文件
   * @returns {Promise<void>}
   */
  async startSendingFile(file) {
    if (!file) {
      throw new Error('文件不能为空');
    }

    if (!this.dataChannel || this.dataChannel.readyState !== 'open') {
      throw new Error('数据通道未打开，无法发送文件');
    }

    if (this.isSending) {
      throw new Error('文件正在发送中，请等待完成');
    }

    this.currentFile = file;
    this.isSending = true;
    this.currentChunkIndex = 0;

    try {
      // 将文件分割成块
      this.fileChunks = splitFileIntoChunks(file, 64 * 1024); // 64KB每块

      // 发送文件元数据
      const fileMetadata = {
        type: 'fileMetadata',
        fileName: file.name,
        fileSize: file.size,
        fileType: file.type,
        totalChunks: this.fileChunks.length
      };

      this.dataChannel.send(JSON.stringify(fileMetadata));
      console.log('文件元数据已发送:', fileMetadata);

      // 等待一小段时间确保元数据被接收
      await new Promise(resolve => setTimeout(resolve, 100));

      // 发送文件块
      await this.sendChunks();

      if (this.onComplete) {
        this.onComplete();
      }

      this.isSending = false;
    } catch (error) {
      this.isSending = false;
      console.error('发送文件失败:', error);
      if (this.onError) {
        this.onError(error);
      }
      throw error;
    }
  }

  /**
   * 发送文件块
   * @returns {Promise<void>}
   */
  async sendChunks() {
    for (let i = 0; i < this.fileChunks.length; i++) {
      // 检查数据通道状态
      if (this.dataChannel.readyState !== 'open') {
        throw new Error('数据通道已关闭，无法继续发送');
      }

      const chunk = this.fileChunks[i];
      
      // 将Blob转换为ArrayBuffer
      const arrayBuffer = await this.blobToArrayBuffer(chunk);
      
      // 创建包含索引的头部信息（使用Uint32Array，4字节）
      const header = new ArrayBuffer(4);
      const headerView = new DataView(header);
      headerView.setUint32(0, i, false); // big-endian
      
      // 合并头部和数据
      const combined = new Uint8Array(header.byteLength + arrayBuffer.byteLength);
      combined.set(new Uint8Array(header), 0);
      combined.set(new Uint8Array(arrayBuffer), header.byteLength);
      
      // 发送二进制数据
      this.dataChannel.send(combined.buffer);

      this.currentChunkIndex = i + 1;

      // 更新进度
      const progress = ((i + 1) / this.fileChunks.length) * 100;
      if (this.onProgress) {
        this.onProgress(progress, i + 1, this.fileChunks.length);
      }

      // 控制发送速度，避免阻塞
      if (i < this.fileChunks.length - 1) {
        await new Promise(resolve => setTimeout(resolve, 10));
      }
    }
  }

  /**
   * 将Blob转换为ArrayBuffer
   * @param {Blob} blob - Blob对象
   * @returns {Promise<ArrayBuffer>}
   */
  blobToArrayBuffer(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsArrayBuffer(blob);
    });
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

    this.currentFile = null;
    this.fileChunks = [];
    this.currentChunkIndex = 0;
    this.isSending = false;
  }

  /**
   * 获取连接状态
   * @returns {string} 连接状态
   */
  getConnectionState() {
    return this.peerConnection ? this.peerConnection.connectionState : 'closed';
  }

  /**
   * 获取发送进度
   * @returns {Object} 进度信息
   */
  getProgress() {
    if (this.fileChunks.length === 0) {
      return { progress: 0, sent: 0, total: 0 };
    }

    return {
      progress: (this.currentChunkIndex / this.fileChunks.length) * 100,
      sent: this.currentChunkIndex,
      total: this.fileChunks.length
    };
  }
}

// 导出单例实例
export const senderService = new SenderService();

