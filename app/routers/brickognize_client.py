import cv2
import httpx
import numpy as np
import asyncio

from app.ai_pipeline import detect_elements


BRICKOGNIZE_PARTS_URL = "https://api.brickognize.com/predict/parts/"





# async def identify_single_crop_with_brickognize(
#     crop_bytes: bytes,
#     filename: str = "crop.jpg",
#     content_type: str = "image/jpeg",
# ) -> dict:
#     files = {
#         "query_image": (filename, crop_bytes, content_type)
#     }

#     async with httpx.AsyncClient(timeout=30.0) as client:
#         response = await client.post(BRICKOGNIZE_PARTS_URL, files=files)

#     if response.status_code != 200:
#         return {"error": f"Brickognize request failed ({response.status_code})"}

#     data = response.json()

async def identify_single_crop_with_brickognize(
    crop_bytes: bytes,
    filename: str = "crop.jpg",
    content_type: str = "image/jpeg",
) -> dict:
    files = {
        "query_image": (filename, crop_bytes, content_type)
    }

    try:
        async with httpx.AsyncClient(timeout=10.0 ) as client: # Rövidebb timeout teszthez
            response = await client.post(BRICKOGNIZE_PARTS_URL, files=files)
            response.raise_for_status() # Ez hibát dob, ha nem 200-as a válasz
    except Exception as e:
        print(f"DEBUG Brickognize API Error: {str(e)}") # Ez már meg kell jelenjen a konzolon!
        return {"error": f"Brickognize API connection error: {str(e)}"}

    data = response.json()
    items = data.get("items", [])
    if not items:
        return {"error": "No Brickognize matches returned."}

    top = items[0]
    bbox = data.get("bounding_box") or {}

    return {
        "elem_id": top["id"],
        "color": None,
        "confidence": float(top.get("score", 0.0)),
        "detection_confidence": float(bbox.get("score", 0.0)),
        "brickognize_bbox": {
            "x1": bbox.get("left"),
            "y1": bbox.get("upper"),
            "x2": bbox.get("right"),
            "y2": bbox.get("lower"),
        },
        "name": top.get("name"),
        "type": top.get("type"),
        "category": top.get("category"),
        "img_url": top.get("img_url"),
    }


def expand_bbox(x1, y1, x2, y2, img_w, img_h, pad_ratio=0.05):
    w = x2 - x1
    h = y2 - y1
    pad_x = int(w * pad_ratio)
    pad_y = int(h * pad_ratio)

    return (
        int(max(0, x1 - pad_x)),
        int(max(0, y1 - pad_y)),
        int(min(img_w, x2 + pad_x)),
        int(min(img_h, y2 + pad_y)),
    )



async def identify_with_brickognize_multi(
    file_bytes: bytes,
    filename: str = "image.jpg",
    content_type: str = "image/jpeg",
) -> dict:
    np_arr = np.frombuffer(file_bytes, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img_bgr is None:
        return {"error": "Failed to decode image."}

    img_h, img_w = img_bgr.shape[:2]
    detections = detect_elements(img_bgr, min_conf=0.50)

    if not detections:
        return {"error": "No LEGO element detected in image."}

    elements = []
    
    print("DEBUG total detections =", len(detections))

    for idx, det in enumerate(detections):
        x1, y1, x2, y2 = expand_bbox(
            det["x1"], det["y1"], det["x2"], det["y2"], img_w, img_h, pad_ratio=0.15
        )

        crop = img_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            print(f"DEBUG crop #{idx} is empty, skipped")
            continue

        ok, encoded = cv2.imencode(".jpg", crop)
        if not ok:
            continue

        crop_bytes = encoded.tobytes()
        bg_result = await identify_single_crop_with_brickognize(
            crop_bytes=crop_bytes,
            filename=f"crop_{idx}.jpg",
            content_type="image/jpeg",
        )
        
        print(f"DEBUG Brickognize result #{idx} =", bg_result)

        if "error" in bg_result:
            continue

        elements.append({
            "part_num": bg_result["elem_id"],
            "color_name": bg_result.get("color"),
            "confidence": round(float(bg_result["confidence"]), 4),
            "detection_confidence": det["detection_confidence"],
            "bounding_box": {
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
            },
        })
        print(f"DEBUG appended crop #{idx}, elements now =", len(elements))
    print("DEBUG final elements count =", len(elements))
    return {
        "count": len(elements),
        "elements": elements,
    }





async def identify_with_brickognize(
    file_bytes: bytes,
    filename: str = "image.jpg",
    content_type: str = "image/jpeg",
) -> dict:
    files = {
        "query_image": (filename, file_bytes, content_type)
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(BRICKOGNIZE_PARTS_URL, files=files)

    if response.status_code != 200:
        return {
            "error": f"Brickognize request failed ({response.status_code}): {response.text}"
        }

    data = response.json()
    items = data.get("items", [])

    if not items:
        return {"error": "No Brickognize matches returned."}

    top = items[0]
    bbox = data.get("bounding_box") or {}

    return {
        "count": 1,
        "elements": [
            {
                "elem_id": top["id"],
                "color": None,
                "confidence": float(top.get("score", 0.0)),
                "detection_confidence": float(bbox.get("score", 0.0)),
                "bounding_box": {
                    "x1": bbox.get("left"),
                    "y1": bbox.get("upper"),
                    "x2": bbox.get("right"),
                    "y2": bbox.get("lower"),
                },
                "name": top.get("name"),
                "type": top.get("type"),
                "category": top.get("category"),
                "img_url": top.get("img_url"),
            }
        ],
    }
