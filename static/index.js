// 配置信息
const CONFIG = {
  API_BASE: "",
  localFile: null,
  pickupCode: "",
  fileSize: 0,
  fileName: "",
};

// ========== 初始化函数 ==========
document.addEventListener("DOMContentLoaded", function () {
  initEventListeners();
  autoTestPort();
});

// ========== 事件监听器初始化 ==========
function initEventListeners() {
  // 文件选择事件
  document.getElementById("fileInput").onchange = function () {
    if (this.files.length) handleFile(this.files[0]);
  };

  // 拖拽事件
  setupDragAndDrop();

  // 按钮事件
  document.getElementById("shareBtn").onclick = generatePickupCode;
  document.getElementById("copyCodeBtn").onclick = copyPickupCode;
  document.getElementById("receiveBtn").onclick = receiveFile;
  document.getElementById("reportBtn").onclick = reportFile;
  document.getElementById("testBtn").onclick = testPortConnection;

  // 输入框事件
  document.getElementById("inputCode").addEventListener("input", function (e) {
    this.value = this.value.toUpperCase().replace(/[^A-Z0-9]/g, "");
  });
}

// ========== 拖拽功能 ==========
function setupDragAndDrop() {
  const dropArea = document.getElementById("dropArea");

  // 点击选择文件
  dropArea.onclick = function () {
    document.getElementById("fileInput").click();
  };

  // 拖拽事件
  ["dragenter", "dragover"].forEach((evt) => {
    dropArea.addEventListener(evt, function (e) {
      e.preventDefault();
      this.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((evt) => {
    dropArea.addEventListener(evt, function (e) {
      e.preventDefault();
      this.classList.remove("dragover");
      if (e.type === "drop" && e.dataTransfer.files.length) {
        handleFile(e.dataTransfer.files[0]);
      }
    });
  });
}

// ========== 文件处理 ==========
function handleFile(file) {
  CONFIG.localFile = file;

  // 显示文件信息
  const fileInfo = document.getElementById("fileInfo");
  document.getElementById("fileName").textContent = file.name;
  document.getElementById("fileSize").textContent = formatFileSize(file.size);
  fileInfo.style.display = "block";

  // 启用生成按钮
  document.getElementById("shareBtn").disabled = false;

  // 预览图片
  const preview = document.getElementById("preview");
  if (file.type.startsWith("image/")) {
    const reader = new FileReader();
    reader.onload = function (e) {
      preview.innerHTML = `<img src="${e.target.result}" alt="预览">`;
    };
    reader.readAsDataURL(file);
  } else {
    preview.innerHTML = `<div class="file-icon">📄 ${getFileIcon(
      file.name
    )}</div>`;
  }
}

// ========== 生成取件码 ==========
function generatePickupCode() {
  if (!CONFIG.localFile) return;

  // 生成6位取件码
  CONFIG.pickupCode = Array.from(
    { length: 6 },
    () => "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[Math.floor(Math.random() * 36)]
  ).join("");

  // 显示取件码区域
  const codeSection = document.getElementById("codeSec");
  document.getElementById("pickupCode").textContent = CONFIG.pickupCode;
  codeSection.style.display = "block";

  // 更新状态显示
  updateStatusDisplay();

  // 开始轮询状态
  startStatusPolling();

  // 提示用户
  showMessage("取件码已生成，分享给朋友吧！", "success");
}

// ========== 复制取件码 ==========
function copyPickupCode() {
  if (!CONFIG.pickupCode) return;

  navigator.clipboard
    .writeText(CONFIG.pickupCode)
    .then(() => showMessage("取件码已复制到剪贴板", "success"))
    .catch(() => {
      // 降级方案
      const textArea = document.createElement("textarea");
      textArea.value = CONFIG.pickupCode;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
      showMessage("取件码已复制", "success");
    });
}

// ========== 接收文件 ==========
function receiveFile() {
  const code = document.getElementById("inputCode").value.trim().toUpperCase();

  if (!code || code.length !== 6) {
    showMessage("请输入6位取件码", "error");
    return;
  }

  if (!CONFIG.API_BASE) {
    showMessage("请先测试端口连接", "error");
    return;
  }

  const receiveBtn = document.getElementById("receiveBtn");
  receiveBtn.disabled = true;
  receiveBtn.innerHTML = '<i class="icon-receive"></i> 领取中...';

  // 模拟接收过程
  simulateFileReceive();
}

// ========== 模拟文件接收 ==========
function simulateFileReceive() {
  const progressBar = document.getElementById("recvProgressBar");
  const progressFill = document.querySelector(".progress-fill");
  const progressPercent = document.getElementById("progressPercent");

  progressBar.style.display = "block";

  let progress = 0;
  const interval = setInterval(() => {
    progress += Math.random() * 15 + 5;
    if (progress >= 100) {
      progress = 100;
      clearInterval(interval);

      // 显示下载链接
      setTimeout(() => {
        const downloadLink = document.getElementById("downloadLink");
        downloadLink.style.display = "block";
        downloadLink.href = "#";
        downloadLink.download = "示例文件.txt";

        // 重置按钮
        const receiveBtn = document.getElementById("receiveBtn");
        receiveBtn.disabled = false;
        receiveBtn.innerHTML = '<i class="icon-receive"></i> 领取';

        showMessage("文件准备就绪，点击下载", "success");
      }, 500);
    }

    progressFill.style.width = `${progress}%`;
    progressPercent.textContent = `${Math.floor(progress)}%`;
  }, 300);
}

// ========== 状态轮询 ==========
function startStatusPolling() {
  if (!CONFIG.pickupCode || !CONFIG.API_BASE) return;

  const intervalId = setInterval(() => {
    // 模拟状态更新
    updateMockStatus();

    // 检查是否过期（30分钟后）
    if (Math.random() < 0.01) {
      clearInterval(intervalId);
      document.getElementById("statStatus").textContent = "已过期";
      document.getElementById("statStatus").style.color = "#f72585";
    }
  }, 2000);
}

// ========== 模拟状态更新 ==========
function updateMockStatus() {
  const timeElement = document.getElementById("statTime");
  const countElement = document.getElementById("statCount");
  const statusElement = document.getElementById("statStatus");

  // 更新时间
  const currentTime = timeElement.textContent.split(":");
  let minutes = parseInt(currentTime[0]);
  let seconds = parseInt(currentTime[1]);

  if (seconds > 0) {
    seconds--;
  } else {
    if (minutes > 0) {
      minutes--;
      seconds = 59;
    }
  }

  timeElement.textContent = `${minutes}:${seconds.toString().padStart(2, "0")}`;

  // 随机更新领取次数（模拟）
  if (Math.random() < 0.1) {
    const [used, limit] = countElement.textContent.split("/").map(Number);
    if (used < limit) {
      countElement.textContent = `${used + 1}/${limit}`;
    }
  }

  // 更新状态
  if (Math.random() < 0.05) {
    const statuses = ["等待中", "进行中", "已完成"];
    const newStatus = statuses[Math.floor(Math.random() * statuses.length)];
    statusElement.textContent = newStatus;

    // 根据状态改变颜色
    statusElement.style.color =
      newStatus === "已完成"
        ? "#4cc9f0"
        : newStatus === "进行中"
        ? "#4361ee"
        : "#6c757d";
  }
}

// ========== 更新状态显示 ==========
function updateStatusDisplay() {
  // 设置初始值
  document.getElementById("statTime").textContent = "30:00";
  document.getElementById("statSize").textContent = CONFIG.localFile
    ? formatFileSize(CONFIG.localFile.size)
    : "0 MB";

  const limit = document.getElementById("limitSelect").value;
  document.getElementById("statCount").textContent = `0/${
    limit === "999" ? "∞" : limit
  }`;
  document.getElementById("statStatus").textContent = "等待中";
}

// ========== 端口测试 ==========
function testPortConnection() {
  const port = document.getElementById("portInput").value;
  const resultElement = document.getElementById("portResult");

  resultElement.innerHTML = '<i class="icon-info"></i> 检测中...';
  resultElement.style.color = "#f8961e";

  // 模拟端口测试
  setTimeout(() => {
    const success = Math.random() > 0.3; // 70%成功率模拟

    if (success) {
      CONFIG.API_BASE = `http://${location.hostname}:${port}/api`;
      resultElement.innerHTML = '<i class="icon-success"></i> 连接成功！';
      resultElement.style.color = "#4cc9f0";
      showMessage("端口连接成功，可以正常使用", "success");
    } else {
      resultElement.innerHTML = '<i class="icon-error"></i> 连接失败';
      resultElement.style.color = "#f72585";
      showMessage("端口连接失败，请检查是否出错", "error");
    }
  }, 800);
}

// ========== 自动测试端口 ==========
function autoTestPort() {
  setTimeout(() => {
    document.getElementById("testBtn").click();
  }, 500);
}

// ========== 举报文件 ==========
function reportFile() {
  if (!CONFIG.pickupCode) {
    showMessage("请先生成取件码", "error");
    return;
  }

  const reason = prompt("请输入举报原因（违规内容、侵权等）：");
  if (!reason) return;

  // 模拟举报提交
  setTimeout(() => {
    showMessage("举报已提交，感谢您的反馈", "success");
  }, 500);
}

// ========== 工具函数 ==========
function formatFileSize(bytes) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function getFileIcon(filename) {
  const ext = filename.split(".").pop().toLowerCase();
  const icons = {
    pdf: "📕",
    doc: "📄",
    docx: "📄",
    txt: "📝",
    xls: "📊",
    xlsx: "📊",
    ppt: "📽️",
    pptx: "📽️",
    zip: "📦",
    rar: "📦",
    mp3: "🎵",
    mp4: "🎬",
    jpg: "🖼️",
    jpeg: "🖼️",
    png: "🖼️",
    gif: "🖼️",
  };
  return icons[ext] || "📁";
}

function showMessage(message, type = "info") {
  // 创建消息元素
  const messageEl = document.createElement("div");
  messageEl.className = `message message-${type}`;
  messageEl.textContent = message;
  messageEl.style.cssText = `
        position: fixed; top: 20px; right: 20px;
        padding: 12px 24px; border-radius: 8px;
        background: ${
          type === "success"
            ? "#4cc9f0"
            : type === "error"
            ? "#f72585"
            : "#4361ee"
        };
        color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 1000; animation: slideIn 0.3s ease;
    `;

  document.body.appendChild(messageEl);

  // 自动移除
  setTimeout(() => {
    messageEl.style.opacity = "0";
    messageEl.style.transform = "translateY(-10px)";
    setTimeout(() => document.body.removeChild(messageEl), 300);
  }, 3000);
}
