from fastapi import APIRouter, Body, Depends, HTTPException
from app.api.deps import get_current_user
from app.services import plantboard_service

router = APIRouter(prefix="/api/tamagotchi", tags=["tamagotchi"])


@router.post("/state")
def get_tamagotchi_state(payload: dict = Body(default_factory=dict), current_user: dict = Depends(get_current_user)):
    plant_id = payload.get("plant_id")
    if not plant_id:
        raise HTTPException(status_code=400, detail="plant_id required")

    username = current_user.get("user_name")
    plants = plantboard_service.get_user_plants(username)
    plant = next((p for p in plants if p.get("id") == plant_id), None)
    if not plant:
        raise HTTPException(status_code=404, detail="plant not found")

    triggers = payload.get("triggers", [])
    result = plantboard_service.call_lora_dialogue(plant, triggers=triggers)

    if not result.get("ok"):
        return {
            "ok": True,
            "state": {
                "text": "잠깐 숨 고르는 중이야. 조금 있다 다시 눌러줘.",
                "emote": "CALM",
                "animation": "idle",
                "tags": ["fallback"],
            },
        }

    return {
        "ok": True,
        "state": {
            "text": result.get("text"),
            "emote": result.get("emote"),
            "animation": result.get("animation"),
            "tags": result.get("tags", []),
        },
    }
