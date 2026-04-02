from fastapi import APIRouter, UploadFile, File, HTTPException
from app.ai_pipeline import identify_element

router = APIRouter(prefix="/ai", tags=["ai"])

@router.post("/identify")
async def identify_lego_element(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are accepted.")

    result = await identify_element(file)

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    return result
