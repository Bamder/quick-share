# models/base.py
from sqlalchemy.ext.declarative import declarative_base

# 生成一个基类，所git add app有数据库模型都要继承这个类
Base = declarative_base()