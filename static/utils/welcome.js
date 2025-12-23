/**
 * 欢迎页面逻辑
 */

// 等待DOM加载完成
document.addEventListener('DOMContentLoaded', function() {
    // 获取开始按钮
    const startBtn = document.getElementById('startBtn');
    
    if (startBtn) {
        // 添加点击事件
        startBtn.addEventListener('click', function() {
            // 添加点击效果
            this.style.transform = 'scale(0.95)';
            
            // 短暂延迟后跳转
            setTimeout(() => {
                window.location.href = '../pages/index.html';
            }, 200);
            
            // 恢复按钮状态
            setTimeout(() => {
                this.style.transform = '';
            }, 200);
        });
        
        // 添加键盘支持
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                startBtn.click();
            }
        });
    }
    
    // 添加一些交互效果
    addInteractiveEffects();
});

/**
 * 添加页面交互效果
 */
function addInteractiveEffects() {
    // 为特性卡片添加鼠标跟随效果
    const cards = document.querySelectorAll('.feature-card');
    
    cards.forEach(card => {
        card.addEventListener('mousemove', function(e) {
            const rect = this.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            
            const rotateY = (x - centerX) / 25;
            const rotateX = (centerY - y) / 25;
            
            this.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-10px)`;
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) translateY(0)';
            setTimeout(() => {
                this.style.transform = '';
            }, 300);
        });
    });
    
    // 添加背景粒子效果（简单版）
    createBackgroundParticles();
}

/**
 * 创建背景粒子效果
 */
function createBackgroundParticles() {
    const container = document.querySelector('.welcome-container');
    if (!container) return;
    
    // 创建粒子容器
    const particlesContainer = document.createElement('div');
    particlesContainer.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: -1;
        overflow: hidden;
    `;
    
    container.appendChild(particlesContainer);
    
    // 创建粒子
    const particleCount = 30;
    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        const size = Math.random() * 4 + 1;
        const posX = Math.random() * 100;
        const posY = Math.random() * 100;
        const delay = Math.random() * 5;
        const duration = Math.random() * 10 + 10;
        
        particle.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            background: rgba(255, 255, 255, ${Math.random() * 0.3 + 0.1});
            border-radius: 50%;
            left: ${posX}%;
            top: ${posY}%;
            animation: floatParticle ${duration}s ease-in-out ${delay}s infinite;
        `;
        
        particlesContainer.appendChild(particle);
    }
    
    // 添加动画关键帧
    const style = document.createElement('style');
    style.textContent = `
        @keyframes floatParticle {
            0%, 100% {
                transform: translate(0, 0) scale(1);
                opacity: 0.3;
            }
            25% {
                transform: translate(${Math.random() * 40 - 20}px, ${Math.random() * 40 - 20}px) scale(1.1);
                opacity: 0.5;
            }
            50% {
                transform: translate(${Math.random() * 40 - 20}px, ${Math.random() * 40 - 20}px) scale(0.9);
                opacity: 0.7;
            }
            75% {
                transform: translate(${Math.random() * 40 - 20}px, ${Math.random() * 40 - 20}px) scale(1);
                opacity: 0.5;
            }
        }
    `;
    document.head.appendChild(style);
}