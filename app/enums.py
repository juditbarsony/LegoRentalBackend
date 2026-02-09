from enum import Enum

class LegoSetState(str, Enum):
    NEW = "NEW"
    USED = "USED"
    TRASH = "TRASH"


class RentalStatus(str, Enum):
    REQUESTED = "REQUESTED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    RETURN_PENDING = "RETURN_PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
