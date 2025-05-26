from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    user_id = Column(String(50), primary_key=True, index=True)
    nickname = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    hashed_password = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    
    plants = relationship("Plant", back_populates="owner")

class Plant(Base):
    __tablename__ = "plants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(100), nullable=False)
    watering_cycle = Column(Integer, nullable=False)
    last_watered = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(String(50), ForeignKey("users.user_id"), nullable=False)
    
    owner = relationship("User", back_populates="plants")

class PlantLed(Base):
    __tablename__ = "plant_leds"

    id = Column(Integer, primary_key=True, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    mode = Column(String(50), nullable=False)
    r = Column(Integer, nullable=False)
    g = Column(Integer, nullable=False)
    b = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plant = relationship("Plant") 