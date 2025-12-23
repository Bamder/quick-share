/**
 * QuickShare 欢迎页面交互逻辑
 * 优化版 - 专注于快速跳转到主页面
 */

// 页面初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 QuickShare 欢迎页面加载完成');
    
    // 立即初始化按钮（优先级最高）
    initPrimaryButton();
    
    // 延迟初始化其他元素（次要优先级）
    setTimeout(() => {
        initFeatureCards();
        initStatsAnimation();
    }, 100);
    
    // 添加页面加载动画
    animatePageLoad();
});

/**
 * 初始化主要按钮 - 这是最重要的功能
 */
function initPrimaryButton() {
    const startBtn = document.getElementById('startBtn');
    
    if (!startBtn) {
        console.error('❌ 错误：找不到开始按钮，请检查HTML结构');
        
        // 尝试自动创建备用按钮
        createFallbackButton();
        return;
    }
    
    console.log('✅ 开始按钮初始化成功');
    
    // 立即显示按钮（不等待其他动画）
    startBtn.style.opacity = '1';
    startBtn.style.transform = 'translateY(0)';
    
    // 添加点击事件
    startBtn.addEventListener('click', handleStartClick);
    
    // 添加键盘快捷键支持
    document.addEventListener('keydown', function(event) {
        // Enter 或 Space 键触发
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            console.log('⌨️ 键盘快捷键触发');
            startBtn.click();
        }
        
        // ESC 键可以取消（如果有加载状态）
        if (event.key === 'Escape') {
            resetButtonState(startBtn);
        }
    });
    
    // 触摸设备优化
    if ('ontouchstart' in window) {
        startBtn.addEventListener('touchstart', function() {
            this.style.transform = 'scale(0.98)';
        });
        
        startBtn.addEventListener('touchend', function() {
            this.style.transform = '';
        });
    }
    
    // 确保按钮始终可见
    ensureButtonVisibility(startBtn);
}

/**
 * 处理开始按钮点击
 */
function handleStartClick(event) {
    if (event) event.preventDefault();
    
    const button = event ? event.target : document.getElementById('startBtn');
    if (!button) return;
    
    console.log('🎯 开始按钮被点击，准备跳转...');
    
    // 防止重复点击
    if (button.getAttribute('data-loading') === 'true') {
        console.log('⏳ 跳转已在处理中，请稍候...');
        return;
    }
    
    button.setAttribute('data-loading', 'true');
    
    // 保存原始状态
    const originalHTML = button.innerHTML;
    const originalWidth = button.offsetWidth;
    
    // 设置固定宽度防止跳动
    button.style.width = `${originalWidth}px`;
    button.style.minWidth = `${originalWidth}px`;
    
    // 显示加载状态
    button.innerHTML = `
        <span style="display:inline-flex;align-items:center;gap:8px;">
            <span class="loading-spinner"></span>
            准备中...
        </span>
    `;
    button.disabled = true;
    
    // 添加加载动画样式
    addLoadingStyles();
    
    // 添加轻微振动反馈（如果支持）
    if (navigator.vibrate) {
        navigator.vibrate([50]);
    }
    
    // 开始跳转（添加短暂延迟让用户看到反馈）
    setTimeout(() => {
        performPageTransition(button);
    }, 600);
}

/**
 * 执行页面跳转
 */
function performPageTransition(button) {
    console.log('🚀 执行页面跳转到主界面');
    
    // 添加页面转场效果
    document.body.style.opacity = '0.9';
    document.body.style.transition = 'opacity 0.3s ease';
    
    // 跳转到主页面
    setTimeout(() => {
        const mainPagePath = '/static/pages/index.html';
        console.log(`📍 跳转路径: ${mainPagePath}`);
        
        // 尝试跳转
        try {
            window.location.href = mainPagePath;
        } catch (error) {
            console.error('❌ 跳转失败:', error);
            
            // 回退方案
            resetButtonState(button);
            showErrorMessage('跳转失败，请手动访问: ' + mainPagePath);
        }
    }, 300);
}

/**
 * 初始化特性卡片
 */
function initFeatureCards() {
    const featureCards = document.querySelectorAll('.feature-card');
    
    if (featureCards.length === 0) {
        console.log('ℹ️ 未找到特性卡片，跳过初始化');
        return;
    }
    
    console.log(`✅ 初始化 ${featureCards.length} 个特性卡片`);
    
    featureCards.forEach((card, index) => {
        // 快速显示（最小延迟）
        setTimeout(() => {
            card.style.transition = 'all 0.3s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 50 * index);
        
        // 添加悬停效果
        card.addEventListener('mouseenter', function() {
            const icon = this.querySelector('.feature-icon');
            if (icon) {
                icon.style.transform = 'scale(1.05)';
            }
        });
        
        card.addEventListener('mouseleave', function() {
            const icon = this.querySelector('.feature-icon');
            if (icon) {
                icon.style.transform = '';
            }
        });
    });
}

/**
 * 初始化统计数据动画
 */
function initStatsAnimation() {
    const stats = document.querySelectorAll('.stat-value');
    
    if (stats.length === 0) {
        console.log('ℹ️ 未找到统计数据，跳过动画');
        return;
    }
    
    // 使用 Intersection Observer 实现滚动动画
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const stat = entry.target;
                const originalValue = stat.textContent;
                
                // 数字动画效果
                if (originalValue === '2GB' || originalValue === '256-bit' || originalValue === '0s') {
                    // 对于特殊值，直接显示
                    stat.style.opacity = '1';
                    stat.style.transform = 'scale(1)';
                } else if (!isNaN(parseFloat(originalValue))) {
                    // 对于数字，执行计数动画
                    animateNumber(stat, 0, parseFloat(originalValue), 1000);
                }
                
                observer.unobserve(stat);
            }
        });
    }, {
        threshold: 0.3,
        rootMargin: '0px 0px -50px 0px'
    });
    
    stats.forEach(stat => {
        stat.style.opacity = '0.5';
        stat.style.transform = 'scale(0.9)';
        observer.observe(stat);
    });
}

/**
 * 数字动画效果
 */
function animateNumber(element, start, end, duration) {
    const startTime = performance.now();
    
    const step = (currentTime) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // 缓动函数
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const currentValue = start + (end - start) * easeOut;
        
        element.textContent = Math.round(currentValue).toString();
        element.style.opacity = 0.5 + (0.5 * easeOut);
        element.style.transform = `scale(${0.9 + (0.1 * easeOut)})`;
        
        if (progress < 1) {
            requestAnimationFrame(step);
        } else {
            element.style.opacity = '1';
            element.style.transform = 'scale(1)';
        }
    };
    
    requestAnimationFrame(step);
}

/**
 * 页面加载动画
 */
function animatePageLoad() {
    // 页面淡入效果
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.4s ease';
    
    requestAnimationFrame(() => {
        document.body.style.opacity = '1';
    });
    
    // 背景网格动画
    const grid = document.querySelector('.geometric-grid');
    if (grid) {
        setTimeout(() => {
            grid.style.transition = 'background-size 15s linear';
            grid.style.backgroundSize = '90px 90px';
        }, 300);
    }
}

/**
 * 添加加载样式
 */
function addLoadingStyles() {
    // 检查是否已添加
    if (document.getElementById('loading-styles')) return;
    
    const style = document.createElement('style');
    style.id = 'loading-styles';
    style.textContent = `
        .loading-spinner {
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        @keyframes fadeOut {
            to { opacity: 0; }
        }
    `;
    
    document.head.appendChild(style);
}

/**
 * 重置按钮状态
 */
function resetButtonState(button) {
    if (!button) return;
    
    button.removeAttribute('data-loading');
    button.disabled = false;
    button.style.width = '';
    button.style.minWidth = '';
    
    // 恢复原始内容（需要根据实际情况调整）
    button.innerHTML = `
        立即开始传输
        <span class="button-icon">→</span>
    `;
}

/**
 * 确保按钮始终可见
 */
function ensureButtonVisibility(button) {
    // 滚动到按钮位置（如果按钮不在视口中）
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (!entry.isIntersecting) {
                // 按钮不在视口中，平滑滚动到按钮
                button.scrollIntoView({
                    behavior: 'smooth',
                    block: 'center'
                });
                observer.unobserve(button);
            }
        });
    }, {
        threshold: 0.5
    });
    
    observer.observe(button);
}

/**
 * 显示错误消息
 */
function showErrorMessage(message) {
    const errorDiv = document.createElement('div');
    errorDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #ef4444;
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        z-index: 10000;
        animation: slideIn 0.3s ease;
        max-width: 300px;
        word-break: break-word;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    `;
    
    errorDiv.innerHTML = `
        <strong>⚠️ 错误</strong>
        <p style="margin: 8px 0 0 0; font-size: 0.9rem;">${message}</p>
    `;
    
    document.body.appendChild(errorDiv);
    
    // 3秒后自动消失
    setTimeout(() => {
        errorDiv.style.opacity = '0';
        errorDiv.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            if (errorDiv.parentNode) {
                document.body.removeChild(errorDiv);
            }
        }, 300);
    }, 3000);
}

/**
 * 创建备用按钮（如果主按钮不存在）
 */
function createFallbackButton() {
    console.log('⚠️ 创建备用按钮...');
    
    const fallbackButton = document.createElement('button');
    fallbackButton.id = 'fallbackStartBtn';
    fallbackButton.textContent = '前往 QuickShare 主页面';
    fallbackButton.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        padding: 16px 32px;
        background: #2563eb;
        color: white;
        border: none;
        border-radius: 8px;
        font-size: 1.1rem;
        font-weight: 600;
        cursor: pointer;
        z-index: 1000;
        box-shadow: 0 8px 20px rgba(37, 99, 235, 0.3);
    `;
    
    fallbackButton.addEventListener('click', function() {
        window.location.href = '/static/pages/index.html';
    });
    
    document.body.appendChild(fallbackButton);
}

/**
 * 全局错误处理
 */
window.addEventListener('error', function(event) {
    console.error('❌ 页面错误:', event.error);
    
    // 不显示技术性错误给普通用户
    if (!event.error.message.includes('ResizeObserver')) {
        showErrorMessage('页面加载异常，请刷新重试');
    }
});

// 导出函数供调试使用
if (typeof window !== 'undefined') {
    window.QuickShareWelcome = {
        initPrimaryButton,
        handleStartClick,
        initFeatureCards,
        initStatsAnimation
    };
    
    console.log('✨ QuickShare 欢迎页面交互模块已加载');
}