/**
 * 主页面逻辑
 */

// 导入工具函数
import {
    formatFileSize,
    getFileIcon,
    showMessage,
    showLoading,
    isValidPickupCode,
    generatePickupCode,
    formatRemainingTime,
    testPortConnection
} from '/static/utils/utils.js';

// 配置信息
const CONFIG = {
    API_BASE: '',
    localFile: null,
    pickupCode: '',
    fileSize: 0,
    fileName: '',
    pollingInterval: null
};

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
function generatePickupCodeHandler() {
    if (!CONFIG.localFile) {
        showMessage('请先选择文件', 'error');
        return;
    }
    
    // 生成取件码
    CONFIG.pickupCode = generatePickupCode();
    
    // 显示取件码区域
    const codeSection = document.getElementById('codeSec');
    const pickupCodeElement = document.getElementById('pickupCode');
    
    if (codeSection && pickupCodeElement) {
        pickupCodeElement.textContent = CONFIG.pickupCode;
        codeSection.style.display = 'block';
        
        // 滚动到取件码区域（移动端优化）
        codeSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    // 更新状态显示
    updateStatusDisplay();
    
    // 开始轮询状态
    startStatusPolling();
    
    // 保存状态
    saveCurrentState();
    
    showMessage('取件码已生成，分享给朋友吧！', 'success');
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
        // 这里应该是实际的API调用
        // const response = await fetch(`${CONFIG.API_BASE}/receive?code=${code}`);
        // const result = await response.json();
        
        // 模拟API调用延迟
        await new Promise(resolve => setTimeout(resolve, 1500));
        
        // 模拟接收过程
        simulateFileReceive();
        
    } catch (error) {
        showMessage('连接失败，请重试', 'error');
    } finally {
        showLoading(false);
        if (receiveBtn) {
            receiveBtn.disabled = false;
            receiveBtn.innerHTML = '<i class="icon-receive"></i> 领取';
        }
    }
}

// ========== 模拟文件接收 ==========
function simulateFileReceive() {
    const progressBar = document.getElementById('recvProgressBar');
    const progressFill = document.querySelector('.progress-fill');
    const progressPercent = document.getElementById('progressPercent');
    
    if (progressBar) {
        progressBar.style.display = 'block';
    }
    
    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 15 + 5;
        if (progress >= 100) {
            progress = 100;
            clearInterval(interval);
            
            // 显示下载链接
            setTimeout(() => {
                const downloadLink = document.getElementById('downloadLink');
                if (downloadLink) {
                    downloadLink.style.display = 'block';
                    downloadLink.href = '#';
                    downloadLink.download = '示例文件.txt';
                    
                    showMessage('文件准备就绪，点击下载', 'success');
                }
            }, 500);
        }
        
        if (progressFill) {
            progressFill.style.width = `${progress}%`;
        }
        if (progressPercent) {
            progressPercent.textContent = `${Math.floor(progress)}%`;
        }
    }, 300);
}

// ========== 状态轮询 ==========
function startStatusPolling() {
    // 清除之前的轮询
    if (CONFIG.pollingInterval) {
        clearInterval(CONFIG.pollingInterval);
    }
    
    if (!CONFIG.pickupCode || !CONFIG.API_BASE) return;
    
    // 模拟状态更新（实际项目中应该调用API）
    CONFIG.pollingInterval = setInterval(() => {
        updateMockStatus();
    }, 2000);
}

// ========== 模拟状态更新 ==========
function updateMockStatus() {
    const timeElement = document.getElementById('statTime');
    const countElement = document.getElementById('statCount');
    const statusElement = document.getElementById('statStatus');
    
    if (!timeElement || !countElement || !statusElement) return;
    
    // 更新时间
    const currentTime = timeElement.textContent.split(':');
    let minutes = parseInt(currentTime[0]) || 30;
    let seconds = parseInt(currentTime[1]) || 0;
    
    if (seconds > 0) {
        seconds--;
    } else {
        if (minutes > 0) {
            minutes--;
            seconds = 59;
        }
    }
    
    timeElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    
    // 更新时间颜色（少于5分钟变红色）
    if (minutes < 5) {
        timeElement.style.color = '#f72585';
    }
    
    // 随机更新领取次数（模拟）
    if (Math.random() < 0.05) {
        const [used, limit] = countElement.textContent.split('/').map(Number);
        if (used < limit || limit === 999) {
            const newUsed = limit === 999 ? used + 1 : Math.min(used + 1, limit);
            countElement.textContent = `${newUsed}/${limit === 999 ? '∞' : limit}`;
        }
    }
    
    // 更新状态
    if (Math.random() < 0.03) {
        const statuses = ['等待中', '进行中', '已完成'];
        const newStatus = statuses[Math.floor(Math.random() * statuses.length)];
        statusElement.textContent = newStatus;
        
        // 根据状态改变颜色
        statusElement.style.color = 
            newStatus === '已完成' ? '#4cc9f0' : 
            newStatus === '进行中' ? '#4361ee' : '#6c757d';
    }
    
    // 检查是否过期
    if (minutes === 0 && seconds === 0) {
        statusElement.textContent = '已过期';
        statusElement.style.color = '#f72585';
        if (CONFIG.pollingInterval) {
            clearInterval(CONFIG.pollingInterval);
        }
    }
}

// ========== 更新状态显示 ==========
function updateStatusDisplay() {
    const timeElement = document.getElementById('statTime');
    const sizeElement = document.getElementById('statSize');
    const countElement = document.getElementById('statCount');
    const statusElement = document.getElementById('statStatus');
    
    if (timeElement) timeElement.textContent = '30:00';
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
        backLink.href = '../pages/welcome.html';
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