from fastapi import APIRouter, Depends, HTTPException
from app.api.survey import get_current_user
from app.services.db_service import supabase
from datetime import datetime, date, timedelta

router = APIRouter()

def get_or_create_streak(user_id: str):
    response = supabase.table("streaks").select("*").eq("user_id", user_id).execute()
    if len(response.data) == 0:
        new_streak = {
            "user_id": user_id,
            "current_streak": 0,
            "highest_streak": 0,
            "last_completed_date": None,
            "restore_chances": 3
        }
        res = supabase.table("streaks").insert(new_streak).execute()
        return res.data[0]
    return response.data[0]

@router.get("/")
def get_streak_info(user_id: str = Depends(get_current_user)):
    streak = get_or_create_streak(user_id)
    today = datetime.utcnow().date()
    
    # Evaluar estado de la racha
    status = "active"
    if streak["last_completed_date"]:
        last_date = datetime.strptime(streak["last_completed_date"], "%Y-%m-%d").date()
        days_diff = (today - last_date).days
        
        if days_diff > 1:
            if streak["restore_chances"] > 0:
                status = "at_risk"
            else:
                # Perdió la racha, resetear automáticamente
                streak["current_streak"] = 0
                streak["restore_chances"] = 3
                streak["last_completed_date"] = None
                supabase.table("streaks").update({
                    "current_streak": 0,
                    "restore_chances": 3,
                    "last_completed_date": None
                }).eq("user_id", user_id).execute()
                status = "lost_and_reset"

    # Obtener el log de hoy
    logs = supabase.table("daily_logs").select("*").eq("user_id", user_id).eq("date", today.isoformat()).execute()
    today_log = logs.data[0] if len(logs.data) > 0 else None

    return {
        "streak": streak,
        "status": status,
        "today_log": today_log
    }

@router.post("/restore")
def restore_streak(user_id: str = Depends(get_current_user)):
    streak = get_or_create_streak(user_id)
    
    if streak["restore_chances"] <= 0:
        raise HTTPException(status_code=400, detail="No restore chances left")
        
    if not streak["last_completed_date"]:
        raise HTTPException(status_code=400, detail="No streak to restore")
        
    today = datetime.utcnow().date()
    last_date = datetime.strptime(streak["last_completed_date"], "%Y-%m-%d").date()
    
    if (today - last_date).days <= 1:
        raise HTTPException(status_code=400, detail="Streak is not at risk")
        
    # Restaurar la racha: asumimos que ayer fue completado para mantenerla viva
    yesterday = (today - timedelta(days=1)).isoformat()
    new_chances = streak["restore_chances"] - 1
    
    res = supabase.table("streaks").update({
        "last_completed_date": yesterday,
        "restore_chances": new_chances
    }).eq("user_id", user_id).execute()
    
    return {"message": "Streak restored", "streak": res.data[0]}
