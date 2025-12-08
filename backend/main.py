# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import materials, modules, assignments, auth

app = FastAPI(title="Remote Learning Platform API (minimal)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for dev/testing. Lock this down in production.
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(materials.router)
app.include_router(modules.router, prefix="/modules", tags=["Modules"])
app.include_router(assignments.router, prefix="/assignments", tags=["Assignments"])

@app.get("/")
def root():
    return {"message": "API running"}