"""
取件码生成工具和时间处理工具
"""
import random
import string
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Union
from sqlalchemy.orm import Session
from app.models.pickup_code import PickupCode


def ensure_aware_datetime(dt: datetime) -> datetime:
    """
    确保 datetime 是 aware 的（有时区信息）
    如果传入的是 naive datetime，假设它是 UTC 时间并添加时区信息
    
    参数：
    - dt: datetime 对象（可能是 naive 或 aware）
    
    返回：
    - aware datetime 对象（UTC 时区）
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # 如果是 naive datetime，假设它是 UTC 时间
        return dt.replace(tzinfo=timezone.utc)
    return dt


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

    # 使用DatetimeUtil检查是否过期
    if DatetimeUtil.is_expired(pickup_code.expire_at):
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
    
    异常：
    - ValueError: 如果取件码格式无效（长度或字符格式）
    """
    if len(full_code) != 12:
        raise ValueError(f"取件码长度错误，应为12位，实际为{len(full_code)}位")
    # 验证字符格式（只允许大写字母和数字）
    if not re.match(r'^[A-Z0-9]{12}$', full_code):
        raise ValueError(f"取件码格式错误，只能包含大写字母和数字")
    return full_code[:6]


def extract_key_code(full_code: str) -> str:
    """
    从完整取件码中提取密钥码（后6位）

    参数：
    - full_code: 完整的12位取件码

    返回：
    - 后6位密钥码
    
    异常：
    - ValueError: 如果取件码格式无效（长度或字符格式）
    """
    if len(full_code) != 12:
        raise ValueError(f"取件码长度错误，应为12位，实际为{len(full_code)}位")
    # 验证字符格式（只允许大写字母和数字）
    if not re.match(r'^[A-Z0-9]{12}$', full_code):
        raise ValueError(f"取件码格式错误，只能包含大写字母和数字")
    return full_code[6:]


class DatetimeUtil:
    """
    时间处理工具类

    提供安全的datetime操作，避免naive和aware datetime混合使用的问题
    """

    @staticmethod
    def now() -> datetime:
        """
        获取当前UTC时间（aware datetime）

        返回：
        - 当前UTC时间的aware datetime对象
        """
        return datetime.now(timezone.utc)

    @staticmethod
    def ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
        """
        确保datetime对象是aware的

        参数：
        - dt: datetime对象（可能是naive或aware）

        返回：
        - aware datetime对象，如果输入为None则返回None
        """
        return ensure_aware_datetime(dt)

    @staticmethod
    def is_expired(expire_at: Optional[datetime], now: Optional[datetime] = None) -> bool:
        """
        检查时间是否过期

        参数：
        - expire_at: 过期时间
        - now: 当前时间（可选，默认使用当前UTC时间）

        返回：
        - True: 已过期
        - False: 未过期
        """
        if expire_at is None:
            return False

        if now is None:
            now = DatetimeUtil.now()

        # 确保两个时间都是aware的
        expire_at = DatetimeUtil.ensure_aware(expire_at)
        now = DatetimeUtil.ensure_aware(now)

        return now > expire_at

    @staticmethod
    def add_hours(dt: datetime, hours: float) -> datetime:
        """
        在datetime上添加小时数

        参数：
        - dt: 基准时间
        - hours: 要添加的小时数（支持小数）

        返回：
        - 添加小时后的datetime
        """
        dt = DatetimeUtil.ensure_aware(dt)
        return dt + timedelta(hours=hours)

    @staticmethod
    def compare(dt1: Optional[datetime], dt2: Optional[datetime]) -> int:
        """
        安全的datetime比较

        参数：
        - dt1: 第一个datetime
        - dt2: 第二个datetime

        返回：
        - -1: dt1 < dt2
        -  0: dt1 == dt2
        -  1: dt1 > dt2
        - 如果任一为None，按None最小处理
        """
        if dt1 is None and dt2 is None:
            return 0
        if dt1 is None:
            return -1
        if dt2 is None:
            return 1

        # 确保都是aware的
        dt1 = DatetimeUtil.ensure_aware(dt1)
        dt2 = DatetimeUtil.ensure_aware(dt2)

        if dt1 < dt2:
            return -1
        elif dt1 > dt2:
            return 1
        else:
            return 0

    @staticmethod
    def format_for_db(dt: datetime, naive: bool = False) -> datetime:
        """
        格式化datetime用于数据库存储

        参数：
        - dt: datetime对象
        - naive: 是否转换为naive datetime（去除时区信息）

        返回：
        - 适合数据库存储的datetime
        """
        dt = DatetimeUtil.ensure_aware(dt)
        if naive:
            # 转换为naive datetime（UTC时间，无时区信息）
            return dt.replace(tzinfo=None)
        else:
            # 保持aware datetime（推荐，用于支持时区）
            return dt

    @staticmethod
    def is_valid_expire_hours(hours: float) -> bool:
        """
        检查过期小时数是否有效

        参数：
        - hours: 小时数

        返回：
        - True: 有效
        - False: 无效
        """
        return isinstance(hours, (int, float)) and 0.1 <= hours <= 168.0  # 0.1小时到7天

    @staticmethod
    def to_iso_string(dt: Optional[datetime]) -> Optional[str]:
        """
        将datetime转换为ISO格式字符串

        参数：
        - dt: datetime对象

        返回：
        - ISO格式字符串（带Z后缀表示UTC），如果输入为None则返回None
        """
        if dt is None:
            return None
        dt = DatetimeUtil.ensure_aware(dt)
        return dt.isoformat() + "Z"

    @staticmethod
    def time_diff_hours(dt1: Optional[datetime], dt2: Optional[datetime]) -> Optional[float]:
        """
        计算两个时间之间的小时差

        参数：
        - dt1: 第一个时间
        - dt2: 第二个时间

        返回：
        - 小时差（dt1 - dt2），如果任一为None则返回None
        """
        if dt1 is None or dt2 is None:
            return None

        dt1 = DatetimeUtil.ensure_aware(dt1)
        dt2 = DatetimeUtil.ensure_aware(dt2)

        diff = dt1 - dt2
        return diff.total_seconds() / 3600

    @staticmethod
    def is_future(dt: Optional[datetime], now: Optional[datetime] = None) -> bool:
        """
        检查时间是否是未来的时间

        参数：
        - dt: 要检查的时间
        - now: 当前时间基准（可选）

        返回：
        - True: 是未来的时间
        - False: 不是未来的时间或已过期
        """
        if dt is None:
            return False

        if now is None:
            now = DatetimeUtil.now()

        return DatetimeUtil.compare(dt, now) > 0

    @staticmethod
    def is_past(dt: Optional[datetime], now: Optional[datetime] = None) -> bool:
        """
        检查时间是否是过去的时间

        参数：
        - dt: 要检查的时间
        - now: 当前时间基准（可选）

        返回：
        - True: 是过去的时间
        - False: 不是过去的时间或还未到
        """
        if dt is None:
            return False

        if now is None:
            now = DatetimeUtil.now()

        return DatetimeUtil.compare(dt, now) < 0

