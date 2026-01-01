/**
 * 主页面逻辑
 */

// 导入工具函数
import { formatFileSize, getFileIcon, downloadBlob, reconstructFileFromChunks } from '/static/utils/file-utils.js';
import {
    showMessage,
    showLoading,
    isValidPickupCode,
    generatePickupCode,
    formatRemainingTime,
    testPortConnection
} from '/static/utils/common-utils.js';

// 导入服务（使用导出的单例实例）
import { senderService as importedSenderService } from '/static/service/sender-service.js';
import { receiverService as importedReceiverService } from '/static/service/receiver-service.js';

// 配置信息
const CONFIG = {
    API_BASE: '',
    localFile: null,
    pickupCode: '',
    fileSize: 0,
    fileName: '',
    pollingInterval: null,
    encryptionKey: null  // 加密密钥（用于分享给接收者）
};

// 服务实例（使用导入的单例）
const senderService = importedSenderService;
const receiverService = importedReceiverService;

// ========== 初始化函数 ==========
// 导入弹窗模块
import { loadModalHTML, openModal, closeModal, initModalEvents } from '/static/components/modal/modal.js';

// 导出 openModal 供其他模块使用
export { openModal, closeModal };

document.addEventListener('DOMContentLoaded', async function() {
    // 先加载弹窗HTML
    await loadModalHTML();
    
    // 然后初始化其他功能
    initEventListeners();
    autoTestPort();
    restorePreviousState();
});

// ========== 事件监听器初始化 ==========
function initEventListeners() {
    // 文件选择事件
    document.getElementById('fileInput').onchange = function() {
        if (this.files.length) handleFile(this.files[0]);
    };
    
    // 拖拽事件
    setupDragAndDrop();
    
    // 按钮事件
    document.getElementById('shareBtn').onclick = generatePickupCodeHandler;
    document.getElementById('copyCodeBtn').onclick = copyPickupCode;
    document.getElementById('receiveBtn').onclick = receiveFile;
    document.getElementById('reportBtn').onclick = reportFile;
    document.getElementById('testBtn').onclick = testPortConnectionHandler;
    
    // 注意：弹窗事件已在 modal.js 中初始化，这里不需要重复绑定
    
    // 输入框事件
    const inputCode = document.getElementById('inputCode');
    if (inputCode) {
        inputCode.addEventListener('input', function(e) {
            this.value = this.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
        });
    }
    
    // 返回欢迎页按钮（可选添加）
    addBackButton();
}

// ========== 拖拽功能 ==========
function setupDragAndDrop() {
    const dropArea = document.getElementById('dropArea');
    if (!dropArea) return;
    
    // 点击选择文件
    dropArea.onclick = function() {
        document.getElementById('fileInput').click();
    };
    
    // 拖拽事件
    ['dragenter', 'dragover'].forEach(evt => {
        dropArea.addEventListener(evt, function(e) {
            e.preventDefault();
            this.classList.add('dragover');
        });
    });
    
    ['dragleave', 'drop'].forEach(evt => {
        dropArea.addEventListener(evt, function(e) {
            e.preventDefault();
            this.classList.remove('dragover');
            if (e.type === 'drop' && e.dataTransfer.files.length) {
                handleFile(e.dataTransfer.files[0]);
            }
        });
    });
}

// ========== 文件处理 ==========
function handleFile(file) {
    CONFIG.localFile = file;
    
    // 显示文件信息
    const fileInfo = document.getElementById('fileInfo');
    if (fileInfo) {
        document.getElementById('fileName').textContent = file.name;
        document.getElementById('fileSize').textContent = formatFileSize(file.size);
        fileInfo.style.display = 'block';
    }
    
    // 启用生成按钮
    const shareBtn = document.getElementById('shareBtn');
    if (shareBtn) {
        shareBtn.disabled = false;
    }
    
    // 预览图片
    const preview = document.getElementById('preview');
    if (preview) {
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function(e) {
                preview.innerHTML = `<img src="${e.target.result}" alt="预览" style="max-width:150px; border-radius:8px;">`;
            };
            reader.readAsDataURL(file);
        } else {
            const icon = getFileIcon(file.name);
            preview.innerHTML = `<div style="font-size:3rem;">${icon}</div>`;
        }
    }
    
    // 保存文件信息
    CONFIG.fileName = file.name;
    CONFIG.fileSize = file.size;
    
    showMessage(`已选择文件: ${file.name}`, 'success');
}

// ========== 生成取件码处理器 ==========
async function generatePickupCodeHandler() {
    if (!CONFIG.localFile) {
        showMessage('请先选择文件', 'error');
        return;
    }
    
    if (!CONFIG.API_BASE) {
        showMessage('请先测试端口连接', 'error');
        return;
    }
    
    const shareBtn = document.getElementById('shareBtn');
    if (shareBtn) {
        shareBtn.disabled = true;
        shareBtn.innerHTML = '<i class="icon-generate"></i> 生成中...';
    }
    
    showLoading(true, '正在创建取件码...');
    
    try {
        // 验证文件大小
        if (!CONFIG.localFile.size || CONFIG.localFile.size <= 0) {
            showMessage('文件大小无效，请选择有效的文件', 'error');
            showLoading(false);
            if (shareBtn) {
                shareBtn.disabled = false;
                shareBtn.innerHTML = '<i class="icon-generate"></i> 生成取件码';
            }
            return;
        }
        
        // 验证文件名
        if (!CONFIG.localFile.name || CONFIG.localFile.name.trim() === '') {
            showMessage('文件名无效，请选择有效的文件', 'error');
            showLoading(false);
            if (shareBtn) {
                shareBtn.disabled = false;
                shareBtn.innerHTML = '<i class="icon-generate"></i> 生成取件码';
            }
            return;
        }
        
        // 获取配置选项
        const expireSelect = document.getElementById('expireSelect');
        const limitSelect = document.getElementById('limitSelect');
        
        // 处理过期时间：前端是分钟，后端需要小时
        const expireMinutes = expireSelect ? parseInt(expireSelect.value) || 1440 : 1440; // 默认1440分钟 = 24小时
        // 转换为小时，至少1小时（如果小于60分钟，也设为1小时）
        // 先计算小时数，然后向上取整，最后转换为整数
        const expireHoursRaw = expireMinutes / 60;
        const expireHours = Math.max(1, Math.ceil(expireHoursRaw)); // 向上取整，至少1小时
        const expireHoursInt = Number.isInteger(expireHours) ? expireHours : Math.floor(expireHours); // 确保是整数
        
        // 确保 limitCount 在有效范围内
        const limitCountRaw = limitSelect ? parseInt(limitSelect.value) || 3 : 3;
        const limitCount = Math.max(1, Math.min(999, limitCountRaw)); // 限制在 1-999 之间
        
        console.log('配置选项:', { 
            expireMinutes, 
            expireHoursRaw, 
            expireHours, 
            expireHoursInt, 
            limitCount,
            '验证expireHoursInt类型': typeof expireHoursInt
        });
        
        // 计算文件哈希（可选，这里先不实现）
        // const fileHash = await calculateFileHash(CONFIG.localFile);
        
        // 准备请求数据（确保所有数字都是整数）
        const requestData = {
            originalName: CONFIG.localFile.name.trim(),
            size: Number.isInteger(CONFIG.localFile.size) ? CONFIG.localFile.size : Math.floor(CONFIG.localFile.size), // 确保是整数
            limitCount: Number.isInteger(limitCount) ? limitCount : Math.floor(limitCount), // 确保是整数
            expireHours: expireHoursInt // 使用计算好的整数
        };
        
        // 验证数据类型
        console.log('请求数据类型验证:', {
            size: { value: requestData.size, type: typeof requestData.size, isInteger: Number.isInteger(requestData.size) },
            limitCount: { value: requestData.limitCount, type: typeof requestData.limitCount, isInteger: Number.isInteger(requestData.limitCount) },
            expireHours: { value: requestData.expireHours, type: typeof requestData.expireHours, isInteger: Number.isInteger(requestData.expireHours) }
        });
        
        // 可选字段：只在有值时才添加
        if (CONFIG.localFile.type && CONFIG.localFile.type.trim() !== '') {
            requestData.mimeType = CONFIG.localFile.type.trim();
        }
        // hash 暂时不计算，不添加到请求中（使用默认值 null）
        
        console.log('发送创建取件码请求:', requestData);
        
        // 调用后端 API 创建文件和取件码
        const response = await fetch(`${CONFIG.API_BASE}/v1/codes`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            let errorData = {};
            try {
                errorData = await response.json();
                console.error('API 错误响应:', errorData);
            } catch (e) {
                console.error('解析错误响应失败:', e);
            }
            
            // 422 错误通常是验证错误，显示详细错误信息
            if (response.status === 422) {
                console.error('请求数据:', requestData);
                console.error('错误详情:', errorData);
                
                let errorMessage = '数据验证失败';
                if (errorData.detail && Array.isArray(errorData.detail)) {
                    const errorMessages = errorData.detail.map(err => {
                        const field = err.field || err.loc?.join('.') || '未知字段';
                        return `${field}: ${err.message || err.msg || '验证失败'}`;
                    }).join('; ');
                    errorMessage = `数据验证失败: ${errorMessages}`;
                } else if (errorData.msg) {
                    errorMessage = errorData.msg;
                }
                
                throw new Error(errorMessage);
            }
            
            throw new Error(errorData.msg || `HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (result.code !== 201 || !result.data) {
            throw new Error(result.msg || '创建取件码失败');
        }
        
        // 保存取件码信息
        CONFIG.pickupCode = result.data.code;
        CONFIG.fileName = result.data.fileName;
        CONFIG.fileSize = result.data.fileSize;
        
        // 更新取件码显示并打开弹窗
        const pickupCodeElement = document.getElementById('pickupCode');
        
        if (pickupCodeElement) {
            pickupCodeElement.textContent = CONFIG.pickupCode;
            // 打开取件码弹窗
            openModal('codeModal');
        }
        
        // 初始化 SenderService 并注册
        await initializeSenderService();
        
        // 更新状态显示（使用服务器返回的数据）
        updateStatusDisplayFromServer(result.data);
        
        // 开始轮询状态
        startStatusPolling();
        
        // 保存状态
        saveCurrentState();
        
        showMessage('取件码已生成，分享给朋友吧！', 'success');
        
    } catch (error) {
        console.error('创建取件码失败:', error);
        showMessage(`创建取件码失败: ${error.message}`, 'error');
    } finally {
        showLoading(false);
        if (shareBtn) {
            shareBtn.disabled = false;
            shareBtn.innerHTML = '<i class="icon-generate"></i> 生成取件码';
        }
    }
}

// ========== 复制取件码 ==========
function copyPickupCode() {
    if (!CONFIG.pickupCode) {
        showMessage('请先生成取件码', 'error');
        return;
    }
    
    // 检查是否支持 Clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(CONFIG.pickupCode)
            .then(() => showMessage('取件码已复制到剪贴板', 'success'))
            .catch((error) => {
                console.warn('Clipboard API 失败，使用降级方案:', error);
                // 降级方案
                fallbackCopyTextToClipboard(CONFIG.pickupCode);
            });
    } else {
        // 直接使用降级方案
        fallbackCopyTextToClipboard(CONFIG.pickupCode);
    }
}

// 降级复制方案（兼容旧浏览器）
function fallbackCopyTextToClipboard(text) {
    try {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        
        if (successful) {
            showMessage('取件码已复制', 'success');
        } else {
            showMessage('复制失败，请手动复制取件码', 'error');
        }
    } catch (error) {
        console.error('复制失败:', error);
        showMessage('复制失败，请手动复制取件码', 'error');
    }
}

// ========== 接收文件 ==========
async function receiveFile() {
    const inputCode = document.getElementById('inputCode');
    if (!inputCode) return;
    
    const code = inputCode.value.trim().toUpperCase();
    
    if (!isValidPickupCode(code)) {
        showMessage('请输入12位有效的取件码', 'error');
        return;
    }
    
    if (!CONFIG.API_BASE) {
        showMessage('请先测试端口连接', 'error');
        return;
    }
    
    const receiveBtn = document.getElementById('receiveBtn');
    if (receiveBtn) {
        receiveBtn.disabled = true;
        receiveBtn.innerHTML = '<i class="icon-receive"></i> 领取中...';
    }
    
    // 显示加载动画
    showLoading(true, '正在连接...');
    
    try {
        // 先查询取件码状态，获取文件信息
        const statusResponse = await fetch(`${CONFIG.API_BASE}/v1/codes/${code}/status`);
        if (!statusResponse.ok) {
            const errorData = await statusResponse.json().catch(() => ({}));
            throw new Error(errorData.msg || '取件码不存在或已失效');
        }
        
        const statusResult = await statusResponse.json();
        const fileInfo = statusResult.data;
        
        if (!fileInfo) {
            throw new Error('无法获取文件信息');
        }
        
        // 更新状态显示（包括剩余时间）
        if (fileInfo) {
            updateStatusDisplayFromServer(fileInfo);
        }
        
        // 开始轮询状态（接收方也需要显示剩余时间）
        startStatusPolling();
        
        // 初始化 ReceiverService
        await initializeReceiverService(code, fileInfo);
        
    } catch (error) {
        console.error('接收文件失败:', error);
        showMessage(`接收失败: ${error.message}`, 'error');
        showLoading(false);
        if (receiveBtn) {
            receiveBtn.disabled = false;
            receiveBtn.innerHTML = '<i class="icon-receive"></i> 领取';
        }
    }
}

// ========== 初始化 SenderService（服务器中转模式） ==========
async function initializeSenderService() {
    if (!CONFIG.API_BASE || !CONFIG.pickupCode || !CONFIG.localFile) {
        return;
    }
    
    try {
        // 初始化服务
        senderService.init(`${CONFIG.API_BASE}/v1`, {
            onProgress: (progress, sent, total) => {
                console.log(`上传进度: ${progress.toFixed(1)}% (${sent}/${total})`);
                // 可以在这里更新上传进度显示（如果需要）
            },
            onComplete: () => {
                console.log('文件上传完成');
                showMessage('文件已成功上传，等待接收方下载', 'success');
            },
            onError: (error) => {
                console.error('上传错误:', error);
                showMessage(`上传失败: ${error.message}`, 'error');
            }
        });
        
        // 通过服务器中转上传文件（使用端到端加密）
        console.log('[Sender] 开始上传文件（服务器中转模式）...');
        showMessage('正在上传文件...', 'info');
        
        await senderService.uploadFileViaRelay(CONFIG.pickupCode, CONFIG.localFile);
        
        console.log('[Sender] ✓ 文件上传完成');
        showMessage('文件上传完成！请将取件码分享给接收方', 'success');
        
    } catch (error) {
        console.error('初始化SenderService失败:', error);
        showMessage(`初始化发送服务失败: ${error.message}`, 'error');
    }
}

// ========== P2P WebRTC 相关代码已完全移除 ==========
// 已改为使用服务器中转模式，不再需要等待 Offer、处理连接等逻辑

// ========== 初始化 ReceiverService（服务器中转模式） ==========
async function initializeReceiverService(code, fileInfo) {
    if (!CONFIG.API_BASE) {
        return;
    }
    
    try {
        // 显示文件信息
        const progressBar = document.getElementById('recvProgressBar');
        const progressFill = document.querySelector('.progress-fill');
        const progressPercent = document.getElementById('progressPercent');
        
        if (progressBar) {
            progressBar.style.display = 'block';
        }
        
        // 初始化服务
        receiverService.init(`${CONFIG.API_BASE}/v1`, {
            onProgress: (progress, received, total) => {
                console.log(`下载进度: ${progress.toFixed(1)}% (${received}/${total})`);
                
                // 更新进度条
                if (progressFill) {
                    progressFill.style.width = `${progress}%`;
                }
                if (progressPercent) {
                    progressPercent.textContent = `${progress.toFixed(1)}%`;
                }
            },
            onComplete: (fileBlob) => {
                console.log('文件下载完成:', fileInfo.fileName);
                
                // 更新进度条
                if (progressFill) {
                    progressFill.style.width = '100%';
                }
                if (progressPercent) {
                    progressPercent.textContent = '100%';
                }
                
                // 显示下载链接
                const downloadLink = document.getElementById('downloadLink');
                if (downloadLink) {
                    downloadLink.style.display = 'block';
                    downloadLink.onclick = (e) => {
                        e.preventDefault();
                        downloadBlob(fileBlob, fileInfo.fileName);
                    };
                    downloadLink.textContent = `下载 ${fileInfo.fileName}`;
                }
                
                showMessage('文件下载完成，可以保存了', 'success');
                showLoading(false);
                
                const receiveBtn = document.getElementById('receiveBtn');
                if (receiveBtn) {
                    receiveBtn.disabled = false;
                    receiveBtn.innerHTML = '<i class="icon-receive"></i> 领取';
                }
            },
            onError: (error) => {
                console.error('下载错误:', error);
                showMessage(`下载失败: ${error.message}`, 'error');
                showLoading(false);
                
                const receiveBtn = document.getElementById('receiveBtn');
                if (receiveBtn) {
                    receiveBtn.disabled = false;
                    receiveBtn.innerHTML = '<i class="icon-receive"></i> 领取';
                }
            }
        });
        
        // 通过服务器中转下载文件（使用端到端解密）
        // 密钥会自动从服务器获取，并使用取件码解密
        showLoading(true, '正在下载文件...');
        console.log('[Receiver] 开始下载文件（服务器中转模式）...');
        
        await receiverService.downloadFileViaRelay(code);
        
    } catch (error) {
        console.error('初始化ReceiverService失败:', error);
        
        // 检查是否是取件码过期错误
        if (error.code === 'EXPIRED') {
            showMessage('取件码已过期，无法使用', 'error');
            // 更新取件码显示为过期状态
            updatePickupCodeExpiredDisplay(code);
        } else if (error.code === 'COMPLETED') {
            showMessage('取件码已完成，无法使用', 'error');
        } else {
            showMessage(`接收失败: ${error.message}`, 'error');
        }
        
        showLoading(false);
        
        const receiveBtn = document.getElementById('receiveBtn');
        if (receiveBtn) {
            receiveBtn.disabled = false;
            receiveBtn.innerHTML = '<i class="icon-receive"></i> 领取';
        }
    }
}

// ========== 更新连接状态（已弃用，服务器中转模式不需要） ==========
// 此函数已不再使用，保留以防其他地方有引用
function updateConnectionStatus(role, state) {
    // 服务器中转模式不需要连接状态更新
    // 此函数保留仅为兼容性，实际不会被调用
}

// ========== 状态轮询 ==========
function startStatusPolling() {
    // 清除之前的轮询
    if (CONFIG.pollingInterval) {
        clearInterval(CONFIG.pollingInterval);
    }
    
    if (!CONFIG.pickupCode || !CONFIG.API_BASE) return;
    
    // 立即执行一次
    updateStatusFromServer();
    
    // 每2秒轮询一次状态
    CONFIG.pollingInterval = setInterval(() => {
        updateStatusFromServer();
    }, 2000);
}

// ========== 从服务器更新状态 ==========
async function updateStatusFromServer() {
    if (!CONFIG.pickupCode || !CONFIG.API_BASE) return;
    
    try {
        const response = await fetch(`${CONFIG.API_BASE}/v1/codes/${CONFIG.pickupCode}/status`);
        if (!response.ok) {
            return; // 静默失败，不显示错误
        }
        
        const result = await response.json();
        if (result.code === 200 && result.data) {
            updateStatusDisplayFromServer(result.data);
        }
    } catch (error) {
        console.warn('状态轮询失败:', error);
        // 静默失败，不影响用户体验
    }
}

// ========== 更新取件码过期显示 ==========
function updatePickupCodeExpiredDisplay(code) {
    const pickupCodeElement = document.getElementById('pickupCode');
    if (pickupCodeElement) {
        pickupCodeElement.textContent = code;
        pickupCodeElement.classList.add('expired');
    }
}

// ========== 从服务器数据更新状态显示 ==========
// 存储过期时间，用于实时倒计时
let CONFIG_EXPIRE_TIME = null;
let CONFIG_COUNTDOWN_INTERVAL = null;

function updateStatusDisplayFromServer(data) {
    const timeElement = document.getElementById('statTime');
    const sizeElement = document.getElementById('statSize');
    const countElement = document.getElementById('statCount');
    const statusElement = document.getElementById('statStatus');
    
    // 更新剩余时间
    if (timeElement && data.expireAt) {
        // 解析过期时间（支持 ISO 8601 格式，处理时区）
        let expireTime;
        try {
            // 处理时区问题：
            // 如果后端返回的时间没有时区标识（如 "2025-12-31T07:06:56"），
            // 我们需要假设它是 UTC 时间，因为后端使用的是 datetime.utcnow()
            let expireAtStr = String(data.expireAt);
            
            // 如果字符串没有时区标识（没有 Z 或 +/-），添加 Z 表示 UTC
            if (!expireAtStr.includes('Z') && !expireAtStr.match(/[+-]\d{2}:\d{2}$/)) {
                // 如果格式是 "YYYY-MM-DDTHH:mm:ss"，添加 "Z"
                if (expireAtStr.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/)) {
                    expireAtStr = expireAtStr + 'Z';
                }
            }
            
            expireTime = new Date(expireAtStr);
            
            // 验证日期是否有效
            if (isNaN(expireTime.getTime())) {
                console.warn('[倒计时] 无效的过期时间:', data.expireAt);
                timeElement.textContent = '--:--';
                return;
            }
            
            // 检查是否已过期
            const now = new Date();
            const isExpired = expireTime.getTime() <= now.getTime();
            
            // 保存过期时间，用于实时倒计时
            CONFIG_EXPIRE_TIME = expireTime;
            
            // 如果已过期，不创建定时器，直接显示过期状态
            if (isExpired) {
                if (timeElement) {
                    timeElement.textContent = '00:00';
                    timeElement.style.color = '#f72585';
                }
                // 清除可能存在的定时器
                if (CONFIG_COUNTDOWN_INTERVAL) {
                    clearInterval(CONFIG_COUNTDOWN_INTERVAL);
                    CONFIG_COUNTDOWN_INTERVAL = null;
                }
                return;
            }
            
            // 如果倒计时定时器不存在且未过期，启动它
            if (!CONFIG_COUNTDOWN_INTERVAL) {
                startCountdown();
            }
            
            // 立即更新一次
            updateCountdown();
        } catch (error) {
            console.error('[倒计时] 解析过期时间失败:', error, data.expireAt);
            timeElement.textContent = '--:--';
        }
    } else {
        console.warn('[倒计时] 缺少必要数据:', {
            hasTimeElement: !!timeElement,
            hasExpireAt: !!data.expireAt,
            expireAt: data.expireAt
        });
    }
    
    // 更新文件大小
    if (sizeElement && data.fileSize) {
        sizeElement.textContent = formatFileSize(data.fileSize);
    }
    
    // 更新领取状态
    if (countElement) {
        const limit = data.limitCount === 999 ? '∞' : data.limitCount;
        countElement.textContent = `${data.usedCount || 0}/${limit}`;
    }
    
    // 更新状态
    if (statusElement) {
        const statusMap = {
            'waiting': '等待中',
            'transferring': '传输中',
            'completed': '已完成',
            'expired': '已过期'
        };
        statusElement.textContent = statusMap[data.status] || data.status;
        
        // 根据状态改变颜色
        if (data.status === 'completed') {
            statusElement.style.color = '#4cc9f0';
        } else if (data.status === 'expired') {
            statusElement.style.color = '#f72585';
        } else if (data.status === 'transferring') {
            statusElement.style.color = '#4361ee';
        } else {
            statusElement.style.color = '#6c757d';
        }
    }
    
    // 如果取件码已过期，更新取件码显示样式
    if (data.status === 'expired') {
        const pickupCodeElement = document.getElementById('pickupCode');
        if (pickupCodeElement && data.code) {
            pickupCodeElement.textContent = data.code;
            pickupCodeElement.classList.add('expired');
        }
    } else {
        // 如果未过期，移除过期样式
        const pickupCodeElement = document.getElementById('pickupCode');
        if (pickupCodeElement) {
            pickupCodeElement.classList.remove('expired');
        }
    }
}

// ========== 实时倒计时 ==========
function startCountdown() {
    // 如果已有定时器，先清除
    if (CONFIG_COUNTDOWN_INTERVAL) {
        clearInterval(CONFIG_COUNTDOWN_INTERVAL);
        CONFIG_COUNTDOWN_INTERVAL = null;
    }
    
    // 检查是否已过期
    if (CONFIG_EXPIRE_TIME && CONFIG_EXPIRE_TIME.getTime() <= new Date().getTime()) {
        // 已过期，不创建定时器
        return;
    }
    
    // 每秒更新一次倒计时
    CONFIG_COUNTDOWN_INTERVAL = setInterval(() => {
        updateCountdown();
    }, 1000);
}

function updateCountdown() {
    const timeElement = document.getElementById('statTime');
    
    if (!timeElement) {
        return;
    }
    
    if (!CONFIG_EXPIRE_TIME) {
        return;
    }
    
    const now = new Date();
    const expireTimestamp = CONFIG_EXPIRE_TIME.getTime();
    const nowTimestamp = now.getTime();
    const diff = expireTimestamp - nowTimestamp;
    
    if (diff > 0) {
        const totalSeconds = Math.floor(diff / 1000);
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        const displayText = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        
        timeElement.textContent = displayText;
        
        // 少于5分钟变红色
        if (minutes < 5) {
            timeElement.style.color = '#f72585';
        } else {
            timeElement.style.color = '';
        }
    } else {
        // 已过期
        timeElement.textContent = '00:00';
        timeElement.style.color = '#f72585';
        
        // 清除倒计时定时器
        if (CONFIG_COUNTDOWN_INTERVAL) {
            clearInterval(CONFIG_COUNTDOWN_INTERVAL);
            CONFIG_COUNTDOWN_INTERVAL = null;
        }
    }
}

// 清理倒计时定时器
function stopCountdown() {
    if (CONFIG_COUNTDOWN_INTERVAL) {
        clearInterval(CONFIG_COUNTDOWN_INTERVAL);
        CONFIG_COUNTDOWN_INTERVAL = null;
    }
    CONFIG_EXPIRE_TIME = null;
}


// ========== 更新状态显示 ==========
function updateStatusDisplay() {
    // 这个方法保留用于初始化显示，实际数据从服务器获取
    const timeElement = document.getElementById('statTime');
    const sizeElement = document.getElementById('statSize');
    const countElement = document.getElementById('statCount');
    const statusElement = document.getElementById('statStatus');
    
    if (timeElement) timeElement.textContent = '--:--';
    if (sizeElement && CONFIG.localFile) {
        sizeElement.textContent = formatFileSize(CONFIG.localFile.size);
    }
    
    if (countElement) {
        const limitSelect = document.getElementById('limitSelect');
        const limit = limitSelect ? limitSelect.value : '3';
        countElement.textContent = `0/${limit === '999' ? '∞' : limit}`;
    }
    
    if (statusElement) {
        statusElement.textContent = '等待中';
        statusElement.style.color = '#4361ee';
    }
}

// ========== 端口测试处理器 ==========
async function testPortConnectionHandler() {
    const portInput = document.getElementById('portInput');
    const resultElement = document.getElementById('portResult');
    
    if (!portInput || !resultElement) return;
    
    const port = portInput.value;
    const host = location.hostname;
    
    resultElement.innerHTML = '<i class="icon-info"></i> 检测中...';
    resultElement.style.color = '#f8961e';
    
    showLoading(true, '测试端口连接...');
    
    try {
        const isConnected = await testPortConnection(host, port);
        
        if (isConnected) {
            CONFIG.API_BASE = `http://${host}:${port}/api`;
            resultElement.innerHTML = '<i class="icon-success"></i> 连接成功！';
            resultElement.style.color = '#4cc9f0';
            showMessage('端口连接成功，可以正常使用', 'success');
        } else {
            resultElement.innerHTML = '<i class="icon-error"></i> 连接失败';
            resultElement.style.color = '#f72585';
            showMessage('端口连接失败，请检查服务是否启动', 'error');
        }
    } catch (error) {
        resultElement.innerHTML = '<i class="icon-error"></i> 测试出错';
        resultElement.style.color = '#f72585';
        showMessage('测试过程中发生错误', 'error');
    } finally {
        showLoading(false);
    }
}

// ========== 自动测试端口 ==========
function autoTestPort() {
    setTimeout(() => {
        const testBtn = document.getElementById('testBtn');
        if (testBtn) {
            testBtn.click();
        }
    }, 1000);
}

// ========== 举报文件 ==========
function reportFile() {
    if (!CONFIG.pickupCode) {
        showMessage('请先生成取件码', 'error');
        return;
    }
    
    const reason = prompt('请输入举报原因（违规内容、侵权等）：\n\n注意：虚假举报可能会影响您的使用权限。');
    if (!reason || reason.trim() === '') return;
    
    showLoading(true, '提交举报中...');
    
    // 模拟提交过程
    setTimeout(() => {
        showLoading(false);
        showMessage('举报已提交，感谢您的反馈', 'success');
    }, 1500);
}

// ========== 状态保存与恢复 ==========
function saveCurrentState() {
    const state = {
        pickupCode: CONFIG.pickupCode,
        fileName: CONFIG.fileName,
        fileSize: CONFIG.fileSize,
        lastUpdated: new Date().toISOString()
    };
    
    try {
        localStorage.setItem('quickshare_state', JSON.stringify(state));
    } catch (e) {
        console.warn('状态保存失败:', e);
    }
}

function restorePreviousState() {
    try {
        const saved = localStorage.getItem('quickshare_state');
        if (saved) {
            const state = JSON.parse(saved);
            const now = new Date();
            const lastUpdated = new Date(state.lastUpdated);
            const hoursDiff = (now - lastUpdated) / (1000 * 60 * 60);
            
            // 只恢复24小时内的状态
            if (hoursDiff < 24 && state.pickupCode) {
                CONFIG.pickupCode = state.pickupCode;
                CONFIG.fileName = state.fileName;
                CONFIG.fileSize = state.fileSize;
                
                // 恢复显示
                const pickupCodeElement = document.getElementById('pickupCode');
                
                if (pickupCodeElement) {
                    pickupCodeElement.textContent = CONFIG.pickupCode;
                    updateStatusDisplay();
                    
                    // 恢复状态时也需要获取最新状态并启动倒计时
                    updateStatusFromServer().then(() => {
                        startStatusPolling();
                    });
                    
                    showMessage('已恢复上次的分享状态', 'info');
                    // 注意：恢复状态时不自动打开弹窗，用户需要点击侧边栏按钮
                }
            }
        }
    } catch (e) {
        console.warn('状态恢复失败:', e);
    }
}

// ========== 添加返回按钮 ==========
function addBackButton() {
    // 在页脚添加返回欢迎页的链接
    const footer = document.querySelector('.app-footer');
    if (footer) {
        const backLink = document.createElement('a');
        backLink.href = '/static/pages/welcome.html';
        backLink.textContent = '← 返回欢迎页';
        backLink.style.cssText = `
            display: inline-block;
            margin-top: 10px;
            color: #4361ee;
            text-decoration: none;
            font-size: 0.9rem;
        `;
        
        backLink.addEventListener('mouseenter', function() {
            this.style.textDecoration = 'underline';
        });
        
        backLink.addEventListener('mouseleave', function() {
            this.style.textDecoration = 'none';
        });
        
        footer.appendChild(document.createElement('br'));
        footer.appendChild(backLink);
    }
}

// ========== 弹窗控制函数 ==========
// 注意：openModal 和 closeModal 已从 modal.js 模块导入，这里不再重复定义
// 如果 modal.js 加载失败，这里保留备用实现
if (typeof openModal === 'undefined') {
    window.openModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'flex';
            modal.style.alignItems = 'center';
            modal.style.justifyContent = 'center';
            modal.style.visibility = 'visible';
            modal.style.opacity = '1';
            modal.style.background = 'rgba(0, 0, 0, 0.6)';
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    };
    
    window.closeModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
            modal.style.visibility = 'hidden';
            modal.style.opacity = '0';
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    };
}

// ========== 页面卸载清理 ==========
window.addEventListener('beforeunload', function() {
    if (CONFIG.pollingInterval) {
        clearInterval(CONFIG.pollingInterval);
    }
    stopCountdown(); // 清理倒计时定时器
});

// ========== 导出配置供其他模块使用 ==========
export { CONFIG };