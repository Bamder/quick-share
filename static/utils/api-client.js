/**
 * QuickShare API 客户端 (服务器中转版)
 * 封装所有与后端交互的接口
 */

// 服务器地址和端口
const API_BASE = "http://你的服务器IP:你的端口"; // 例如: http://47.104.xxx.xxx:8000

const API_VERSION = "/api/v1";

/**
 * 统一的API请求函数
 * @param {string} method 请求方法
 * @param {string} endpoint API端点
 * @param {Object} body 请求体
 * @param {Object} customHeaders 自定义请求头
 */
export async function apiRequest(
  method,
  endpoint,
  body = null,
  customHeaders = {}
) {
  const url = `${API_BASE}${API_VERSION}${endpoint}`;

  // 自动添加Authorization头
  const token = localStorage.getItem("quickshare_token");
  const authHeader = token ? { Authorization: `Bearer ${token}` } : {};

  const headers = {
    Accept: "application/json",
    ...authHeader,
    ...customHeaders,
  };

  // 如果body不是FormData且不为null，则添加Content-Type头
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const options = {
    method,
    headers,
  };

  // 添加请求体
  if (body) {
    options.body = body instanceof FormData ? body : JSON.stringify(body);
  }

  try {
    const response = await fetch(url, options);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || `HTTP ${response.status}`);
    }

    return data;
  } catch (error) {
    console.error(`API请求失败 [${method} ${endpoint}]:`, error);
    throw error;
  }
}

/**
 * 取件码与文件元信息API
 */
export const CodeAPI = {
  // 创建取件码（开始上传流程）
  async createCode(fileInfo) {
    return await apiRequest("POST", "/codes", fileInfo);
  },

  // 验证取件码状态
  async getCodeStatus(code) {
    return await apiRequest("GET", `/codes/${code}/status`);
  },

  // 获取文件信息
  async getFileInfo(code) {
    return await apiRequest("GET", `/codes/${code}/file-info`);
  },

  // 记录完成一次领取
  async recordUsage(code) {
    return await apiRequest("POST", `/codes/${code}/usage`);
  },
};

/**
 * 文件分块传输API (服务器中转核心)
 */
export const TransferAPI = {
  // 【发送方】上传一个文件块
  async uploadChunk(code, chunkIndex, chunkData, totalChunks) {
    const formData = new FormData();
    formData.append("chunk_index", chunkIndex);
    formData.append("chunk_data", new Blob([chunkData]), `chunk_${chunkIndex}`);
    formData.append("total_chunks", totalChunks);

    // 注意：这里直接使用 ${API_BASE}，不走 apiRequest 包装，以便上传二进制数据
    const response = await fetch(
      `${API_BASE}${API_VERSION}/transfer/${code}/upload-chunk`,
      {
        method: "POST",
        body: formData,
      }
    );
    return await response.json();
  },

  // 【发送方】通知服务器上传完成
  async completeUpload(code, fileHash) {
    return await apiRequest("POST", `/transfer/${code}/complete`, {
      file_hash: fileHash,
    });
  },

  // 【接收方】获取一个文件块
  async downloadChunk(code, chunkIndex) {
    const response = await fetch(
      `${API_BASE}${API_VERSION}/transfer/${code}/download-chunk?chunk_index=${chunkIndex}`
    );
    if (!response.ok) throw new Error(`下载块失败: ${response.status}`);
    return await response.arrayBuffer(); // 返回二进制数据
  },

  // 【接收方】获取文件块信息（总块数等）
  async getChunkInfo(code) {
    return await apiRequest("GET", `/transfer/${code}/chunk-info`);
  },
};

/**
 * 举报功能API
 */
export const ReportAPI = {
  async submitReport(code, reason) {
    return await apiRequest("POST", "/reports", { code, reason });
  },
};

/**
 * 服务器健康检查
 */
export const HealthAPI = {
  async check() {
    const response = await fetch(`${API_BASE}/health`);
    return response.ok;
  },
};

/**
 * 测试用：预置的测试取件码 (功能不变)
 */
export const TEST_CODES = {
  WAIT01: "WAIT01",
  TRAN02: "TRAN02",
  DONE03: "DONE03",
};
