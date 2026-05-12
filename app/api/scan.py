"""
Scan Router — Clean Architecture.
Responsabilidad: exponer los endpoints HTTP de escaneo e historial.
Delega toda la lógica a los servicios correspondientes.
"""
from fastapi import APIRouter, Depends
from app.models.schemas import ScanRequest
from app.services.ai_service import analyze_food_image
from app.services.db_service import supabase
from app.api.survey import get_current_user

router = APIRouter()


# ── POST /api/scan-food/ ───────────────────────────────────────────────────────

@router.post("/")
def scan_food(request: ScanRequest, user_id: str = Depends(get_current_user)):
    """
    Recibe una imagen en Base64, la analiza con la IA y persiste el resultado
    en el historial del usuario.  Devuelve el desglose completo por alimento
    más el total consolidado.
    """
    result = analyze_food_image(request.image_base64)

    # Persist to history (fire-and-forget — never block the response)
    try:
        total = result.get("total", {})
        items = result.get("items", [])
        food_names = ", ".join(i.get("food_name", "") for i in items)

        supabase.table("scan_history").insert({
            "user_id":     user_id,
            "food_name":   food_names,
            "calories":    total.get("calories", 0),
            "protein":     total.get("protein", 0),
            "carbs":       total.get("carbs", 0),
            "fat":         total.get("fat", 0),
            "portion_size": f"{len(items)} alimento(s)",
            "confidence":  result.get("confidence", "—"),
            "items_json":  items,       # rich detail for future use
        }).execute()
    except Exception as exc:
        print(f"[History Save Error]: {exc}")

    return result


# ── GET /api/scan-food/history ─────────────────────────────────────────────────

@router.get("/history")
def get_scan_history(user_id: str = Depends(get_current_user)):
    """Devuelve el historial de escaneos del usuario, más reciente primero."""
    result = (
        supabase.table("scan_history")
        .select("*")
        .eq("user_id", user_id)
        .order("scanned_at", desc=True)
        .limit(50)
        .execute()
    )
    return result.data

# ── DELETE /api/scan-food/history ──────────────────────────────────────────────

@router.delete("/history")
def clear_scan_history(user_id: str = Depends(get_current_user)):
    """Elimina todo el historial de escaneos del usuario."""
    supabase.table("scan_history").delete().eq("user_id", user_id).execute()
    return {"message": "Historial limpiado correctamente"}
