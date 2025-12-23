/**
 * QuickShare 通用工具函数
 * 所有页面通用的工具方法放在这里
 */

// ========== 文件处理工具 ==========

/**
 * 格式化文件大小
 * @param {number} bytes 文件大小（字节）
 * @returns {string} 格式化后的文件大小
 */
export function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 根据文件扩展名获取图标
 * @param {string} filename 文件名
 * @returns {string} 对应的emoji图标
 */
export function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
        pdf: '📕', doc: '📄', docx: '📄', txt: '📝',
        xls: '📊', xlsx: '📊', ppt: '📽️', pptx: '📽️',
        zip: '📦', rar: '📦', '7z': '📦', tar: '📦',
        mp3: '🎵', wav: '🎵', flac: '🎵',
        mp4: '🎬', avi: '🎬', mov: '🎬', mkv: '🎬',
        jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️',
        svg: '🖼️', webp: '🖼️',
        exe: '⚙️', msi: '⚙️',
        dmg: '💿', iso: '💿'
    };
    return icons[ext] || '📁';
}

// ========== UI 工具 ==========

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
 * 加载动画
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
    return /^[A-Z0-9]{6}$/.test(code);
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
 * @returns {string} 6位取件码
 */
export function generatePickupCode() {
    return Array.from({length: 6}, () => 
        '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'[Math.floor(Math.random() * 36)]
    ).join('');
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
        if (key.startsWith('quickshare_')) {
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
        const url = `http://${host}:${port}/api/status`;
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