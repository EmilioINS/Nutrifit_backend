from fastapi import APIRouter, HTTPException, status, Depends
from app.models.schemas import UserCreate, UserLogin
from app.services.auth_service import get_password_hash, verify_password, create_access_token
from app.services.db_service import supabase

router = APIRouter()

@router.post("/register")
def register(user: UserCreate):
    # Verificar si existe
    existing = supabase.table("users_profile").select("*").eq("email", user.email).execute()
    if len(existing.data) > 0:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = get_password_hash(user.password)
    
    # Crear usuario
    result = supabase.table("users_profile").insert({
        "email": user.email,
        "password_hash": hashed_password,
        "first_name": user.first_name,
        "last_name_paternal": user.last_name_paternal,
        "last_name_maternal": user.last_name_maternal
    }).execute()
    
    if len(result.data) == 0:
        raise HTTPException(status_code=500, detail="Error creating user")
        
    new_user = result.data[0]
    token = create_access_token(data={"sub": new_user["id"]})
    
    return {"access_token": token, "token_type": "bearer", "user": {"id": new_user["id"], "email": new_user["email"]}}

@router.post("/login")
def login(user: UserLogin):
    result = supabase.table("users_profile").select("*").eq("email", user.email).execute()
    
    if len(result.data) == 0:
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    db_user = result.data[0]
    if not verify_password(user.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    token = create_access_token(data={"sub": db_user["id"]})
    return {"access_token": token, "token_type": "bearer", "user": {"id": db_user["id"], "email": db_user["email"]}}
