# backend/main.py
import os
from typing import List
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
# load .env explicitly from the backend directory (robust regardless of cwd)
from dotenv import load_dotenv
import os
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    # fallback: try default loader (keeps previous behavior)
    try:
        load_dotenv()
    except Exception:
        pass

# Import routers from the routers package (adjust path if your project root differs)
from routers import materials, modules, assignments

# Try to import get_current_user for /profiles/me (optional)
try:
    from auth import get_current_user  # type: ignore
except Exception:
    try:
        from auth import get_current_user  # type: ignore
    except Exception:
        get_current_user = None

app = FastAPI(title="Remote Learning Platform API (minimal)")

# FRONTEND_ORIGINS can be comma-separated; default to "*" for dev
origins_env = os.environ.get("FRONTEND_ORIGINS", "*")
_origins: List[str] = ["*"] if origins_env.strip() == "*" else [o.strip() for o in origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin"],
)

# Include routers WITHOUT adding a prefix (routers already define their own prefixes)
app.include_router(materials.router)
app.include_router(modules.router)
app.include_router(assignments.router)


@app.on_event("startup")
async def _startup():
    # minimal env hint
    required = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE", "SUPABASE_ANON_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"Warning: missing env vars: {missing}")


@app.get("/")
def root():
    return {"message": "API running"}


if get_current_user is not None:
    @app.get("/profiles/me", tags=["Profiles"])
    async def profiles_me(current_user: dict = Depends(get_current_user)):
        return {"user": current_user}