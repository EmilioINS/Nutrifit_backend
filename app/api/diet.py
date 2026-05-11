"""
Diet Router — Clean Architecture.
Responsabilidad: exponer los endpoints HTTP de generación y consulta de dietas.
Delega toda la lógica de negocio a diet_service.
"""
from fastapi import APIRouter, Depends
from app.services.diet_service import generate_diet_plans
from app.services.db_service import supabase
from app.api.survey import get_current_user

router = APIRouter()


# ── POST /api/diet/generate ────────────────────────────────────────────────────

@router.post("/generate")
def generate(user_id: str = Depends(get_current_user)):
    """
    Recupera el perfil del usuario de la BD y genera 2 planes de dieta
    semanales personalizados. Los persiste en diet_plans para consulta posterior.
    """
    # Load user profile from survey responses
    survey_res = supabase.table("survey_responses").select("*").eq("user_id", user_id).execute()
    profile = survey_res.data[0] if survey_res.data else {}

    result = generate_diet_plans(profile)

    # Persist (upsert) — overwrite any previous plan for this user
    if result.get("plans"):
        try:
            supabase.table("diet_plans").upsert({
                "user_id":    user_id,
                "plans_json": result["plans"],
                "macros_json": result.get("macros", {}),
            }).execute()
        except Exception as exc:
            print(f"[Diet Save Error]: {exc}")

    return result


# ── GET /api/diet/ ─────────────────────────────────────────────────────────────

@router.get("/")
def get_saved_plan(user_id: str = Depends(get_current_user)):
    """Devuelve el último plan de dieta guardado para el usuario."""
    res = (
        supabase.table("diet_plans")
        .select("*")
        .eq("user_id", user_id)
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
    )
    if res.data:
        row = res.data[0]
        return {"plans": row["plans_json"], "macros": row.get("macros_json", {})}
    return {"plans": [], "macros": {}}
