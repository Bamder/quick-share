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

// 导入 WebRTC 服务（使用导出的单例实例）
import { senderService as importedSenderService } from '/static/service/sender-service.js';
import { receiverService as importedReceiverService } from '/static/service/receiver-service.js';

// 配置信息
const CONFIG = {
    API_BASE: '',
    localFile: null,
    pickupCode: '',
    fileSize: 0,
    fileName: '',
    pollingInterval: null
};

// WebRTC 服务实例（使用导入的单例）
const senderService = importedSenderService;
const receiverService = importedReceiverService;

// ========== 初始化函数 ==========
document.addEventListener('DOMContentLoaded', function() {
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
        // 获取配置选项
        const expireSelect = document.getElementById('expireSelect');
        const limitSelect = document.getElementById('limitSelect');
        const expireHours = expireSelect ? parseInt(expireSelect.value) / 60 : 24; // 转换为小时
        const limitCount = limitSelect ? parseInt(limitSelect.value) : 3;
        
        // 计算文件哈希（可选，这里先不实现）
        // const fileHash = await calculateFileHash(CONFIG.localFile);
        
        // 调用后端 API 创建文件和取件码
        const response = await fetch(`${CONFIG.API_BASE}/v1/codes`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                originalName: CONFIG.localFile.name,
                size: CONFIG.localFile.size,
                mimeType: CONFIG.localFile.type || null,
                hash: null, // 可选，暂时不计算
                limitCount: limitCount,
                expireHours: expireHours
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
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
        
        // 显示取件码区域
        const codeSection = document.getElementById('codeSec');
        const pickupCodeElement = document.getElementById('pickupCode');
        
        if (codeSection && pickupCodeElement) {
            pickupCodeElement.textContent = CONFIG.pickupCode;
            codeSection.style.display = 'block';
            
            // 滚动到取件码区域（移动端优化）
            codeSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
    
    navigator.clipboard.writeText(CONFIG.pickupCode)
        .then(() => showMessage('取件码已复制到剪贴板', 'success'))
        .catch(() => {
            // 降级方案
            const textArea = document.createElement('textarea');
            textArea.value = CONFIG.pickupCode;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            showMessage('取件码已复制', 'success');
        });
}

// ========== 接收文件 ==========
async function receiveFile() {
    const inputCode = document.getElementById('inputCode');
    if (!inputCode) return;
    
    const code = inputCode.value.trim().toUpperCase();
    
    if (!isValidPickupCode(code)) {
        showMessage('请输入6位有效的取件码', 'error');
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

// ========== 初始化 SenderService ==========
async function initializeSenderService() {
    if (!CONFIG.API_BASE || !CONFIG.pickupCode) {
        return;
    }
    
    try {
        // 创建 SenderService 实例
        senderService = new SenderService();
        
        // 初始化服务
        senderService.init(`${CONFIG.API_BASE}/v1`, {
            onConnectionStateChange: (state) => {
                console.log('Sender连接状态变更:', state);
                updateConnectionStatus('sender', state);
            },
            onDataChannelOpen: () => {
                console.log('数据通道已打开，准备发送文件');
                showMessage('连接已建立，等待接收方准备...', 'info');
            },
            onProgress: (sent, total) => {
                const progress = Math.floor((sent / total) * 100);
                console.log(`发送进度: ${progress}%`);
                // 可以在这里更新发送进度显示（如果需要）
            },
            onComplete: () => {
                console.log('文件发送完成');
                showMessage('文件已成功发送', 'success');
            },
            onError: (error) => {
                console.error('Sender错误:', error);
                showMessage(`发送失败: ${error.message}`, 'error');
            }
        });
        
        // 注册 Sender
        await senderService.registerSender(CONFIG.pickupCode);
        console.log('Sender注册成功，等待Receiver连接...');
        
        // 开始自动等待 Offer
        startWaitingForOffer();
        
    } catch (error) {
        console.error('初始化SenderService失败:', error);
        showMessage(`初始化发送服务失败: ${error.message}`, 'error');
    }
}

// ========== 自动等待 Offer ==========
async function startWaitingForOffer() {
    if (!CONFIG.API_BASE || !CONFIG.pickupCode || !CONFIG.localFile) {
        return;
    }
    
    console.log('开始轮询等待Receiver的Offer...');
    showMessage('等待接收方连接...', 'info');
    
    const maxAttempts = 120; // 最多等待2分钟（120次 * 1秒）
    const interval = 1000; // 每秒查询一次
    
    for (let i = 0; i < maxAttempts; i++) {
        try {
            // 查询活跃的会话列表
            const response = await fetch(
                `${CONFIG.API_BASE}/v1/codes/${CONFIG.pickupCode}/webrtc/sessions?status=offer_created`
            );
            
            if (response.ok) {
                const result = await response.json();
                
                if (result.code === 200 && result.data && result.data.sessions) {
                    const sessions = result.data.sessions;
                    
                    // 查找有 Offer 且未过期的会话
                    const activeSession = sessions.find(s => 
                        s.hasOffer && 
                        !s.isExpired && 
                        s.status === 'offer_created'
                    );
                    
                    if (activeSession) {
                        console.log('找到活跃会话:', activeSession.sessionId);
                        showMessage('发现接收方连接，正在建立连接...', 'info');
                        
                        // 获取 Offer 并创建 Answer
                        await handleReceiverOffer(activeSession.sessionId);
                        return; // 成功，退出轮询
                    }
                }
            }
            
            // 等待后继续轮询
            await new Promise(resolve => setTimeout(resolve, interval));
            
            // 每10次显示一次进度
            if (i % 10 === 0 && i > 0) {
                console.log(`等待中... (${i}/${maxAttempts})`);
            }
            
        } catch (error) {
            console.error(`轮询会话列表失败 (尝试 ${i + 1}/${maxAttempts}):`, error);
            await new Promise(resolve => setTimeout(resolve, interval));
        }
    }
    
    // 超时
    console.warn('等待Offer超时');
    showMessage('等待接收方连接超时，请检查取件码是否正确分享', 'warning');
}

// ========== 处理 Receiver 的 Offer ==========
async function handleReceiverOffer(sessionId) {
    try {
        // 使用 SenderService 获取 Offer 并创建 Answer
        const offer = await senderService.waitForOffer(sessionId, 10, 500); // 最多等待5秒
        
        // 接收 Offer 并创建 Answer
        await senderService.receiveOfferAndCreateAnswer(
            CONFIG.pickupCode,
            sessionId,
            offer
        );
        
        console.log('Answer已创建，等待连接建立...');
        showMessage('连接已建立，准备发送文件...', 'info');
        
        // 等待数据通道打开后自动发送文件
        const originalOnDataChannelOpen = senderService.onDataChannelOpen;
        senderService.onDataChannelOpen = () => {
            // 调用原始回调
            if (originalOnDataChannelOpen) {
                originalOnDataChannelOpen();
            }
            
            // 数据通道打开后，自动开始发送文件
            if (CONFIG.localFile) {
                console.log('数据通道已打开，开始发送文件...');
                senderService.startSendingFile(CONFIG.localFile)
                    .then(() => {
                        console.log('文件发送完成');
                    })
                    .catch((error) => {
                        console.error('文件发送失败:', error);
                        showMessage(`文件发送失败: ${error.message}`, 'error');
                    });
            }
        };
        
    } catch (error) {
        console.error('处理Offer失败:', error);
        showMessage(`连接失败: ${error.message}`, 'error');
    }
}

// ========== 初始化 ReceiverService ==========
async function initializeReceiverService(code, fileInfo) {
    if (!CONFIG.API_BASE) {
        return;
    }
    
    try {
        // 创建 ReceiverService 实例
        receiverService = new ReceiverService();
        
        // 显示文件信息
        const progressBar = document.getElementById('recvProgressBar');
        const progressFill = document.querySelector('.progress-fill');
        const progressPercent = document.getElementById('progressPercent');
        
        if (progressBar) {
            progressBar.style.display = 'block';
        }
        
        // 初始化服务
        receiverService.init(`${CONFIG.API_BASE}/v1`, {
            onConnectionStateChange: (state) => {
                console.log('Receiver连接状态变更:', state);
                updateConnectionStatus('receiver', state);
            },
            onDataChannelOpen: () => {
                console.log('数据通道已打开，开始接收文件');
                showMessage('连接已建立，开始接收文件...', 'info');
            },
            onDataChannelMessage: (event) => {
                // 进度更新由服务内部处理
            },
            onDataChannelClose: () => {
                console.log('数据通道已关闭');
            },
            onError: (error) => {
                console.error('Receiver错误:', error);
                showMessage(`接收失败: ${error.message}`, 'error');
                showLoading(false);
            }
        });
        
        // 保存原始回调
        const originalOnMessage = receiverService.onDataChannelMessage;
        
        // 设置自定义回调来处理文件接收完成和进度更新
        receiverService.onDataChannelMessage = (event) => {
            // 如果是文件完成事件（从 reconstructFile 触发）
            if (event && typeof event === 'object' && event.type === 'fileComplete') {
                const fileBlob = event.file;
                const fileName = event.fileName;
                
                console.log('文件接收完成:', fileName);
                
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
                        downloadBlob(fileBlob, fileName);
                    };
                    downloadLink.textContent = `下载 ${fileName}`;
                }
                
                showMessage('文件接收完成，可以下载了', 'success');
                showLoading(false);
                
                const receiveBtn = document.getElementById('receiveBtn');
                if (receiveBtn) {
                    receiveBtn.disabled = false;
                    receiveBtn.innerHTML = '<i class="icon-receive"></i> 领取';
                }
            } else {
                // 调用原始处理函数（处理正常的消息事件）
                if (originalOnMessage) {
                    originalOnMessage(event);
                }
                
                // 更新进度（从 receivedChunks 计算）
                if (receiverService.fileInfo && receiverService.receivedChunks) {
                    const receivedCount = receiverService.receivedChunks.filter(chunk => chunk !== undefined).length;
                    const total = receiverService.fileInfo.totalChunks;
                    if (total > 0) {
                        const progress = Math.floor((receivedCount / total) * 100);
                        
                        if (progressFill) {
                            progressFill.style.width = `${progress}%`;
                        }
                        if (progressPercent) {
                            progressPercent.textContent = `${progress}%`;
                        }
                    }
                }
            }
        };
        
        // 创建 Offer 并开始连接
        showLoading(true, '正在建立连接...');
        const sessionId = await receiverService.createOffer(code);
        console.log('Receiver创建Offer成功，sessionId:', sessionId);
        
        // 等待 Answer（服务内部会自动处理）
        await receiverService.waitForAnswer();
        
    } catch (error) {
        console.error('初始化ReceiverService失败:', error);
        showMessage(`接收失败: ${error.message}`, 'error');
        showLoading(false);
        
        const receiveBtn = document.getElementById('receiveBtn');
        if (receiveBtn) {
            receiveBtn.disabled = false;
            receiveBtn.innerHTML = '<i class="icon-receive"></i> 领取';
        }
    }
}

// ========== 更新连接状态 ==========
function updateConnectionStatus(role, state) {
    const statusElement = document.getElementById('statStatus');
    if (!statusElement) return;
    
    const statusMap = {
        'new': '新建',
        'connecting': '连接中',
        'connected': '已连接',
        'disconnected': '已断开',
        'failed': '连接失败',
        'closed': '已关闭'
    };
    
    statusElement.textContent = statusMap[state] || state;
    
    // 根据状态改变颜色
    if (state === 'connected') {
        statusElement.style.color = '#4cc9f0';
    } else if (state === 'failed' || state === 'closed') {
        statusElement.style.color = '#f72585';
    } else {
        statusElement.style.color = '#4361ee';
    }
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

// ========== 从服务器数据更新状态显示 ==========
function updateStatusDisplayFromServer(data) {
    const timeElement = document.getElementById('statTime');
    const sizeElement = document.getElementById('statSize');
    const countElement = document.getElementById('statCount');
    const statusElement = document.getElementById('statStatus');
    
    // 更新剩余时间
    if (timeElement && data.expireAt) {
        const expireTime = new Date(data.expireAt);
        const now = new Date();
        const diff = expireTime - now;
        
        if (diff > 0) {
            const minutes = Math.floor(diff / 60000);
            const seconds = Math.floor((diff % 60000) / 1000);
            timeElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            
            // 少于5分钟变红色
            if (minutes < 5) {
                timeElement.style.color = '#f72585';
            } else {
                timeElement.style.color = '';
            }
        } else {
            timeElement.textContent = '00:00';
            timeElement.style.color = '#f72585';
        }
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
                const codeSection = document.getElementById('codeSec');
                const pickupCodeElement = document.getElementById('pickupCode');
                
                if (codeSection && pickupCodeElement) {
                    pickupCodeElement.textContent = CONFIG.pickupCode;
                    codeSection.style.display = 'block';
                    updateStatusDisplay();
                    startStatusPolling();
                    
                    showMessage('已恢复上次的分享状态', 'info');
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

// ========== 页面卸载清理 ==========
window.addEventListener('beforeunload', function() {
    if (CONFIG.pollingInterval) {
        clearInterval(CONFIG.pollingInterval);
    }
});

// ========== 导出配置供其他模块使用 ==========
export { CONFIG };