from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.schemas import SurveyData
from app.services.auth_service import decode_access_token
from app.services.db_service import supabase

router = APIRouter()
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]

@router.post("/")
def save_survey(survey: SurveyData, user_id: str = Depends(get_current_user)):
    data = survey.model_dump(exclude_none=True)
    data["user_id"] = user_id
    
    # Usar upsert para crear o actualizar
    result = supabase.table("survey_responses").upsert(data).execute()
    
    if len(result.data) == 0:
        raise HTTPException(status_code=500, detail="Error saving survey")
        
    return {"message": "Survey saved successfully", "data": result.data[0]}

@router.get("/")
def get_survey(user_id: str = Depends(get_current_user)):
    result = supabase.table("survey_responses").select("*").eq("user_id", user_id).execute()
    if len(result.data) == 0:
        return {}
    return result.data[0]
