import cv2
import numpy as np
import joblib
import tensorflow as tf
from ultralytics import YOLO
from pathlib import Path
import pandas as pd

# ==========================================
# MODELLEK BETÖLTÉSE (egyszer, indításkor)
# ==========================================
BASE_DIR = Path(__file__).parent  # app/

yolo_model = YOLO(str(BASE_DIR / "models" / "best.pt"))
shape_model = tf.keras.models.load_model(str(BASE_DIR / "models" / "lego_shape_model_v6_4_224.keras"))
knn_model   = joblib.load(str(BASE_DIR / "models" / "lego_color_v6_weighted.pkl"))
knn_scaler  = joblib.load(str(BASE_DIR / "models" / "lego_color_v6_scaler.pkl"))

# Color-shape constraint mapping
PARTS_DF = pd.read_excel(
    r"C:\Users\bj\Documents\OE\szakdoga\colors\rebrickable_parts_final.xlsx"
)
# B200_Name normalizálása: " Bright Red" → "bright_red"
PARTS_DF["B200_Name_normalized"] = (
    PARTS_DF["B200_Name"].str.strip().str.lower().str.replace(" ", "_")
)
# {elem_id: {"bright_red", "med._stone_grey", ...}}
SET_COLOR_MAP = (
    PARTS_DF.groupby("Part")["B200_Name_normalized"]
    .apply(set)
    .to_dict()
)

# Osztálynevek (tanítóadat mappa sorrendje alapján)
import os
DATASET_DIR = r"C:\Users\bj\Documents\OE\szakdoga\10696_training_data_balanced_FINAL"
CLASS_NAMES = sorted(os.listdir(DATASET_DIR))

# ==========================================
# SZÍNFELISMERÉS (k-NN, ROI alapú)
# ==========================================
def get_color_features(img_bgr: np.ndarray) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    margin_y = int(h * 0.35)
    margin_x = int(w * 0.35)
    roi = img_bgr[margin_y:h - margin_y, margin_x:w - margin_x]

    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB).astype(np.float32)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV).astype(np.float32)

    features = [
        np.median(lab[:, :, 0]), np.mean(lab[:, :, 0]),
        np.median(lab[:, :, 1]), np.mean(lab[:, :, 1]),
        np.median(lab[:, :, 2]), np.mean(lab[:, :, 2]),
        np.median(hsv[:, :, 0]), np.mean(hsv[:, :, 0]),
        np.median(hsv[:, :, 1]), np.mean(hsv[:, :, 1]),
        np.median(hsv[:, :, 2]), np.mean(hsv[:, :, 2]),
    ]
    return np.array(features).reshape(1, -1)

def predict_color(img_bgr: np.ndarray) -> str:
    features = get_color_features(img_bgr)
    features_scaled = knn_scaler.transform(features)
    return knn_model.predict(features_scaled)[0]

# ==========================================
# ALAKFELISMERÉS (MobileNetV2)
# ==========================================
def predict_shape(img_bgr: np.ndarray, top_k: int = 5):
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_resized = cv2.resize(img_rgb, (224, 224))
    img_array = np.expand_dims(img_resized, axis=0).astype(np.float32)

    preds = shape_model.predict(img_array, verbose=0)[0]
    top_indices = np.argsort(preds)[::-1][:top_k]

    return [
        {
            "elem_id": CLASS_NAMES[i],
            "confidence": round(float(preds[i]) * 100, 2)
        }
        for i in top_indices
    ]
#filter
def filter_by_set_colors(top5: list, detected_color: str) -> list:
    color_normalized = detected_color.strip().lower().replace(" ", "_")
    
    filtered = [
        item for item in top5
        if item["elem_id"] not in SET_COLOR_MAP or
           color_normalized in SET_COLOR_MAP[item["elem_id"]]
    ]
    # Ha minden kiszűrődött → visszaadjuk az eredetit
    return filtered if filtered else top5
# ==========================================
# TELJES PIPELINE
# ==========================================
async def identify_element(file) -> dict:
    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img_bgr is None:
        return {"error": "Failed to decode image."}

    # YOLO detection
    results = yolo_model(img_bgr, verbose=False)
    boxes = results[0].boxes

    if boxes is None or len(boxes) == 0:
        return {"error": "No LEGO element detected in image."}

    # ← MINDEN elemet feldolgozunk
    identified_elements = []

    for box in boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        detection_confidence = float(box.conf[0])

        crop = img_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        top5  = predict_shape(crop)
        color = predict_color(crop)
        top5_filtered = filter_by_set_colors(top5, color)

        identified_elements.append({
            "elem_id": top5_filtered[0]["elem_id"],
            "color": color,
            "confidence": top5_filtered[0]["confidence"],
            "detection_confidence": round(detection_confidence * 100, 2),
            "top5_raw": top5,
            "top5_filtered": top5_filtered,
            "bounding_box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        })

    return {
        "count": len(identified_elements),
        "elements": identified_elements
    }
