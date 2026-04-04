from pydantic import BaseModel, EmailStr
from typing import Optional, List
from app.models import UserBase
from datetime import date, datetime
from sqlmodel import SQLModel, Field
from app.enums import LegoSetState
from app.enums import RentalStatus



# We can inherit from UserBase to avoid duplication
class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: int

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None


# --- LEGO SET SCHEMAS ---

class LegoSetBase(SQLModel):
    set_num: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    location: str

    rental_price: float = 0.0
    deposit: float = 0.0
    scan_required: bool = False

    state: LegoSetState | None = None  # "NEW" / "USED" / "TRASH"
    missing_items: Optional[List[str]] = None   # part number lista
    notes: Optional[str] = None

    public: bool = True
    img_url: str | None = None 
class LegoSetCreate(LegoSetBase):
    """
    Legalább az egyik kötelező: set_num vagy title.
    A backend fogja beolvasni a RebrickableSet-et set_num alapján,
    és abból származtatjuk number_of_items-et.
    """
class LegoSetUpdate(SQLModel):
    rental_price: Optional[float] = None
    deposit: Optional[float] = None
    scan_required: Optional[bool] = None
    state: Optional[LegoSetState] = None  # vagy Optional[str]
    notes: Optional[str] = None
    public: Optional[bool] = None


class LegoSetRead(LegoSetBase):
    id: int
    owner_id: int
    created_at: datetime
    number_of_items: Optional[int] = None
    img_url: Optional[str] = None
    
class AvailabilityBase(SQLModel):
    start_date: date
    end_date: date

class AvailabilityCreate(AvailabilityBase):
    pass

class AvailabilityRead(AvailabilityBase):
    id: int
    lego_set_id: int
    
class RentalBase(SQLModel):
    lego_set_id: int
    start_date: date
    end_date: date

class RentalCreate(RentalBase):
    pass

class RentalRead(RentalBase):
    id: int
    renter_id: int
    total_price: float
    status: RentalStatus
    created_at: datetime
    updated_at: datetime
    
# --- SCAN SCHEMAS ---

class ScanItemRead(BaseModel):
    id: int
    session_id: int
    part_num: str
    name: Optional[str] = None
    color: Optional[str] = None
    img_url: Optional[str] = None
    status: str  # "ai_identified" | "manually_confirmed" | "missing"
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    confidence: Optional[float] = None

    class Config:
        from_attributes = True

class ScanSessionCreate(BaseModel):
    rental_id: int
    lego_set_id: int

class ScanSessionRead(BaseModel):
    id: int
    rental_id: int
    lego_set_id: int
    scanned_at: datetime
    status: str
    items: List[ScanItemRead] = []

    class Config:
        from_attributes = True

class ScanIdentifyResult(BaseModel):
    part_num: str
    color_name: Optional[str] = None
    confidence: float
    detection_confidence: float        # YOLO box confidence
    bounding_box: dict                 # x1, y1, x2, y2

class ScanIdentifyResponse(BaseModel):
    count: int
    elements: List[ScanIdentifyResult]  # ← lista, nem egy elem
    
######   batch mark endpoint    #######

class MarkBatchElement(BaseModel):
    part_num: str
    color_name: Optional[str] = None
    confidence: float

class MarkBatchRequest(BaseModel):
    elements: List[MarkBatchElement]


