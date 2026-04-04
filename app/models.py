#from __future__ import annotations
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, date
from app.enums import LegoSetState, RentalStatus
from typing import Optional
from sqlalchemy import PrimaryKeyConstraint



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
    location: str
    rental_price: float = 0.0
    deposit: float = 0.0
    scan_required: bool = False
    state: Optional[str] = None
    notes: Optional[str] = None
    public: bool = True
    img_url: Optional[str] = None

class LegoSet(SQLModel, table=True):
    __tablename__ = "lego_sets"

    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    

    # Rebrickable kapcsolat
    set_num: str = Field(foreign_key="rebrickable_sets.set_num", index=True)
    title: str
    img_url: Optional[str] = Field(default=None)


    # Wireframe mezők
    location: str = Field(index=True)
    rental_price: float = Field(default=0.0)
    deposit: float = Field(default=0.0)
    scan_required: bool = Field(default=False)
    
    state: Optional[str] = Field(default=None)  # "NEW" / "USED" / "TRASH"
    notes: Optional[str] = Field(default=None)
    public: bool = Field(default=True)

    number_of_items: Optional[int] = Field(default=None)
    missing_items_raw: Optional[str] = Field(default=None)
    

    # Relationships
    owner: Optional["User"] = Relationship(back_populates="lego_sets")
    rentals: List["Rental"] = Relationship(back_populates="lego_set")
    availabilities: List["Availability"] = Relationship(back_populates="lego_set")

# --- RENTAL MODELS ---

class RentalBase(SQLModel):
    lego_set_id: int = Field(foreign_key="lego_sets.id")
    start_date: datetime
    end_date: Optional[datetime] = None
    total_price: float
    status: str = Field(default="REQUESTED")

class Rental(SQLModel, table=True):
    __tablename__ = "rentals"
    id: Optional[int] = Field(default=None, primary_key=True)
    lego_set_id: int = Field(foreign_key="lego_sets.id", index=True)
    renter_id: int = Field(foreign_key="users.id", index=True)  # user_id → renter_id (tisztább név)
    
    start_date: date
    end_date: date
    total_price: float
    status: RentalStatus = Field(default=RentalStatus.REQUESTED)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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

    # --- Availability ---
    
class Availability(SQLModel, table=True):
    __tablename__ = "availabilities"

    id: Optional[int] = Field(default=None, primary_key=True)
    lego_set_id: int = Field(foreign_key="lego_sets.id", index=True)
    start_date: date
    end_date: date

    lego_set: Optional["LegoSet"] = Relationship(back_populates="availabilities")
    
# --- SCAN MODELS ---

class ScanSession(SQLModel, table=True):
    __tablename__ = "scan_sessions"
    id: Optional[int] = Field(default=None, primary_key=True)
    rental_id: int = Field(foreign_key="rentals.id", index=True)
    lego_set_id: int = Field(foreign_key="lego_sets.id", index=True)
    scanned_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="INCOMPLETE")  # COMPLETE / INCOMPLETE
    items: List["ScanItem"] = Relationship(back_populates="session")



class ScanItem(SQLModel, table=True):
    __tablename__ = "scan_items"
    id: Optional[int] = Field(default=None, primary_key=True)  # ← EZ HIÁNYZIK
    session_id: int = Field(foreign_key="scan_sessions.id", index=True)
    part_num: str
    name: Optional[str] = Field(default=None)
    color: Optional[str] = Field(default=None)
    img_url: Optional[str] = Field(default=None)
    status: str = Field(default="missing")  # "ai_identified" | "manually_confirmed" | "missing"
    confirmed_by: Optional[int] = Field(default=None, foreign_key="users.id")
    confirmed_at: Optional[datetime] = Field(default=None)
    confidence: Optional[float] = Field(default=None)
    session: Optional["ScanSession"] = Relationship(back_populates="items")


#----------Rebrickable models-----------------
class RbInventory(SQLModel, table=True):
    __tablename__ = "rb_inventories"

    id: int = Field(primary_key=True)
    version: int
    set_num: str = Field(index=True)


class RbInventoryPart(SQLModel, table=True):
    __tablename__ = "rb_inventory_parts"

    inventory_id: int = Field(primary_key=True)
    part_num: str = Field(primary_key=True)
    color_id: int = Field(primary_key=True)
    is_spare: bool = Field(default=False, primary_key=True)
    quantity: int
    img_url: Optional[str] = None


class RbPart(SQLModel, table=True):
    __tablename__ = "rb_parts"

    part_num: str = Field(primary_key=True)
    name: str
    part_cat_id: Optional[int] = None
    part_material: Optional[str] = None


class RbColor(SQLModel, table=True):
    __tablename__ = "rb_colors"

    id: int = Field(primary_key=True)
    name: str
    rgb: Optional[str] = None
    is_trans: Optional[bool] = None
