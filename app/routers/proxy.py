import httpx
from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter(prefix="/proxy", tags=["proxy"])

@router.get("/image")
async def proxy_image(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    return Response(
        content=response.content,
        media_type=response.headers.get("content-type", "image/jpeg"),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=86400",
        }
    )



