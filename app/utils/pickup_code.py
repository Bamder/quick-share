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


def generate_unique_lookup_code(db: Session, max_attempts: int = 100) -> str:
    """
    生成唯一的6位查找码（用于数据库存储）
    
    参数：
    - db: 数据库会话
    - max_attempts: 最大尝试次数（防止无限循环）
    
    返回：
    - 唯一的6位查找码（只存储到数据库，不包含密钥码）
    
    异常：
    - RuntimeError: 如果尝试多次后仍无法生成唯一查找码
    """
    chars = string.ascii_uppercase + string.digits
    for _ in range(max_attempts):
        lookup_code = ''.join(random.choice(chars) for _ in range(6))
        # 检查数据库中是否已存在（只检查6位查找码）
        existing = db.query(PickupCode).filter(PickupCode.code == lookup_code).first()
        if not existing:
            return lookup_code
    
    raise RuntimeError(f"无法生成唯一查找码，已尝试 {max_attempts} 次")


def generate_unique_pickup_code(db: Session, max_attempts: int = 100) -> tuple[str, str]:
    """
    生成完整的12位取件码（前端使用）
    
    参数：
    - db: 数据库会话
    - max_attempts: 最大尝试次数（防止无限循环）
    
    返回：
    - (lookup_code, full_code) 元组
      - lookup_code: 6位查找码（存储到数据库）
      - full_code: 12位完整取件码（前6位查找码+后6位密钥码，返回给前端）
    
    异常：
    - RuntimeError: 如果尝试多次后仍无法生成唯一查找码
    """
    # 生成唯一的6位查找码（存储到数据库）
    lookup_code = generate_unique_lookup_code(db, max_attempts)
    
    # 生成6位密钥码（只在客户端使用，不存储到数据库）
    chars = string.ascii_uppercase + string.digits
    key_code = ''.join(random.choice(chars) for _ in range(6))
    
    # 组合成12位完整取件码（返回给前端）
    full_code = lookup_code + key_code
    
    return lookup_code, full_code


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

