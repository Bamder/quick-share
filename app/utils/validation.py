import re
from typing import Optional


def validate_pickup_code(code: str) -> bool:
    """
    验证取件码格式
    
    规则：6位大写字母或数字
    正则：^[A-Z0-9]{6}$
    
    示例：
    - WAIT01 ✓
    - TRAN02 ✓
    - ABC123 ✓
    - abc123 ✗ (小写)
    - ABC12 ✗ (5位)
    """
    pattern = r'^[A-Z0-9]{6}$'
    return bool(re.match(pattern, code))


def validate_session_id(session_id: str) -> bool:
    """验证会话ID格式"""
    return bool(session_id and len(session_id) <= 64)


def validate_ip_address(ip: str) -> bool:
    """简单验证IP地址格式"""
    import socket
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False


def validate_file_size(size_bytes: int, max_mb: int = 100) -> bool:
    """验证文件大小"""
    max_bytes = max_mb * 1024 * 1024
    return 0 < size_bytes <= max_bytes


def validate_mime_type(mime_type: str) -> bool:
    """验证MIME类型格式"""
    # 简单的MIME类型验证
    if not mime_type or '/' not in mime_type:
        return False
    return True