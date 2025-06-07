from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TelegramUser(Base):
    __tablename__ = "telegram_users"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True)  # Telegram ID
    username = Column(String, nullable=True)
    name = Column(String)

    favorites = relationship("FavoritePlace", back_populates="user", cascade="all, delete-orphan")
