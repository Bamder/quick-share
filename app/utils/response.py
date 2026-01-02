from typing import Any, Optional
from pydantic import BaseModel


class StandardResponse(BaseModel):
    """标准响应格式"""
    code: int
    msg: str
    data: Optional[Any] = None


def success_response(data: Any = None, msg: str = "success") -> dict:
    """成功响应"""
    return {
        "code": 200,
        "msg": msg,
        "data": data
    }


def error_response(code: int = 400, msg: str = "请求错误", data: Any = None) -> dict:
    """错误响应"""
    return {
        "code": code,
        "msg": msg,
        "data": data
    }


def created_response(data: Any = None, msg: str = "创建成功") -> dict:
    """创建成功响应"""
    return {
        "code": 201,
        "msg": msg,
        "data": data
    }


def not_found_response(msg: str = "资源不存在", data: Any = None) -> dict:
    """资源不存在响应"""
    return error_response(404, msg, data)


def bad_request_response(msg: str = "请求参数错误", data: Any = None) -> dict:
    """请求参数错误响应"""
    return error_response(400, msg, data)


def rate_limit_response(retry_after: int = 60) -> dict:
    """频率限制响应"""
    return error_response(429, "请求过于频繁，请稍后再试", {"retryAfter": retry_after})