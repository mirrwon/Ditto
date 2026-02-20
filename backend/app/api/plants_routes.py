import json
import os
from typing import Any, Dict, List

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/plants")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "plantsData")
DATA_FILE = os.path.join(DATA_DIR, "plants_sample.json")


def _load_items() -> List[Dict[str, Any]]:
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    except Exception:
        return []
    return []


@router.get("")
def list_plants() -> JSONResponse:
    return JSONResponse({"items": _load_items()})
