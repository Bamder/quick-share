/**
 * 用户服务
 * 处理用户注册、登录、登出和token管理
 */

// 导入API客户端
import { apiRequest } from '../utils/api-client.js';

// 用户状态事件监听器
let userStatusListeners = [];

// 保存当前用户信息
let currentUser = null;

/**
 * 初始化用户服务
 */
export function initUserService() {
    // 从localStorage加载token并验证
    const token = localStorage.getItem('quickshare_token');
    if (token) {
        verifyToken(token)
            .then(user => {
                setCurrentUser(user);
            })
            .catch(() => {
                // token无效，清除
                localStorage.removeItem('quickshare_token');
                setCurrentUser(null);
            });
    }
}

/**
 * 设置当前用户并触发事件
 * @param {Object|null} user 用户信息或null
 */
function setCurrentUser(user) {
    currentUser = user;
    // 触发所有监听器
    userStatusListeners.forEach(listener => listener(user));
}

/**
 * 注册用户
 * @param {string} username 用户名
 * @param {string} password 密码
 * @returns {Promise<Object>} 注册结果
 */
export async function register(username, password) {
    try {
        // 密码哈希处理
        const hashedPassword = await hashPassword(password);
        
        // 打印日志，显示加密后的哈希值
        console.log('【用户服务】注册 - 用户名:', username);
        console.log('【用户服务】注册 - 明文密码:', password);
        console.log('【用户服务】注册 - 哈希后密码:', hashedPassword);
        console.log('【用户服务】注册 - 密码长度:', password.length, '字符');
        console.log('【用户服务】注册 - 哈希长度:', hashedPassword.length, '字符');
        
        const response = await apiRequest('POST', '/api/auth/register', {
            username,
            password: hashedPassword
        });
        
        if (response.token) {
            // 保存token
            localStorage.setItem('quickshare_token', response.token);
            // 设置当前用户
            setCurrentUser(response.user);
        }
        
        return response;
    } catch (error) {
        console.error('注册失败:', error);
        throw error;
    }
}

/**
 * 用户登录
 * @param {string} username 用户名
 * @param {string} password 密码
 * @returns {Promise<Object>} 登录结果
 */
export async function login(username, password) {
    try {
        // 密码哈希处理
        const hashedPassword = await hashPassword(password);
        
        // 打印日志，显示加密后的哈希值
        console.log('【用户服务】登录 - 用户名:', username);
        console.log('【用户服务】登录 - 明文密码:', password);
        console.log('【用户服务】登录 - 哈希后密码:', hashedPassword);
        console.log('【用户服务】登录 - 密码长度:', password.length, '字符');
        console.log('【用户服务】登录 - 哈希长度:', hashedPassword.length, '字符');
        
        const response = await apiRequest('POST', '/api/auth/login', {
            username,
            password: hashedPassword
        });
        
        if (response.token) {
            // 保存token
            localStorage.setItem('quickshare_token', response.token);
            // 设置当前用户
            setCurrentUser(response.user);
        }
        
        return response;
    } catch (error) {
        console.error('登录失败:', error);
        throw error;
    }
}

/**
 * 用户登出
 */
export function logout() {
    // 清除token
    localStorage.removeItem('quickshare_token');
    // 设置当前用户为null
    setCurrentUser(null);
}

/**
 * 验证token有效性
 * @param {string} token 用户token
 * @returns {Promise<Object>} 用户信息
 */
export async function verifyToken(token) {
    try {
        const response = await apiRequest('GET', '/api/auth/verify', {}, {
            'Authorization': `Bearer ${token}`
        });
        return response.user;
    } catch (error) {
        console.error('token验证失败:', error);
        throw error;
    }
}

/**
 * 获取当前用户信息
 * @returns {Object|null} 当前用户信息
 */
export function getCurrentUser() {
    return currentUser;
}

/**
 * 添加用户状态变化监听器
 * @param {Function} listener 监听器函数
 */
export function addUserStatusListener(listener) {
    userStatusListeners.push(listener);
    // 立即触发一次当前状态
    listener(currentUser);
}

/**
 * 移除用户状态变化监听器
 * @param {Function} listener 监听器函数
 */
export function removeUserStatusListener(listener) {
    userStatusListeners = userStatusListeners.filter(l => l !== listener);
}

/**
 * 密码哈希处理
 * @param {string} password 明文密码
 * @returns {Promise<string>} 哈希后的密码
 */
export async function hashPassword(password) {
    try {
        // 将密码转换为ArrayBuffer
        const passwordBuffer = new TextEncoder().encode(password);
        // 使用SHA-256哈希
        const hashBuffer = await crypto.subtle.digest('SHA-256', passwordBuffer);
        // 转换为十六进制字符串
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        return hashHex;
    } catch (error) {
        console.error('密码哈希失败:', error);
        throw error;
    }
}
