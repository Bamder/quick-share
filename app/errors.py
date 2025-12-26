from fastapi import HTTPException
from typing import Optional

class CustomHTTPException(HTTPException):
    def __init__(self, status_code=400, detail="请求错误", code=None, msg=None):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code if code is not None else status_code
        self.msg = msg if msg is not None else detail

class CodeNotFoundException(CustomHTTPException):
    def __init__(self, code: str):
        super().__init__(status_code=404, detail=f"取件码 {code} 不存在", code=404, msg="取件码不存在")

class FileNotFoundException(CustomHTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="文件不存在", code=404, msg="文件不存在")

class UsageLimitExceededException(CustomHTTPException):
    def __init__(self):
        super().__init__(status_code=400, detail="已达到使用上限", code=400, msg="已达到使用上限")
