"""
Scan Router — Clean Architecture.
Responsabilidad: exponer los endpoints HTTP de escaneo e historial.
Delega toda la lógica a los servicios correspondientes.
"""
from fastapi import APIRouter, Depends, HTTPException
from app.models.schemas import ScanRequest, LogMealRequest
from app.services.ai_service import analyze_food_image
from app.services.db_service import supabase
from app.api.survey import get_current_user
from datetime import datetime

router = APIRouter()


# ── POST /api/scan-food/log-meal ───────────────────────────────────────────────

@router.post("/log-meal")
def log_meal(request: LogMealRequest, user_id: str = Depends(get_current_user)):
    """
    Registra una comida del plan alimenticio.
    Compara los macros escaneados con los objetivos.
    """
    result = analyze_food_image(request.image_base64)
    total = result.get("total", {})
    
    scanned_cal = total.get("calories", 0)
    target_cal = request.target_macros.calories
    
    # Check 20% margin
    if target_cal > 0:
        margin = target_cal * 0.20
        min_cal = target_cal - margin
        max_cal = target_cal + margin
    else:
        min_cal, max_cal = 0, 50 # Fallback
        
    is_similar = min_cal <= scanned_cal <= max_cal
    
    if not is_similar:
        raise HTTPException(
            status_code=400, 
            detail=f"Los valores nutricionales no coinciden. Escaneado: {scanned_cal} kcal, Esperado: {target_cal} kcal (±20%)"
        )
        
    # Registrar en historial normal
    items = result.get("items", [])
    food_names = ", ".join(i.get("food_name", "") for i in items)
    supabase.table("scan_history").insert({
        "user_id": user_id,
        "food_name": food_names,
        "calories": scanned_cal,
        "protein": total.get("protein", 0),
        "carbs": total.get("carbs", 0),
        "fat": total.get("fat", 0),
        "portion_size": f"{len(items)} alimento(s) - {request.meal_name}",
        "confidence": result.get("confidence", "—"),
        "items_json": items,
    }).execute()
    
    # Update daily_logs and streaks
    today = datetime.utcnow().date().isoformat()
    
    # Get or create daily log
    logs = supabase.table("daily_logs").select("*").eq("user_id", user_id).eq("date", today).execute()
    if len(logs.data) == 0:
        new_log = {
            "user_id": user_id,
            "date": today,
            "completed_meals": [request.meal_name],
            "total_expected_meals": request.total_expected_meals,
            "is_day_completed": False
        }
        log_res = supabase.table("daily_logs").insert(new_log).execute()
        current_log = log_res.data[0]
    else:
        current_log = logs.data[0]
        completed = current_log["completed_meals"]
        if request.meal_name not in completed:
            completed.append(request.meal_name)
            current_log = supabase.table("daily_logs").update({
                "completed_meals": completed,
                "total_expected_meals": request.total_expected_meals
            }).eq("id", current_log["id"]).execute().data[0]
            
    # Check if day is completed
    completed_meals = current_log["completed_meals"]
    if len(completed_meals) >= current_log["total_expected_meals"] and not current_log["is_day_completed"]:
        # Mark day as completed
        supabase.table("daily_logs").update({"is_day_completed": True}).eq("id", current_log["id"]).execute()
        
        # Update streak
        from app.api.streaks import get_or_create_streak
        streak = get_or_create_streak(user_id)
        new_streak_val = streak["current_streak"] + 1
        new_highest = max(new_streak_val, streak["highest_streak"])
        
        supabase.table("streaks").update({
            "current_streak": new_streak_val,
            "highest_streak": new_highest,
            "last_completed_date": today
        }).eq("user_id", user_id).execute()
        
        return {"status": "success", "message": "Meal logged and streak updated!", "day_completed": True}
        
    return {"status": "success", "message": "Meal logged successfully", "day_completed": False}

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
