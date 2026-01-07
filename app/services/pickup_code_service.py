from typing import Optional
from sqlalchemy.orm import Session
from app.models.pickup_code import PickupCode

def get_pickup_code_by_lookup(db: Session, lookup_code: str) -> Optional[PickupCode]:
    """
    使用查找码（6位）查询取件码
    
    参数：
    - db: 数据库会话
    - lookup_code: 6位查找码（服务器只接收查找码，不接触密钥码）
    
    返回：
    - PickupCode对象，如果找到
    - None，如果未找到
    
    安全性：
    - 服务器只接收和查询6位查找码
    - 后6位密钥码完全不进入服务器
    """
    # 直接使用6位查找码查询数据库
    pickup_code = db.query(PickupCode).filter(
        PickupCode.code == lookup_code
    ).first()
    
    return pickup_code