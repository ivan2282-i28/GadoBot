from sqlalchemy import Column, Integer, String, BigInteger, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs

class Base(AsyncAttrs, DeclarativeBase):
    pass

class Warn(Base):
    __tablename__ = "warns"
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, index=True)
    user_id = Column(BigInteger, index=True)
    count = Column(Integer, default=0)
    __table_args__ = (UniqueConstraint('chat_id', 'user_id', name='_chat_user_warn_uc'),)

class ChatSettings(Base):
    __tablename__ = "chat_settings"
    chat_id = Column(BigInteger, primary_key=True)
    warn_limit = Column(Integer, default=3)
    lang = Column(String, default="eng")

class Blacklist(Base):
    __tablename__ = "blacklist"
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, index=True)
    user_id = Column(BigInteger)
    __table_args__ = (UniqueConstraint('chat_id', 'user_id', name='_chat_user_bl_uc'),)

class CustomFilter(Base):
    __tablename__ = "filters"
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, index=True)
    trigger = Column(String)
    response = Column(String)
    file_id = Column(String, nullable=True) 
    file_type = Column(String, nullable=True) 
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, index=True)
    lang = Column(String, default="eng")