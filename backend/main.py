# backend/backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import materials

app = FastAPI(title="Remote Learning Platform API (minimal)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for dev/testing. Lock this down in production.
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(materials.router)

@app.get("/")
def root():
    return {"message": "API running"}