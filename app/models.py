from __future__ import annotations
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey
from typing import Optional, List
from datetime import datetime
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base
from app.database import Base

# RebrickableSet és RebrickableTheme változatlan...

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="USER")

    # Javított kapcsolat
    sets: Mapped[List["LegoSet"]] = relationship(back_populates="owner")

class LegoSet(SQLModel, table=True):
    __tablename__ = "lego_sets"
    
    id: Mapped[Optional[int]] = mapped_column(primary_key=True)
    set_num: Mapped[str] = mapped_column(ForeignKey("rebrickable_sets.set_num"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str]
    description: Mapped[Optional[str]]
    rental_price_per_day: Mapped[float]
    condition: Mapped[str]
    location: Mapped[str]
    available: Mapped[bool] = Field(default=True)
    created_at: Mapped[datetime] = Field(default_factory=datetime.utcnow)

    # Javított kapcsolatok
    owner: Mapped["User"] = relationship(back_populates="sets")
    rentals: Mapped[List["Rental"]] = relationship(back_populates="lego_set")

class Rental(SQLModel, table=True):
    __tablename__ = "rentals"
    id: Mapped[Optional[int]] = mapped_column(primary_key=True)
    lego_set_id: Mapped[int] = mapped_column(ForeignKey("lego_sets.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    start_date: datetime
    end_date: Optional[datetime]
    total_price: float
    status: str = Field(default="ACTIVE")
    
    lego_set: Mapped["LegoSet"] = relationship(back_populates="rentals")
    renter: Mapped["User"] = relationship(back_populates="rentals")
