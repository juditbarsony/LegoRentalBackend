# app/identify_dispatcher.py
from fastapi import UploadFile
from app.ai_pipeline import identify_element
from app.routers.brickognize_client import identify_with_brickognize_multi
import asyncio

LOCAL_MODEL_SET_NUM = "10696-1"


def get_identifier_source_for_set(set_num: str) -> str:
    normalized = (set_num or "").strip()
    if normalized == LOCAL_MODEL_SET_NUM:
        return "local_ai"
    return "brickognize"


async def identify_elements_dispatch(file, set_num: str, session_parts: dict | None = None) -> dict:
    identifier_source = get_identifier_source_for_set(set_num)
    print("DEBUG identify_elements_dispatch reached, set_num =", set_num)
    file_bytes = await file.read()
    if not file_bytes:
        return {"error": "Empty uploaded file."}

    filename = file.filename or "upload.jpg"
    content_type = file.content_type or "image/jpeg"

    if identifier_source == "local_ai":
        return await identify_element(
            file_bytes=file_bytes,
            session_parts=session_parts,
            filename=filename,
            content_type=content_type,
        )

    return await identify_with_brickognize_multi(
        file_bytes=file_bytes,
        filename=filename,
        content_type=content_type,
    )

