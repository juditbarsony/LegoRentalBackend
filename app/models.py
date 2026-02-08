#from __future__ import annotations
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

# --- USER MODELS ---

class UserBase(SQLModel):
    email: str = Field(unique=True, index=True)
    full_name: str
    role: str = Field(default="USER")

class User(UserBase, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str

    # A List["LegoSet"] helyett csak a típust adjuk meg, 
    # az SQLModel tudni fogja, hogy ez egy lista a Relationship miatt
    lego_sets: List["LegoSet"] = Relationship(back_populates="owner")
    rentals: List["Rental"] = Relationship(back_populates="renter")

# --- LEGO MODELS ---

class LegoSetBase(SQLModel):
    set_num: str = Field(foreign_key="rebrickable_sets.set_num")
    title: str
    description: Optional[str] = None
    rental_price_per_day: float
    condition: str
    location: str
    available: bool = Field(default=True)

class LegoSet(LegoSetBase, table=True):
    __tablename__ = "lego_sets"
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    owner: Optional["User"] = Relationship(back_populates="lego_sets")
    rentals: List["Rental"] = Relationship(back_populates="lego_set")

# --- RENTAL MODELS ---

class RentalBase(SQLModel):
    lego_set_id: int = Field(foreign_key="lego_sets.id")
    start_date: datetime
    end_date: Optional[datetime] = None
    total_price: float
    status: str = Field(default="ACTIVE")

class Rental(RentalBase, table=True):
    __tablename__ = "rentals"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")

    lego_set: Optional["LegoSet"] = Relationship(back_populates="rentals")
    renter: Optional["User"] = Relationship(back_populates="rentals")

# --- REBRICKABLE MODELS ---

class RebrickableTheme(SQLModel, table=True):
    __tablename__ = "rebrickable_themes"
    id: int = Field(primary_key=True)
    name: str
    parent_id: Optional[int] = Field(default=None, foreign_key="rebrickable_themes.id")

class RebrickableSet(SQLModel, table=True):
    __tablename__ = "rebrickable_sets"
    set_num: str = Field(primary_key=True)
    name: str
    year: int
    theme_id: int = Field(foreign_key="rebrickable_themes.id")
    num_parts: int
    img_url: Optional[str] = None
