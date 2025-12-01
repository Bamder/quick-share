// 后端地址
var API_BASE = "";

// 全局变量
var localFile = null;
var pickupCode = "";
var shareExpireMin = 30;
var shareLimit = 3;
var pc = null;
var dc = null;
var receiveBuffer = [];
var fileSize = 0;
var fileName = "";

// 端口测试函数
function testPort(host, port) {
  var url = "http://" + host + ":" + port + "/api/status";
  return fetch(url, { method: "GET" })
    .then(function (res) {
      return res.ok;
    })
    .catch(function () {
      return false;
    });
}

// 端口验证按钮事件
document.getElementById("testBtn").onclick = function () {
  var port = document.getElementById("portInput").value;
  var portResult = document.getElementById("portResult");
  portResult.innerHTML =
    '<span class="result-icon">⏳</span><span class="result-text">检测中...</span>';

  testPort(location.hostname, port).then(function (ok) {
    API_BASE = "http://" + location.hostname + ":" + port + "/api";
    if (ok) {
      portResult.innerHTML =
        '<span class="result-icon" style="color: var(--success-color)">✅</span><span class="result-text" style="color: var(--success-color)">端口通畅，连接成功</span>';
    } else {
      portResult.innerHTML =
        '<span class="result-icon" style="color: var(--error-color)">❌</span><span class="result-text" style="color: var(--error-color)">端口不通，请检查后端服务</span>';
    }
  });
};

// 文件选择事件
document.getElementById("fileInput").onchange = function () {
  if (this.files.length) handleFile(this.files[0]);
};

// 拖拽事件
document.getElementById("dropArea").onclick = function () {
  document.getElementById("fileInput").click();
};

["dragenter", "dragover"].forEach(function (evt) {
  document.getElementById("dropArea").addEventListener(evt, function (e) {
    e.preventDefault();
    this.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach(function (evt) {
  document.getElementById("dropArea").addEventListener(evt, function (e) {
    e.preventDefault();
    this.classList.remove("dragover");
  });
});

document.getElementById("dropArea").addEventListener("drop", function (e) {
  var files = e.dataTransfer.files;
  if (files.length) handleFile(files[0]);
});

// 处理文件函数
function handleFile(file) {
  localFile = file;

  // 更新文件信息显示
  document.getElementById("fileName").textContent = file.name;
  document.getElementById("fileSize").textContent =
    (file.size / 1024 / 1024).toFixed(2) + " MB";

  // 启用生成取件码按钮
  document.getElementById("shareBtn").disabled = false;

  // 预览图片文件
  if (file.type.startsWith("image/")) {
    var reader = new FileReader();
    reader.onload = function (ev) {
      var preview = document.getElementById("preview");
      preview.innerHTML =
        '<img src="' +
        ev.target.result +
        '" alt="预览" style="max-width:200px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">';
    };
    reader.readAsDataURL(file);
  } else {
    // 显示文件图标
    var preview = document.getElementById("preview");
    var fileIcon = getFileIcon(file.name);
    preview.innerHTML =
      '<div style="font-size: 4rem; opacity: 0.8;">' + fileIcon + "</div>";
  }
}

// 根据文件类型返回图标
function getFileIcon(filename) {
  var ext = filename.split(".").pop().toLowerCase();
  var icons = {
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
    avi: "🎬",
    mov: "🎬",
    jpg: "🖼️",
    jpeg: "🖼️",
    png: "🖼️",
    gif: "🖼️",
    exe: "⚙️",
    dmg: "💿",
  };
  return icons[ext] || "📁";
}

// 生成取件码按钮事件
document.getElementById("shareBtn").onclick = function () {
  if (!localFile) return;

  // 生成6位取件码（字母+数字）
  pickupCode = Array.from({ length: 6 }, function () {
    return "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[
      Math.floor(Math.random() * 36)
    ];
  }).join("");

  // 显示取件码区域
  var codeSec = document.getElementById("codeSec");
  codeSec.style.display = "block";
  document.getElementById("pickupCode").textContent = pickupCode;

  // 更新设置
  shareExpireMin = document.getElementById("expireSelect").value;
  shareLimit = document.getElementById("limitSelect").value;

  // 开始状态轮询
  startStatusPolling();

  // 滚动到取件码区域
  codeSec.scrollIntoView({ behavior: "smooth" });

  // 更新二维码（这里用简单的模拟）
  updateQRCode();
};

// 更新二维码显示
function updateQRCode() {
  var qrGrid = document.querySelector(".qr-grid");
  if (qrGrid) {
    qrGrid.innerHTML = "";
    // 创建简单的二维码模拟效果
    for (var i = 0; i < 49; i++) {
      var cell = document.createElement("div");
      cell.style.backgroundColor =
        Math.random() > 0.5 ? "var(--primary-color)" : "transparent";
      cell.style.borderRadius = "2px";
      qrGrid.appendChild(cell);
    }
  }
}

// 复制按钮
document.getElementById("copyCodeBtn").onclick = function () {
  if (!navigator.clipboard) {
    // 降级方案
    var textArea = document.createElement("textarea");
    textArea.value = pickupCode;
    document.body.appendChild(textArea);
    textArea.select();
    document.execCommand("copy");
    document.body.removeChild(textArea);
    showNotification("取件码已复制到剪贴板");
  } else {
    navigator.clipboard.writeText(pickupCode).then(function () {
      showNotification("取件码已复制到剪贴板");
    });
  }
};

// 显示通知
function showNotification(message) {
  var notification = document.createElement("div");
  notification.className = "notification";
  notification.textContent = message;
  notification.style.cssText =
    "position: fixed; top: 20px; right: 20px; background: var(--success-color); color: white; padding: 12px 24px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 1000; animation: slideIn 0.3s ease;";
  document.body.appendChild(notification);

  setTimeout(function () {
    notification.style.opacity = "0";
    notification.style.transform = "translateY(-20px)";
    setTimeout(function () {
      document.body.removeChild(notification);
    }, 300);
  }, 2000);
}

// 状态轮询
function startStatusPolling() {
  if (!pickupCode) return;

  var interval = setInterval(function () {
    if (!API_BASE) return;

    fetch(API_BASE + "/status?code=" + pickupCode)
      .then(function (res) {
        if (!res.ok) throw new Error("请求失败");
        return res.json();
      })
      .then(function (json) {
        if (json.code !== 200) return;

        var d = json.data;

        // 更新文件大小
        document.getElementById("statSize").textContent =
          (d.fileSize / 1024 / 1024).toFixed(2) + " MB";

        // 更新领取次数
        var limitText = d.limit === 999 ? "∞" : d.limit;
        document.getElementById("statCount").textContent =
          d.used + " / " + limitText;

        // 更新状态
        var statusElement = document.getElementById("statStatus");
        statusElement.textContent = d.status;
        if (d.status === "已完成") {
          statusElement.style.color = "var(--success-color)";
        } else if (d.status === "进行中") {
          statusElement.style.color = "var(--primary-color)";
        }

        // 更新时间
        var left = new Date(d.expireAt) - Date.now();
        if (left <= 0) {
          clearInterval(interval);
          document.getElementById("statTime").textContent = "已过期";
          document.getElementById("statTime").parentElement.style.color =
            "var(--error-color)";
        } else {
          var min = Math.floor(left / 60000);
          var sec = Math.floor((left % 60000) / 1000);
          document.getElementById("statTime").textContent =
            min + ":" + sec.toString().padStart(2, "0");
        }
      })
      .catch(function (err) {
        console.error("轮询错误:", err);
      });
  }, 1000);
}

// 领取按钮绑定事件
document.getElementById("receiveBtn").onclick = function () {
  var code = document.getElementById("inputCode").value.trim().toUpperCase();
  if (!code || code.length !== 6) {
    showNotification("请输入6位取件码");
    return;
  }

  var receiveBtn = this;
  receiveBtn.disabled = true;
  receiveBtn.innerHTML = '<span class="btn-icon">⏳</span>领取中...';

  if (!API_BASE) {
    showNotification("请先测试端口连接");
    receiveBtn.disabled = false;
    receiveBtn.innerHTML = '<span class="btn-icon">⬇️</span>领取文件';
    return;
  }

  fetch(API_BASE + "/receive?code=" + code)
    .then(function (res) {
      if (!res.ok) throw new Error("网络错误");
      return res.json();
    })
    .then(function (json) {
      if (json.code !== 200) {
        throw new Error(json.msg || "领取失败");
      }

      var d = json.data;
      fileName = d.fileName;
      fileSize = d.fileSize;

      // 显示进度条
      var progressBar = document.getElementById("recvProgressBar");
      progressBar.style.display = "block";

      // 模拟进度更新
      simulateProgress();

      return fetch(API_BASE + "/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code, answer: "", ice: [] }),
      });
    })
    .then(function () {
      // 模拟下载完成
      setTimeout(function () {
        var downloadLink = document.getElementById("downloadLink");
        downloadLink.style.display = "flex";
        downloadLink.href = "#";
        downloadLink.download = fileName;

        showNotification("文件准备就绪，点击下载");

        receiveBtn.disabled = false;
        receiveBtn.innerHTML = '<span class="btn-icon">⬇️</span>领取文件';
      }, 2000);
    })
    .catch(function (err) {
      showNotification(err.message || "领取失败");
      receiveBtn.disabled = false;
      receiveBtn.innerHTML = '<span class="btn-icon">⬇️</span>领取文件';
    });
};

// 模拟进度更新
function simulateProgress() {
  var progressFill = document.querySelector(".progress-fill");
  var progressPercent = document.querySelector(".progress-percent");
  var width = 0;

  var interval = setInterval(function () {
    if (width >= 100) {
      clearInterval(interval);
      progressPercent.textContent = "100%";
      progressFill.style.width = "100%";
    } else {
      width += Math.random() * 10 + 5;
      if (width > 100) width = 100;
      progressFill.style.width = width + "%";
      progressPercent.textContent = Math.floor(width) + "%";
    }
  }, 200);
}

// 举报按钮
document.getElementById("reportBtn").onclick = function () {
  var reason = prompt("请描述举报原因（违规内容、侵权等）：");
  if (!reason) return;

  if (!API_BASE) {
    showNotification("请先测试端口连接");
    return;
  }

  fetch(API_BASE + "/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code: pickupCode, reason: reason }),
  })
    .then(function (res) {
      return res.json();
    })
    .then(function (json) {
      showNotification(json.msg || "举报已提交，感谢您的反馈");
    })
    .catch(function () {
      showNotification("网络错误，请稍后重试");
    });
};

// 页面加载完成后初始化
document.addEventListener("DOMContentLoaded", function () {
  // 自动测试默认端口
  setTimeout(function () {
    document.getElementById("testBtn").click();
  }, 1000);

  // 输入取件码时自动转大写
  document.getElementById("inputCode").addEventListener("input", function (e) {
    this.value = this.value.toUpperCase();
  });
});
