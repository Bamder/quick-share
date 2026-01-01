/**
 * 文件处理工具函数
 * 负责所有与文件操作相关的工具方法
 */

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

/**
 * 将文件分割成块（用于传输）
 * @param {File|Blob} file 要分割的文件
 * @param {number} chunkSize 每个块的大小（字节），默认64KB
 * @returns {Array<Blob>} 文件块数组
 */
export function splitFileIntoChunks(file, chunkSize = 64 * 1024) {
    const chunks = [];
    let offset = 0;

    while (offset < file.size) {
        const chunk = file.slice(offset, offset + chunkSize);
        chunks.push(chunk);
        offset += chunkSize;
    }

    return chunks;
}

/**
 * 从块重建文件
 * @param {Array<Blob>} chunks 文件块数组
 * @param {string} fileName 文件名（可选，用于下载）
 * @param {string} mimeType MIME类型
 * @returns {Blob} 重建的文件Blob
 */
export function reconstructFileFromChunks(chunks, fileName = null, mimeType = 'application/octet-stream') {
    return new Blob(chunks, { type: mimeType });
}

/**
 * 创建下载链接并触发下载
 * @param {Blob} blob 文件Blob
 * @param {string} fileName 文件名
 */
export function downloadBlob(blob, fileName) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

