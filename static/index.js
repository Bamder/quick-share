// 后端地址
var API_BASE = '';

// 全局变量
var localFile      = null;
var pickupCode     = '';
var shareExpireMin = 30;
var shareLimit     = 3;
var pc             = null;
var dc             = null;
var receiveBuffer  = [];
var fileSize       = 0;
var fileName       = '';

// 端口测试函数
function testPort(host, port) {
  var url = 'http://' + host + ':' + port + '/api/status';
  return fetch(url, {method: 'GET'})
    .then(function(res){ return res.ok; })
    .catch(function(){ return false; });
}

// 端口验证按钮事件
document.getElementById('testBtn').onclick = function () {
  var port = document.getElementById('portInput').value;
  document.getElementById('portResult').textContent = '检测中...';
  testPort(location.hostname, port).then(function(ok){
    API_BASE = 'http://' + location.hostname + ':' + port + '/api';
    document.getElementById('portResult').textContent = ok ? '端口通畅，连好了' : '端口不通';
  });
};

// 文件选择事件
document.getElementById('fileInput').onchange = function () {
  if (this.files.length) handleFile(this.files[0]);
};

// 拖拽事件
document.getElementById('dropArea').onclick = function () {
  document.getElementById('fileInput').click();
};

['dragenter', 'dragover'].forEach(function(evt){
  document.getElementById('dropArea').addEventListener(evt, function(e){
    e.preventDefault(); this.classList.add('dragover');
  });
});

['dragleave', 'drop'].forEach(function(evt){
  document.getElementById('dropArea').addEventListener(evt, function(e){
    e.preventDefault(); this.classList.remove('dragover');
  });
});

document.getElementById('dropArea').addEventListener('drop', function(e){
  var files = e.dataTransfer.files; if (files.length) handleFile(files[0]);
});

// 处理文件函数
function handleFile(file) {
  localFile = file;
  document.getElementById('fileName').textContent = file.name + ' (' + (file.size/1024/1024).toFixed(2) + ' MB)';
  document.getElementById('shareBtn').disabled = false;
  if (file.type.startsWith('image/')) {
    var reader = new FileReader();
    reader.onload = function(ev){
      document.getElementById('preview').innerHTML = '<img src="' + ev.target.result + '" alt="预览" style="max-width:200px">';
    };
    reader.readAsDataURL(file);
  }
}

// 生成取件码按钮事件
document.getElementById('shareBtn').onclick = function () {
  if (!localFile) return;
  pickupCode = Array.from({length:6}, function(){
    return '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'[Math.floor(Math.random() * 36)];
  }).join('');
  document.getElementById('codeSec').style.display = 'block';
  document.getElementById('pickupCode').textContent = pickupCode;
  startStatusPolling();
};

// 复制按钮
document.getElementById('copyCodeBtn').onclick = function (){
  navigator.clipboard.writeText(pickupCode).then(function(){ alert('已复制'); });
};

// 状态轮询
function startStatusPolling() {
  setInterval(function (){
    fetch(API_BASE + '/status?code=' + pickupCode)
      .then(function(res){ return res.json(); })
      .then(function(json){
        if (json.code !== 200) return;
        var d = json.data;
        document.getElementById('statSize').textContent = (d.fileSize / 1024 / 1024).toFixed(2) + ' MB';
        document.getElementById('statCount').textContent = d.used + ' / ' + (d.limit === 999 ? '∞' : d.limit);
        document.getElementById('statStatus').textContent = d.status;
        var left = new Date(d.expireAt) - Date.now();
        var min = Math.floor(left / 60000);
        var sec = Math.floor((left % 60000) / 1000);
        document.getElementById('statTime').textContent = min + ':' + sec.toString().padStart(2, '0');
      })
      .catch(function(){});
  }, 1000);
}

// 领取按钮事件
document.getElementById('receiveBtn').onclick = function (){
  var code = document.getElementById('inputCode').value.trim().toUpperCase();
  if (!code) { alert('请输入取件码'); return; }
  fetch(API_BASE + '/receive?code=' + code)
    .then(function(res){ return res.json(); })
    .then(function(json){
      if (json.code !== 200) { alert(json.msg || '领取失败'); return; }
      var d = json.data;
      fileName = d.fileName; fileSize = d.fileSize;
      document.getElementById('recvProgressBar').style.display = 'block';
      return fetch(API_BASE + '/answer', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({code: code, answer: '', ice: []})   // 
      });
    })
    .then(function(){})
    .catch(function(){ alert('网络错误'); });
};

// 举报按钮
document.getElementById('reportBtn').onclick = function (){
  var reason = prompt('请描述举报原因：');
  if (!reason) return;
  fetch(API_BASE + '/report', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({code: pickupCode, reason: reason})
  }).then(function(res){ return res.json(); })
    .then(function(json){ alert(json.msg || '举报已提交'); })
    .catch(function(){ alert('网络错误'); });
};