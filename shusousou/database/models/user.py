"""
书搜搜 - 用户模型
负责：用户表结构（部门2维护）
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from . import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    is_verified = Column(Boolean, default=False)
    verify_code = Column(String(10), nullable=True)
    verify_code_expire = Column(DateTime, nullable=True)
    verify_token = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    # 关联
    posts = relationship("Post", back_populates="user")
    comments = relationship("Comment", back_populates="user")
    exchange_books = relationship("ExchangeBook", back_populates="owner")

