/**
 * 通用工具函数
 * 负责 UI、验证、存储、网络、日期时间等通用功能
 */

// ========== UI 工具 ==========

/**
 * 显示确认对话框
 * @param {string} title - 标题
 * @param {string} message - 消息内容
 * @param {string} confirmText - 确认按钮文字
 * @param {string} cancelText - 取消按钮文字
 * @returns {Promise<boolean>} 用户选择（true=确认，false=取消）
 */
export function showConfirmDialog(title, message, confirmText = '确认', cancelText = '取消') {
    return new Promise((resolve) => {
        // 创建遮罩层
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;

        // 创建对话框
        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: white;
            border-radius: 12px;
            padding: 24px;
            max-width: 500px;
            width: 90%;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            animation: slideIn 0.3s ease;
        `;

        dialog.innerHTML = `
            <h3 style="margin: 0 0 16px 0; font-size: 1.3rem; color: #212529;">${title}</h3>
            <p style="margin: 0 0 24px 0; color: #6c757d; line-height: 1.6; white-space: pre-line;">${message}</p>
            <div style="display: flex; gap: 12px; justify-content: flex-end;">
                <button class="cancel-btn" style="
                    padding: 10px 20px;
                    border: 2px solid #dee2e6;
                    background: white;
                    color: #6c757d;
                    border-radius: 8px;
                    cursor: pointer;
                    font-weight: 600;
                    transition: all 0.2s;
                ">${cancelText}</button>
                <button class="confirm-btn" style="
                    padding: 10px 20px;
                    border: none;
                    background: linear-gradient(135deg, #4361ee, #7209b7);
                    color: white;
                    border-radius: 8px;
                    cursor: pointer;
                    font-weight: 600;
                    transition: all 0.2s;
                ">${confirmText}</button>
            </div>
        `;

        // 添加按钮样式
        const confirmBtn = dialog.querySelector('.confirm-btn');
        const cancelBtn = dialog.querySelector('.cancel-btn');

        confirmBtn.onmouseover = () => {
            confirmBtn.style.transform = 'translateY(-2px)';
            confirmBtn.style.boxShadow = '0 6px 20px rgba(67, 97, 238, 0.3)';
        };
        confirmBtn.onmouseout = () => {
            confirmBtn.style.transform = '';
            confirmBtn.style.boxShadow = '';
        };

        cancelBtn.onmouseover = () => {
            cancelBtn.style.background = '#f8f9fa';
        };
        cancelBtn.onmouseout = () => {
            cancelBtn.style.background = 'white';
        };

        // 事件处理
        const handleConfirm = () => {
            document.body.removeChild(overlay);
            resolve(true);
        };

        const handleCancel = () => {
            document.body.removeChild(overlay);
            resolve(false);
        };

        confirmBtn.onclick = handleConfirm;
        cancelBtn.onclick = handleCancel;
        overlay.onclick = (e) => {
            if (e.target === overlay) {
                handleCancel();
            }
        };

        dialog.appendChild(confirmBtn);
        dialog.appendChild(cancelBtn);
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);
    });
}

/**
 * 显示消息提示
 * @param {string} message 消息内容
 * @param {string} type 消息类型：success, error, info, warning
 * @param {number} duration 显示时长（毫秒）
 */
export function showMessage(message, type = 'info', duration = 3000) {
    // 移除可能已存在的消息
    const existingMsg = document.querySelector('.quick-share-message');
    if (existingMsg) {
        document.body.removeChild(existingMsg);
    }
    
    // 创建消息元素
    const messageEl = document.createElement('div');
    messageEl.className = `quick-share-message message-${type}`;
    messageEl.textContent = message;
    
    // 样式配置
    const typeColors = {
        success: '#4cc9f0',
        error: '#f72585',
        warning: '#f8961e',
        info: '#4361ee'
    };
    
    messageEl.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 14px 24px;
        border-radius: 8px;
        background: ${typeColors[type] || typeColors.info};
        color: white;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
        z-index: 9999;
        animation: slideIn 0.3s ease;
        font-weight: 500;
        max-width: 400px;
        word-break: break-word;
    `;
    
    document.body.appendChild(messageEl);
    
    // 自动移除
    setTimeout(() => {
        messageEl.style.opacity = '0';
        messageEl.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            if (messageEl.parentNode) {
                document.body.removeChild(messageEl);
            }
        }, 300);
    }, duration);
}

/**
 * 显示/隐藏加载动画
 * @param {boolean} show 是否显示
 * @param {string} text 加载文字
 */
export function showLoading(show = true, text = '加载中...') {
    let loader = document.getElementById('quick-share-loader');
    
    if (show) {
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'quick-share-loader';
            loader.innerHTML = `
                <div class="loader-spinner"></div>
                <div class="loader-text">${text}</div>
            `;
            
            loader.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(255, 255, 255, 0.9);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                z-index: 9999;
            `;
            
            const spinnerStyle = document.createElement('style');
            spinnerStyle.textContent = `
                .loader-spinner {
                    width: 50px;
                    height: 50px;
                    border: 4px solid #f3f3f3;
                    border-top: 4px solid #4361ee;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin-bottom: 15px;
                }
                .loader-text {
                    color: #333;
                    font-size: 1rem;
                }
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            `;
            document.head.appendChild(spinnerStyle);
            
            document.body.appendChild(loader);
        }
    } else if (loader) {
        document.body.removeChild(loader);
    }
}

// ========== 验证工具 ==========

/**
 * 验证取件码格式
 * @param {string} code 取件码
 * @returns {boolean} 是否有效
 */
export function isValidPickupCode(code) {
    return /^[A-Z0-9]{12}$/.test(code);
}

/**
 * 验证端口号
 * @param {number|string} port 端口号
 * @returns {boolean} 是否有效
 */
export function isValidPort(port) {
    const portNum = parseInt(port);
    return !isNaN(portNum) && portNum > 0 && portNum <= 65535;
}

/**
 * 生成取件码
 * @returns {string} 12位取件码（前6位查找码+后6位密钥码）
 */
export function generatePickupCode() {
    return Array.from({length: 12}, () => 
        '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'[Math.floor(Math.random() * 36)]
    ).join('');
}

/**
 * 生成唯一会话ID（用于 WebRTC 会话标识）
 * @returns {string} 会话ID
 */
export function generateSessionId() {
    return 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// ========== 日期时间工具 ==========

/**
 * 格式化剩余时间
 * @param {number} milliseconds 毫秒数
 * @returns {string} 格式化的时间 (MM:SS)
 */
export function formatRemainingTime(milliseconds) {
    const totalSeconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

/**
 * 获取未来时间
 * @param {number} minutes 增加的分钟数
 * @returns {Date} 未来的时间
 */
export function getFutureTime(minutes) {
    const now = new Date();
    return new Date(now.getTime() + minutes * 60000);
}

// ========== 存储工具 ==========

/**
 * 保存数据到 localStorage
 * @param {string} key 键名
 * @param {any} data 数据
 */
export function saveToStorage(key, data) {
    try {
        localStorage.setItem(`quickshare_${key}`, JSON.stringify(data));
    } catch (e) {
        console.warn('localStorage 存储失败:', e);
    }
}

/**
 * 从 localStorage 读取数据
 * @param {string} key 键名
 * @returns {any} 数据
 */
export function loadFromStorage(key) {
    try {
        const data = localStorage.getItem(`quickshare_${key}`);
        return data ? JSON.parse(data) : null;
    } catch (e) {
        console.warn('localStorage 读取失败:', e);
        return null;
    }
}

/**
 * 清空相关存储
 */
export function clearStorage() {
    const keys = [];
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('quickshare_')) {
            keys.push(key);
        }
    }
    keys.forEach(key => localStorage.removeItem(key));
}

// ========== 网络工具 ==========

/**
 * 测试端口连接
 * @param {string} host 主机地址
 * @param {number} port 端口号
 * @returns {Promise<boolean>} 是否连通
 */
export async function testPortConnection(host, port) {
    try {
        // 检测当前页面的协议（HTTPS或HTTP），使用相同的协议避免混合内容错误
        const protocol = typeof window !== 'undefined' && window.location 
            ? window.location.protocol 
            : 'http:';
        
        // 使用健康检查端点
        const url = `${protocol}//${host}:${port}/health`;
        const response = await fetch(url, {
            method: 'GET',
            mode: 'cors',
            cache: 'no-cache',
            headers: {
                'Accept': 'application/json'
            }
        });
        return response.ok;
    } catch (error) {
        console.warn('端口测试失败:', error);
        return false;
    }
}

/**
 * 带超时的 fetch
 * @param {string} url 请求URL
 * @param {object} options fetch选项
 * @param {number} timeout 超时时间（毫秒）
 * @returns {Promise<Response>} 响应
 */
export function fetchWithTimeout(url, options = {}, timeout = 10000) {
    return Promise.race([
        fetch(url, options),
        new Promise((_, reject) =>
            setTimeout(() => reject(new Error('请求超时')), timeout)
        )
    ]);
}

