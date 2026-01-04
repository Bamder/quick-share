/**
 * 弹窗管理模块
 * 负责弹窗的打开、关闭和事件绑定
 */

// ========== 弹窗控制函数 ==========
export function openModal(modalIdOrContent, options = {}) {
  let modal;

  // 如果是字符串且包含HTML标签，则创建新弹窗
  if (typeof modalIdOrContent === "string" && modalIdOrContent.includes("<")) {
    const content = modalIdOrContent;

    // 创建弹窗元素
    modal = document.createElement("div");
    modal.id = "dynamic-modal";
    modal.className = "modal";
    modal.innerHTML = `
            <div class="modal-content" style="${
              options.width ? `width: ${options.width};` : ""
            }">
                ${content}
            </div>
        `;

    // 添加到body
    document.body.appendChild(modal);

    // 绑定关闭事件
    modal.addEventListener("click", function (e) {
      if (e.target === this) closeModal("dynamic-modal");
    });
  } else {
    // 否则按ID查找预定义弹窗
    const modalId = modalIdOrContent;
    modal = document.getElementById(modalId);
  }

  if (modal) {
    // 确保使用 flex 布局并居中
    modal.style.display = "flex";
    modal.style.alignItems = "center";
    modal.style.justifyContent = "center";
    modal.style.visibility = "visible";
    modal.style.opacity = "1";
    modal.style.background = "rgba(0, 0, 0, 0.6)";
    modal.classList.add("active");
    // 防止背景滚动
    document.body.style.overflow = "hidden";
  }
}

export function closeModal(modalId = "dynamic-modal") {
  const modal = document.getElementById(modalId);
  if (modal) {
    // 恢复内联样式，确保隐藏
    modal.style.display = "none";
    modal.style.visibility = "hidden";
    modal.style.opacity = "0";
    modal.classList.remove("active");
    // 恢复背景滚动
    document.body.style.overflow = "";

    // 如果是动态创建的弹窗，从DOM中移除
    if (modalId === "dynamic-modal") {
      setTimeout(() => {
        if (modal.parentNode) {
          modal.parentNode.removeChild(modal);
        }
      }, 300);
    }
  }
}

// ========== 初始化弹窗事件 ==========
export function initModalEvents() {
  // 侧边栏按钮事件
  const codeSecBtn = document.getElementById("codeSecBtn");
  const configBtn = document.getElementById("configBtn");

  if (codeSecBtn) {
    codeSecBtn.onclick = () => openModal("codeModal");
  }

  if (configBtn) {
    configBtn.onclick = () => openModal("configModal");
  }

  // 弹窗关闭按钮事件
  const closeCodeModal = document.getElementById("closeCodeModal");
  const closeConfigModal = document.getElementById("closeConfigModal");

  if (closeCodeModal) {
    closeCodeModal.onclick = () => closeModal("codeModal");
  }

  if (closeConfigModal) {
    closeConfigModal.onclick = () => closeModal("configModal");
  }

  // 点击遮罩层关闭弹窗
  const codeModal = document.getElementById("codeModal");
  const configModal = document.getElementById("configModal");

  if (codeModal) {
    codeModal.onclick = function (e) {
      if (e.target === this) closeModal("codeModal");
    };
  }

  if (configModal) {
    configModal.onclick = function (e) {
      if (e.target === this) closeModal("configModal");
    };
  }

  // ESC 键关闭弹窗
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      closeModal("codeModal");
      closeModal("configModal");
    }
  });

  // 确保弹窗默认关闭
  closeModal("codeModal");
  closeModal("configModal");
}

// ========== 加载弹窗HTML ==========
export async function loadModalHTML() {
  try {
    const response = await fetch("/static/components/modal/modal.html");
    if (!response.ok) {
      throw new Error("Failed to load modal HTML");
    }
    const html = await response.text();

    // 创建临时容器解析HTML
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = html;

    // 将弹窗元素添加到body
    while (tempDiv.firstChild) {
      document.body.appendChild(tempDiv.firstChild);
    }

    // 初始化事件
    initModalEvents();

    return true;
  } catch (error) {
    console.error("加载弹窗HTML失败:", error);
    return false;
  }
}
