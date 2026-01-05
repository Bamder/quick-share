/**
 * 文件传输管理器 
 * 处理文件的分块上传、下载、进度管理
 */

import { TransferAPI } from '../utils/api-client.js';

class TransferManager {
    constructor() {
        this.currentCode = null;
        this.chunkSize = 1 * 1024 * 1024; // 1MB 每块，可根据网络调整
        this.maxConcurrent = 3; // 最大并发数
    }
    
    /**
     * 作为发送方：上传整个文件
     */
    async uploadFile(code, file) {
        this.currentCode = code;
        const totalChunks = Math.ceil(file.size / this.chunkSize);
        let uploadedChunks = 0;
        
        // 1. 更新UI：开始上传
        this.updateTransferStatus('uploading', `准备上传 (共${totalChunks}块)`);
        this.updateProgress(0, file.size);
        
        // 2. 计算文件哈希（简略版，实际应由后端校验）
        const fileHash = await this.calculateFileHash(file);
        
        // 3. 分块上传
        const uploadPromises = [];
        const errors = [];
        
        for (let i = 0; i < totalChunks; i++) {
            // 控制并发数
            if (uploadPromises.length >= this.maxConcurrent) {
                await Promise.race(uploadPromises);
            }
            
            const start = i * this.chunkSize;
            const end = Math.min(start + this.chunkSize, file.size);
            const chunkBlob = file.slice(start, end);
            
            const promise = this.uploadSingleChunk(code, i, chunkBlob, totalChunks)
                .then(() => {
                    uploadedChunks++;
                    const progress = (uploadedChunks / totalChunks) * 100;
                    this.updateProgress(start + (end - start), file.size);
                    this.updateTransferStatus('uploading', `上传中 ${uploadedChunks}/${totalChunks}`);
                })
                .catch(err => {
                    errors.push(`块${i}失败: ${err.message}`);
                });
            
            uploadPromises.push(promise);
        }
        
        // 等待所有块上传完成
        await Promise.allSettled(uploadPromises);
        
        // 4. 检查结果并完成上传
        if (errors.length > 0) {
            this.updateTransferStatus('error', `部分块上传失败`);
            throw new Error(errors.slice(0, 3).join('; ')); // 只显示前3个错误
        }
        
        this.updateTransferStatus('processing', '正在验证文件...');
        await TransferAPI.completeUpload(code, fileHash);
        
        this.updateTransferStatus('completed', '上传完成！');
        this.updateProgress(file.size, file.size);
        
        return { success: true, chunks: totalChunks };
    }
    
    /**
     * 上传单个块
     */
    async uploadSingleChunk(code, index, chunkBlob, totalChunks) {
        // 重试机制
        let lastError;
        for (let attempt = 1; attempt <= 3; attempt++) {
            try {
                const result = await TransferAPI.uploadChunk(code, index, chunkBlob, totalChunks);
                if (result.code === 200) return result;
                throw new Error(result.message);
            } catch (error) {
                lastError = error;
                await new Promise(resolve => setTimeout(resolve, attempt * 1000)); // 递增延迟
            }
        }
        throw lastError;
    }
    
    /**
     * 作为接收方：下载整个文件
     */
    async downloadFile(code) {
        this.currentCode = code;
        
        // 1. 获取文件块信息
        this.updateTransferStatus('preparing', '准备下载...');
        const chunkInfo = await TransferAPI.getChunkInfo(code);
        const totalChunks = chunkInfo.data.total_chunks;
        const fileSize = chunkInfo.data.total_size;
        
        // 2. 初始化进度
        this.updateTransferStatus('downloading', `开始下载 (共${totalChunks}块)`);
        this.updateProgress(0, fileSize);
        
        // 3. 分块下载
        const downloadedChunks = new Array(totalChunks);
        const errors = [];
        
        for (let i = 0; i < totalChunks; i++) {
            // 控制并发下载
            const activeDownloads = downloadedChunks.filter(c => c && c.status === 'downloading').length;
            if (activeDownloads >= this.maxConcurrent) {
                await new Promise(resolve => setTimeout(resolve, 100));
                i--; // 重试当前索引
                continue;
            }
            
            if (!downloadedChunks[i]) {
                downloadedChunks[i] = { status: 'downloading' };
                this.downloadSingleChunk(code, i, totalChunks)
                    .then(chunkData => {
                        downloadedChunks[i] = { status: 'done', data: chunkData };
                        // 更新进度
                        const doneCount = downloadedChunks.filter(c => c && c.status === 'done').length;
                        const progress = (doneCount / totalChunks) * 100;
                        this.updateProgress((doneCount / totalChunks) * fileSize, fileSize);
                        this.updateTransferStatus('downloading', `下载中 ${doneCount}/${totalChunks}`);
                        
                        // 如果全部完成，组装文件
                        if (doneCount === totalChunks) {
                            this.assembleFile(downloadedChunks.map(c => c.data), chunkInfo.data);
                        }
                    })
                    .catch(err => {
                        errors.push(`块${i}失败: ${err.message}`);
                        downloadedChunks[i] = { status: 'error' };
                    });
            }
        }
        
        // 返回一个Promise，在组装完成后resolve
        return new Promise((resolve, reject) => {
            const checkInterval = setInterval(() => {
                const doneCount = downloadedChunks.filter(c => c && c.status === 'done').length;
                if (doneCount === totalChunks) {
                    clearInterval(checkInterval);
                    resolve({ success: true });
                }
                if (errors.length > 5) { // 错误太多则失败
                    clearInterval(checkInterval);
                    reject(new Error('下载失败块过多'));
                }
            }, 500);
        });
    }
    
    /**
     * 下载单个块
     */
    async downloadSingleChunk(code, index, totalChunks) {
        for (let attempt = 1; attempt <= 3; attempt++) {
            try {
                return await TransferAPI.downloadChunk(code, index);
            } catch (error) {
                if (attempt === 3) throw error;
                await new Promise(resolve => setTimeout(resolve, attempt * 1000));
            }
        }
    }
    
    /**
     * 组装文件并触发下载
     */
    assembleFile(chunkArrayBuffers, fileInfo) {
        // 按顺序组装所有块
        const combined = new Uint8Array(fileInfo.total_size);
        let offset = 0;
        
        for (const chunk of chunkArrayBuffers) {
            combined.set(new Uint8Array(chunk), offset);
            offset += chunk.byteLength;
        }
        
        // 创建Blob并触发下载
        const blob = new Blob([combined], { type: fileInfo.mime_type });
        const url = URL.createObjectURL(blob);
        
        this.updateTransferStatus('completed', '下载完成！');
        this.triggerFileDownload(url, fileInfo.filename);
        
        // 通知服务器领取完成
        TransferAPI.recordUsage(this.currentCode).catch(console.error);
    }
    
    /**
     * 简化的文件哈希计算（实际校验应依赖后端）
     */
    async calculateFileHash(file) {
        // 这里是一个简单示例，生产环境应使用更安全算法（如SHA-256）
        const slice = file.slice(0, Math.min(1024, file.size));
        const buffer = await slice.arrayBuffer();
        const hashArray = Array.from(new Uint8Array(buffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 32);
    }
    
    /**
     * 更新传输状态 (UI集成点)
     */
    updateTransferStatus(status, message) {
        // 更新右侧状态显示
        const statusElement = document.getElementById('transferStatus');
        const descElement = document.getElementById('transferDescription');
        
        if (statusElement) statusElement.textContent = this.getStatusText(status);
        if (descElement) descElement.textContent = message;
        
        // 显示/隐藏传输进度容器
        const container = document.getElementById('transferProgressContainer');
        if (container) {
            container.style.display = ['uploading', 'downloading', 'processing'].includes(status) ? 'block' : 'none';
        }
    }
    
    /**
     * 更新进度条 (UI集成点)
     */
    updateProgress(current, total) {
        const progressElement = document.getElementById('transferProgress');
        const percentElement = document.getElementById('transferPercent');
        
        if (progressElement && percentElement) {
            const percent = Math.round((current / total) * 100);
            progressElement.style.width = `${percent}%`;
            percentElement.textContent = `${percent}%`;
        }
    }
    
    /**
     * 触发文件下载 (UI集成点)
     */
    triggerFileDownload(url, filename) {
        const downloadLink = document.getElementById('downloadLink');
        if (downloadLink) {
            downloadLink.href = url;
            downloadLink.download = filename;
            downloadLink.style.display = 'block';
            downloadLink.click(); // 自动触发下载
        }
    }
    
    getStatusText(status) {
        const map = {
            'preparing': '准备中',
            'uploading': '上传中',
            'downloading': '下载中',
            'processing': '处理中',
            'completed': '已完成',
            'error': '错误'
        };
        return map[status] || status;
    }
}

// 创建全局实例
const transferManager = new TransferManager();
export default transferManager;