from pydantic import BaseModel, Field
from typing import Optional, List, Any

class UserCreate(BaseModel):
    email: str
    password: str
    first_name: str
    last_name_paternal: str
    last_name_maternal: str

class UserLogin(BaseModel):
    email: str
    password: str

class SurveyData(BaseModel):
    goal: Optional[str] = None
    modality: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    target_weight: Optional[float] = None
    trains_strength: Optional[bool] = None
    training_days: Optional[str] = None
    diet_type: Optional[str] = None
    meals_per_day: Optional[int] = None
    favorite_foods: Optional[List[str]] = None
    plan_format: Optional[str] = None

class ScanRequest(BaseModel):
    image_base64: str
