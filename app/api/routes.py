
from fastapi import APIRouter

router = APIRouter()


@router.get("/demo")
def demo():
    return {"message": "LEGO rental backend demo endpoint"}
