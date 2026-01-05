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
    testPortConnection,
    showConfirmDialog
} from '/static/utils/common-utils.js';
import { cleanupExpiredKeys, getKeyFromCache, storeKeyInCache, removeKeyFromCache, storePickupCodeInCache, getPickupCodeFromCache, removePickupCodeFromCache } from '/static/utils/key-cache.js';

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
    fileId: null,  // 文件ID（用于作废功能）
    fileHash: null,  // 文件哈希（用于密钥缓存）
    expireHours: 24,  // 过期时间（小时，用于密钥缓存）
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
    // 清理过期的密钥缓存
    cleanupExpiredKeys();
    
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
    
    // 作废文件记录按钮
    const invalidateBtn = document.getElementById('invalidateBtn');
    if (invalidateBtn) {
        invalidateBtn.onclick = async function() {
            if (!CONFIG.fileId) {
                showMessage('没有可作废的文件记录', 'warning');
                return;
            }
            
            const confirmed = await showConfirmDialog(
                '确认作废',
                `确定要作废文件 "${CONFIG.fileName}" 的所有取件码吗？\n\n此操作不可逆，所有取件码将立即失效。`,
                '确认作废',
                '取消'
            );
            
            if (confirmed) {
                // 先撤销上传完成的提示
                clearUploadCompleteUI();
                
                try {
                    await invalidateFileRecord(CONFIG.fileId);
                    // 删除缓存的密钥
                    if (CONFIG.fileHash) {
                        removeKeyFromCache(CONFIG.fileHash);
                    }
                    showMessage('文件记录已作废，所有取件码已失效', 'success');
                    // 隐藏作废按钮
                    invalidateBtn.style.display = 'none';
                    // 重置CONFIG
                    CONFIG.fileId = null;
                    CONFIG.fileHash = null;
                    CONFIG.pickupCode = '';
                    CONFIG.fileName = '';
                    CONFIG.fileSize = 0;
                } catch (error) {
                    showMessage(`作废失败: ${error.message}`, 'error');
                }
            }
        };
    }
    
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
        // 计算文件哈希（用于文件去重和密钥缓存）
        try {
            const { calculateFileHash } = await import('/static/utils/encryption-utils.js');
            CONFIG.fileHash = await calculateFileHash(CONFIG.localFile);
            requestData.hash = CONFIG.fileHash;
            console.log('文件哈希计算完成:', CONFIG.fileHash.substring(0, 16) + '...');
        } catch (error) {
            console.warn('计算文件哈希失败，将使用文件名+大小进行去重:', error);
            CONFIG.fileHash = null;
            // 如果哈希计算失败，不传递hash，后端将使用文件名+大小进行去重
        }
        
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
                console.error('错误响应状态码:', response.status);
                console.error('错误响应data:', errorData.data);
                console.error('错误响应完整结构:', JSON.stringify(errorData, null, 2));
            } catch (e) {
                console.error('解析错误响应失败:', e);
            }
            
            // 处理文件已存在的情况
            // 检查错误码是否为 FILE_ALREADY_EXISTS
            if (response.status === 400) {
                // 检查 errorData.data.code 或 errorData.code
                const errorCode = errorData.data?.code || errorData.code;
                console.log('检查错误码:', errorCode, '是否为 FILE_ALREADY_EXISTS:', errorCode === 'FILE_ALREADY_EXISTS');
                console.log('errorData.data:', errorData.data);
                console.log('errorData.data?.code:', errorData.data?.code);
                console.log('errorData.code:', errorData.code);
                
                // 尝试多种方式匹配错误码
                const isFileExists = errorCode === 'FILE_ALREADY_EXISTS' || 
                                   errorData.data?.code === 'FILE_ALREADY_EXISTS' ||
                                   (errorData.msg && errorData.msg.includes('已创建过未过期的取件码'));
                
                console.log('是否匹配文件已存在错误:', isFileExists);
                
                if (isFileExists) {
                    // 检查是否有密钥缓存和取件码缓存
                    const hasCachedKey = requestData.hash ? getKeyFromCache(requestData.hash) !== null : false;
                    const oldPickupCode = requestData.hash ? getPickupCodeFromCache(requestData.hash) : null;
                    console.log('密钥缓存检查:', { hasCachedKey, fileHash: requestData.hash ? requestData.hash.substring(0, 16) + '...' : null, oldPickupCode: oldPickupCode ? oldPickupCode.substring(0, 6) + '****' : null });
                    
                    let dialogTitle, dialogMessage, confirmText;
                    if (hasCachedKey && oldPickupCode) {
                        // 有缓存密钥和旧取件码，可以复用旧密钥重新生成取件码
                        dialogTitle = '文件已存在';
                        dialogMessage = `该文件已创建过未过期的取件码（旧取件码: ${oldPickupCode}）。\n\n选择操作：\n• 重新生成（复用旧文件密钥）：无需重新上传文件，旧的取件码仍然可以下载\n• 取消：不进行任何操作`;
                        confirmText = '重新生成（复用旧文件密钥）';
                    } else {
                        // 没有缓存密钥或旧取件码，需要作废旧文件记录
                        dialogTitle = '文件已存在但密钥丢失';
                        dialogMessage = `该文件已存在未过期的取件码，但本地缓存丢失旧文件密钥。\n\n选择操作：\n• 重新生成（生成全新取件码）：重新上传文件，旧的取件码将无法下载\n• 取消：不进行任何操作`;
                        confirmText = '重新生成（生成全新取件码）';
                    }
                    
                    // 显示确认弹窗，让用户决定是否重新生成
                    console.log('显示确认弹窗:', { dialogTitle, dialogMessage });
                    const shouldRegenerate = await showConfirmDialog(
                        dialogTitle,
                        dialogMessage,
                        confirmText,
                        '取消'
                    );
                    
                    console.log('用户选择:', shouldRegenerate ? confirmText : '取消');
                    
                    if (shouldRegenerate) {
                        const fileId = errorData.data?.fileId || errorData.fileId;
                        if (fileId) {
                            try {
                                if (hasCachedKey && oldPickupCode) {
                                    // 有缓存密钥和旧取件码：复用旧密钥，只需作废旧取件码，保留文件记录和密钥
                                    console.log('复用旧密钥重新生成取件码, fileId:', fileId);
                                    await invalidateFileRecord(fileId);
                                    // 注意：不删除缓存的密钥和取件码，这样上传时会自动使用旧密钥
                                    console.log('重新调用创建取件码（将复用缓存的密钥，通过映射表复用文件块，无需重新上传）');
                                    return await generatePickupCodeHandler();
                                } else {
                                    // 没有缓存密钥或旧取件码：作废旧文件记录，生成新密钥
                                    console.log('作废旧文件记录并生成新密钥, fileId:', fileId);
                                    await invalidateFileRecord(fileId);
                                    // 删除缓存的密钥和取件码（如果存在）
                                    if (requestData.hash) {
                                        removeKeyFromCache(requestData.hash);
                                        removePickupCodeFromCache(requestData.hash);
                                    }
                                    console.log('重新调用创建取件码（将生成新密钥，需要重新上传文件块）');
                                    return await generatePickupCodeHandler();
                                }
                            } catch (error) {
                                throw new Error(`作废旧文件记录失败: ${error.message}`);
                            }
                        } else {
                            throw new Error('无法获取文件ID，无法重新生成');
                        }
                    } else {
                        // 用户取消
                        showMessage('已取消重新生成取件码', 'info');
                        return;
                    }
                }
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
        
        // 检查响应体中的 code 字段（后端可能返回 HTTP 200 但 code 不是 201）
        if (result.code !== 201) {
            // 处理文件已存在的情况（后端返回 code: 400）
            if (result.code === 400) {
                const errorCode = result.data?.code || result.code;
                console.log('检查响应体错误码:', errorCode, '是否为 FILE_ALREADY_EXISTS:', errorCode === 'FILE_ALREADY_EXISTS');
                console.log('result.data:', result.data);
                console.log('result.msg:', result.msg);
                
                // 尝试多种方式匹配错误码
                const isFileExists = errorCode === 'FILE_ALREADY_EXISTS' || 
                                   result.data?.code === 'FILE_ALREADY_EXISTS' ||
                                   (result.msg && result.msg.includes('已创建过未过期的取件码'));
                
                console.log('是否匹配文件已存在错误:', isFileExists);
                
                if (isFileExists) {
                    // 检查是否有密钥缓存和取件码缓存
                    const hasCachedKey = requestData.hash ? getKeyFromCache(requestData.hash) !== null : false;
                    const oldPickupCode = requestData.hash ? getPickupCodeFromCache(requestData.hash) : null;
                    console.log('密钥缓存检查:', { hasCachedKey, fileHash: requestData.hash ? requestData.hash.substring(0, 16) + '...' : null, oldPickupCode: oldPickupCode ? oldPickupCode.substring(0, 6) + '****' : null });
                    
                    let dialogTitle, dialogMessage, confirmText;
                    if (hasCachedKey && oldPickupCode) {
                        // 有缓存密钥和旧取件码，可以复用旧密钥重新生成取件码
                        // 注意：通过映射表机制，复用旧密钥时无需重新上传文件块
                        dialogTitle = '文件已存在';
                        dialogMessage = `该文件已创建过未过期的取件码（旧取件码: ${oldPickupCode}）。\n\n选择操作：\n• 重新生成（复用旧文件密钥）：无需重新上传文件，旧的取件码仍然可以下载\n• 取消：不进行任何操作`;
                        confirmText = '重新生成（复用旧文件密钥）';
                    } else {
                        // 没有缓存密钥或旧取件码，需要作废旧文件记录
                        dialogTitle = '文件已存在但密钥丢失';
                        dialogMessage = `该文件已存在未过期的取件码，但本地缓存丢失旧文件密钥。\n\n选择操作：\n• 重新生成（生成全新取件码）：重新上传文件，旧的取件码将无法下载\n• 取消：不进行任何操作`;
                        confirmText = '重新生成（生成全新取件码）';
                    }
                    
                    // 显示确认弹窗，让用户决定是否重新生成
                    console.log('显示确认弹窗:', { dialogTitle, dialogMessage });
                    const shouldRegenerate = await showConfirmDialog(
                        dialogTitle,
                        dialogMessage,
                        confirmText,
                        '取消'
                    );
                    
                    console.log('用户选择:', shouldRegenerate ? confirmText : '取消');
                    
                    if (shouldRegenerate) {
                        const fileId = result.data?.fileId || result.fileId;
                        if (fileId) {
                            try {
                                if (hasCachedKey && oldPickupCode) {
                                    // 有缓存密钥和旧取件码：复用旧密钥，只需作废旧取件码，保留文件记录和密钥
                                    // 注意：通过映射表机制，复用旧密钥时无需重新上传文件块
                                    console.log('复用旧密钥重新生成取件码, fileId:', fileId);
                                    await invalidateFileRecord(fileId);
                                    // 注意：不删除缓存的密钥和取件码，这样上传时会自动使用旧密钥
                                    // 重新调用创建取件码（会自动使用缓存的密钥，通过映射表复用文件块，无需重新上传）
                                    console.log('重新调用创建取件码（将复用缓存的密钥，通过映射表复用文件块，无需重新上传）');
                                    return await generatePickupCodeHandler();
                                } else {
                                    // 没有缓存密钥或旧取件码：作废旧文件记录，生成新密钥
                                    console.log('作废旧文件记录并生成新密钥, fileId:', fileId);
                                    await invalidateFileRecord(fileId);
                                    // 删除缓存的密钥和取件码（如果存在）
                                    if (requestData.hash) {
                                        removeKeyFromCache(requestData.hash);
                                        removePickupCodeFromCache(requestData.hash);
                                    }
                                    // 重新调用创建取件码（将生成新密钥，需要重新上传文件块）
                                    console.log('重新调用创建取件码（将生成新密钥，需要重新上传文件块）');
                                    return await generatePickupCodeHandler();
                                }
                            } catch (error) {
                                throw new Error(`作废旧文件记录失败: ${error.message}`);
                            }
                        } else {
                            throw new Error('无法获取文件ID，无法重新生成');
                        }
                    } else {
                        // 用户取消
                        showMessage('已取消重新生成取件码', 'info');
                        return;
                    }
                }
            }
            
            // 如果不是文件已存在错误，抛出通用错误
            throw new Error(result.msg || '创建取件码失败');
        }
        
        if (!result.data) {
            throw new Error(result.msg || '创建取件码失败');
        }
        
        // 保存取件码信息
        CONFIG.pickupCode = result.data.code;
        CONFIG.fileName = result.data.fileName;
        CONFIG.fileSize = result.data.fileSize;
        
        // 保存文件ID和过期时间到CONFIG，用于作废功能和密钥缓存
        if (result.data.fileId) {
            CONFIG.fileId = result.data.fileId;
            // 显示作废按钮
            const invalidateBtn = document.getElementById('invalidateBtn');
            if (invalidateBtn) {
                invalidateBtn.style.display = 'block';
            }
        }
        
        // 保存过期时间（用于密钥缓存）
        CONFIG.expireHours = requestData.expireHours || 24;
        
        // 缓存完整的12位取件码（以文件哈希为键），用于后续显示旧取件码
        if (CONFIG.fileHash && CONFIG.pickupCode) {
            storePickupCodeInCache(CONFIG.fileHash, CONFIG.pickupCode, CONFIG.expireHours);
        }
        
        // 更新取件码显示并打开弹窗
        const pickupCodeElement = document.getElementById('pickupCode');
        
        if (pickupCodeElement) {
            pickupCodeElement.textContent = CONFIG.pickupCode;
            // 打开取件码弹窗
            openModal('codeModal');
        }
        
        // 更新状态显示（使用服务器返回的数据）
        updateStatusDisplayFromServer(result.data);
        
        // 开始轮询状态
        startStatusPolling();
        
        // 保存状态
        saveCurrentState();
        
        // 关闭遮罩（创建取件码的短过程已完成）
        showLoading(false);
        showMessage('取件码已生成，正在上传文件...', 'success');
        
        // 初始化 SenderService 并上传文件（长过程，不使用遮罩，让用户看到进度条）
        await initializeSenderService();
        
    } catch (error) {
        console.error('创建取件码失败:', error);
        // 改进错误提示：显示更友好的错误信息
        let errorMessage = error.message;
        if (errorMessage.includes('已创建过未过期的取件码')) {
            // 这个错误已经在弹窗中处理了，不需要再次显示
            return;
        } else if (errorMessage.includes('数据验证失败')) {
            errorMessage = '请求数据格式错误，请刷新页面重试';
        } else if (errorMessage.includes('网络') || errorMessage.includes('fetch')) {
            errorMessage = '网络连接失败，请检查网络后重试';
        } else if (errorMessage.includes('超时')) {
            errorMessage = '请求超时，请稍后重试';
        }
        showMessage(`创建取件码失败: ${errorMessage}`, 'error');
    } finally {
        // 确保遮罩被关闭
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
    
    // 隐藏保存按钮（下载完成前不显示）
    const downloadLink = document.getElementById('downloadLink');
    if (downloadLink) {
        downloadLink.style.display = 'none';
    }
    
    // 隐藏进度条（重新开始时重置）
    const progressBar = document.getElementById('recvProgressBar');
    if (progressBar) {
        progressBar.style.display = 'none';
    }
    
    // 显示加载动画
    showLoading(true, '正在连接...');
    
    try {
        // 提取前6位查找码（只发送查找码到服务器，不暴露后6位密钥码）
        const lookupCode = code.substring(0, 6);
        
        // 先查询取件码状态，获取文件信息（只发送6位查找码）
        const statusResponse = await fetch(`${CONFIG.API_BASE}/v1/codes/${lookupCode}/status`);
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
        // 改进错误提示
        let errorMessage = error.message;
        if (errorMessage.includes('网络') || errorMessage.includes('fetch')) {
            errorMessage = '网络连接失败，请检查网络后重试';
        } else if (errorMessage.includes('超时')) {
            errorMessage = '下载超时，请稍后重试';
        } else if (errorMessage.includes('加密') || errorMessage.includes('密钥')) {
            errorMessage = '文件解密失败，请检查取件码是否正确';
        } else if (errorMessage.includes('不存在') || errorMessage.includes('已过期')) {
            // 保持原错误信息
        } else {
            errorMessage = '下载失败，请稍后重试';
        }
        showMessage(`接收失败: ${errorMessage}`, 'error');
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
        // 显示上传进度条
        const sendProgressBar = document.getElementById('sendProgressBar');
        const sendProgressFill = document.getElementById('sendProgressFill');
        const sendProgressPercent = document.getElementById('sendProgressPercent');
        
        if (sendProgressBar) {
            sendProgressBar.style.display = 'block';
        }
        
        // 初始化进度条为0%
        if (sendProgressFill) {
            sendProgressFill.style.width = '0%';
        }
        if (sendProgressPercent) {
            sendProgressPercent.textContent = '0%';
        }
        
        // 初始化服务
        senderService.init(`${CONFIG.API_BASE}/v1`, {
            onProgress: (progress, sent, total) => {
                console.log(`上传进度: ${progress.toFixed(1)}% (${sent}/${total})`);
                
                // 更新上传进度条
                if (sendProgressFill) {
                    sendProgressFill.style.width = `${progress}%`;
                }
                if (sendProgressPercent) {
                    sendProgressPercent.textContent = `${progress.toFixed(1)}%`;
                }
            },
            onComplete: () => {
                console.log('文件上传完成');
                
                // 更新进度条到100%
                if (sendProgressFill) {
                    sendProgressFill.style.width = '100%';
                    sendProgressFill.classList.add('completed');
                }
                if (sendProgressPercent) {
                    sendProgressPercent.textContent = '100%';
                }
                
                // 标记进度容器为完成状态
                if (sendProgressBar) {
                    sendProgressBar.classList.add('completed');
                    const headerText = sendProgressBar.querySelector('.progress-header span:first-child');
                    if (headerText) {
                        headerText.textContent = '上传完成';
                    }
                }
                
                // 显示完成标记
                const uploadCompleteBadge = document.getElementById('uploadCompleteBadge');
                if (uploadCompleteBadge) {
                    uploadCompleteBadge.classList.add('show');
                }
                
                showMessage('文件已成功上传，等待接收方下载', 'success');
            },
            onError: (error) => {
                console.error('上传错误:', error);
                // 改进错误提示
                let errorMessage = error.message;
                if (errorMessage.includes('网络') || errorMessage.includes('fetch')) {
                    errorMessage = '网络连接失败，请检查网络后重试';
                } else if (errorMessage.includes('超时')) {
                    errorMessage = '上传超时，请稍后重试';
                } else if (errorMessage.includes('加密')) {
                    errorMessage = '文件加密失败，请刷新页面重试';
                }
                showMessage(`上传失败: ${errorMessage}`, 'error');
            }
        });
        
        // 使用已计算的文件哈希和过期时间（用于密钥缓存）
        // 文件哈希和过期时间在创建取件码时已经计算并保存到 CONFIG
        
        // 通过服务器中转上传文件（使用端到端加密）
        // 注意：不使用遮罩，让用户看到上传进度条的变化
        console.log('[Sender] 开始上传文件（服务器中转模式）...');
        
        await senderService.uploadFileViaRelay(CONFIG.pickupCode, CONFIG.localFile, CONFIG.fileHash, CONFIG.expireHours || 24);
        
        console.log('[Sender] ✓ 文件上传完成');
        // 上传完成的提示已经在 onComplete 回调中显示，这里不需要重复显示
        
    } catch (error) {
        console.error('初始化SenderService失败:', error);
        // 改进错误提示
        let errorMessage = error.message;
        if (errorMessage.includes('网络') || errorMessage.includes('fetch')) {
            errorMessage = '网络连接失败，请检查网络后重试';
        } else if (errorMessage.includes('超时')) {
            errorMessage = '上传超时，请稍后重试';
        } else if (errorMessage.includes('加密')) {
            errorMessage = '文件加密失败，请刷新页面重试';
        }
        showMessage(`上传失败: ${errorMessage}`, 'error');
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
        // 注意：使用更精确的选择器，选择接收区域的进度条填充元素
        const progressFill = progressBar ? progressBar.querySelector('.progress-fill') : null;
        const progressPercent = document.getElementById('progressPercent');
        
        // 隐藏保存按钮（下载完成前不显示）
        const downloadLink = document.getElementById('downloadLink');
        if (downloadLink) {
            downloadLink.style.display = 'none';
        }
        
        // 初始化进度条
        if (progressBar) {
            progressBar.style.display = 'block';
        }
        if (progressFill) {
            progressFill.style.width = '0%';
        }
        if (progressPercent) {
            progressPercent.textContent = '0%';
        }
        
        // 初始化服务
        receiverService.init(`${CONFIG.API_BASE}/v1`, {
            onProgress: (progress, received, total, message) => {
                console.log(`下载进度: ${progress.toFixed(1)}% (${received}/${total})`, message || '');
                
                // 如果有等待消息，显示在进度条上（连接建立阶段）
                if (message !== null && message !== undefined) {
                    if (progressPercent) {
                        progressPercent.textContent = message;
                    }
                    // 保持遮罩显示，不更新进度条宽度
                } else {
                    // 连接建立完成（message为null/undefined）或开始下载（progress > 0）
                    // 关闭连接遮罩，显示进度条
                    if (message === null || message === undefined || progress > 0) {
                        showLoading(false); // 关闭连接遮罩，让进度条可见
                    }
                    
                    // 更新进度条（确保进度值有效）
                    const validProgress = Math.max(0, Math.min(100, progress || 0));
                    if (progressFill) {
                        progressFill.style.width = `${validProgress}%`;
                    }
                    if (progressPercent) {
                        progressPercent.textContent = `${validProgress.toFixed(1)}%`;
                    }
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
                
                // 显示下载链接（保存按钮）
                const downloadLink = document.getElementById('downloadLink');
                if (downloadLink) {
                    downloadLink.style.display = 'block';
                    downloadLink.onclick = (e) => {
                        e.preventDefault();
                        downloadBlob(fileBlob, fileInfo.fileName);
                    };
                    downloadLink.textContent = `保存 ${fileInfo.fileName}`;
                }
                
                // 确保保存按钮可见
                if (downloadLink) {
                    downloadLink.style.display = 'block';
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
        // 只在建立连接时显示遮罩（获取密钥、获取文件信息阶段）
        showLoading(true, '正在连接...');
        console.log('[Receiver] 开始下载文件（服务器中转模式）...');
        
        await receiverService.downloadFileViaRelay(code);
        
        // 下载开始后，遮罩会在onProgress回调中关闭（当progress > 0时）
        
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
        // 提取前6位查找码（只发送查找码到服务器，不暴露后6位密钥码）
        const lookupCode = CONFIG.pickupCode.substring(0, 6);
        const response = await fetch(`${CONFIG.API_BASE}/v1/codes/${lookupCode}/status`);
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
            // 使用当前页面的协议（HTTPS或HTTP），避免混合内容错误
            const protocol = window.location.protocol;
            CONFIG.API_BASE = `${protocol}//${host}:${port}/api`;
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

// ========== 清理上传完成UI ==========
/**
 * 清除上传完成的UI状态
 */
function clearUploadCompleteUI() {
    // 清除上传进度条的完成状态
    const sendProgressBar = document.getElementById('sendProgressBar');
    const sendProgressFill = document.getElementById('sendProgressFill');
    const sendProgressPercent = document.getElementById('sendProgressPercent');
    
    if (sendProgressBar) {
        sendProgressBar.classList.remove('completed');
        const headerText = sendProgressBar.querySelector('.progress-header span:first-child');
        if (headerText) {
            headerText.textContent = '上传进度';
        }
    }
    
    if (sendProgressFill) {
        sendProgressFill.classList.remove('completed');
        sendProgressFill.style.width = '0%';
    }
    
    if (sendProgressPercent) {
        sendProgressPercent.textContent = '0%';
    }
    
    // 隐藏上传完成徽章
    const uploadCompleteBadge = document.getElementById('uploadCompleteBadge');
    if (uploadCompleteBadge) {
        uploadCompleteBadge.classList.remove('show');
    }
    
    console.log('[UI] 已清除上传完成状态');
}

// ========== 文件作废功能 ==========
/**
 * 作废文件记录
 * @param {number} fileId - 文件ID
 */
async function invalidateFileRecord(fileId) {
    if (!CONFIG.API_BASE) {
        throw new Error('API基础URL未设置');
    }
    
    const response = await fetch(`${CONFIG.API_BASE}/v1/codes/files/${fileId}/invalidate`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    });
    
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.msg || `HTTP ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    if (result.code !== 200) {
        throw new Error(result.msg || '作废文件记录失败');
    }
    
    return result.data;
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