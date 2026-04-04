from pathlib import Path
from typing import Optional
import pandas as pd

BASE_DIR = Path(__file__).parent
COLORS_DF = pd.read_csv(BASE_DIR / "data" / "colors_filled.csv")


def _canon(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    s = str(value).strip().lower()
    if not s or s == "nan":
        return None

    replacements = {
        "_": " ",
        "-": " ",
        ".": "",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)

    s = " ".join(s.split())
    return s


def _compact(value: Optional[str]) -> Optional[str]:
    c = _canon(value)
    return c.replace(" ", "") if c else None


MODEL_NAME_TO_REBRICKABLE_NAME = {}
MODEL_NAME_TO_REBRICKABLE_ID = {}
REBRICKABLE_ID_TO_NAME = {}
REBRICKABLE_NAME_TO_ID = {}

for _, row in COLORS_DF.iterrows():
    color_id = row.get("id")
    rb_name = row.get("name")
    model_name = row.get("m_colorname")

    if pd.notna(color_id):
        color_id = int(color_id)
    else:
        color_id = None

    rb_name_c = _canon(rb_name)
    model_name_c = _canon(model_name)

    if color_id is not None:
        if rb_name_c:
            REBRICKABLE_ID_TO_NAME[color_id] = rb_name_c
            REBRICKABLE_NAME_TO_ID[rb_name_c] = color_id

        if model_name_c:
            MODEL_NAME_TO_REBRICKABLE_ID[model_name_c] = color_id

            if rb_name_c:
                MODEL_NAME_TO_REBRICKABLE_NAME[model_name_c] = rb_name_c


def normalize_color_name(value: Optional[str]) -> Optional[str]:
    return _canon(value)


def normalize_db_color(value: Optional[str]) -> Optional[str]:
    return _canon(value)


def normalize_model_color(value: Optional[str]) -> Optional[str]:
    return _canon(value)


def model_color_to_rebrickable_name(model_color: Optional[str]) -> Optional[str]:
    model_color_c = _canon(model_color)
    if not model_color_c:
        return None
    return MODEL_NAME_TO_REBRICKABLE_NAME.get(model_color_c)


def model_color_to_rebrickable_id(model_color: Optional[str]) -> Optional[int]:
    model_color_c = _canon(model_color)
    if not model_color_c:
        return None
    return MODEL_NAME_TO_REBRICKABLE_ID.get(model_color_c)


def rebrickable_id_to_name(color_id: Optional[int]) -> Optional[str]:
    if color_id is None:
        return None
    return REBRICKABLE_ID_TO_NAME.get(int(color_id))
