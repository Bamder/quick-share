"""
取件码生成工具
"""
import random
import string
from sqlalchemy.orm import Session
from app.models.pickup_code import PickupCode


def generate_pickup_code() -> str:
    """
    生成6位取件码（大写字母+数字）
    
    返回：
    - 6位大写字母和数字的组合
    """
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(6))


def generate_unique_pickup_code(db: Session, max_attempts: int = 100) -> str:
    """
    生成唯一的取件码
    
    参数：
    - db: 数据库会话
    - max_attempts: 最大尝试次数（防止无限循环）
    
    返回：
    - 唯一的6位取件码
    
    异常：
    - RuntimeError: 如果尝试多次后仍无法生成唯一取件码
    """
    for _ in range(max_attempts):
        code = generate_pickup_code()
        # 检查数据库中是否已存在
        existing = db.query(PickupCode).filter(PickupCode.code == code).first()
        if not existing:
            return code
    
    raise RuntimeError(f"无法生成唯一取件码，已尝试 {max_attempts} 次")

