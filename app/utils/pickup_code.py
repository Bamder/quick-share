"""
取件码生成工具
"""
import random
import string
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.pickup_code import PickupCode


def check_and_update_expired_pickup_code(pickup_code: PickupCode, db: Session) -> bool:
    """
    检查取件码是否过期，如果过期则更新状态
    
    参数：
    - pickup_code: 取件码对象
    - db: 数据库会话
    
    返回：
    - True: 已过期并更新状态
    - False: 未过期
    """
    if pickup_code.status == "expired":
        return True
    
    # 检查是否过期
    if pickup_code.expire_at and datetime.utcnow() > pickup_code.expire_at:
        pickup_code.status = "expired"
        db.commit()
        return True
    
    return False


def generate_pickup_code() -> str:
    """
    生成12位取件码（大写字母+数字）
    
    格式：前6位（查找码）+ 后6位（密钥码）
    - 查找码：用于数据库查找，服务器可见
    - 密钥码：用于加密，只有客户端知道
    
    返回：
    - 12位大写字母和数字的组合
    """
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(12))


def generate_unique_pickup_code(db: Session, max_attempts: int = 100) -> str:
    """
    生成唯一的取件码
    
    参数：
    - db: 数据库会话
    - max_attempts: 最大尝试次数（防止无限循环）
    
    返回：
    - 唯一的12位取件码（前6位查找码+后6位密钥码）
    
    异常：
    - RuntimeError: 如果尝试多次后仍无法生成唯一取件码
    """
    for _ in range(max_attempts):
        code = generate_pickup_code()
        # 检查数据库中是否已存在（使用完整12位码）
        existing = db.query(PickupCode).filter(PickupCode.code == code).first()
        if not existing:
            return code
    
    raise RuntimeError(f"无法生成唯一取件码，已尝试 {max_attempts} 次")


def extract_lookup_code(full_code: str) -> str:
    """
    从完整取件码中提取查找码（前6位）
    
    参数：
    - full_code: 完整的12位取件码
    
    返回：
    - 前6位查找码
    """
    if len(full_code) != 12:
        raise ValueError(f"取件码长度错误，应为12位，实际为{len(full_code)}位")
    return full_code[:6]


def extract_key_code(full_code: str) -> str:
    """
    从完整取件码中提取密钥码（后6位）
    
    参数：
    - full_code: 完整的12位取件码
    
    返回：
    - 后6位密钥码
    """
    if len(full_code) != 12:
        raise ValueError(f"取件码长度错误，应为12位，实际为{len(full_code)}位")
    return full_code[6:]

