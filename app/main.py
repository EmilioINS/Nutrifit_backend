from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, survey, scan, diet, streaks

app = FastAPI(title="NutriFit AI API")

origins = [
    "https://practica-open-api.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(survey.router, prefix="/api/survey", tags=["survey"])
app.include_router(scan.router, prefix="/api/scan-food", tags=["scan"])
app.include_router(diet.router, prefix="/api/diet", tags=["diet"])
app.include_router(streaks.router, prefix="/api/streaks", tags=["streaks"])

@app.get("/")
def read_root():
    return {"message": "Welcome to NutriFit AI API"}