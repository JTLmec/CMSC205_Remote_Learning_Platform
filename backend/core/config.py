# backend/backend/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()  # load .env values locally; Render will use environment vars

class Settings:
    # REQUIRED for any Supabase project
    SUPABASE_URL: str = "https://mzjphxynfusdiyuoacba.supabase.co"

    # DO NOT hardcode keys — read from environment
    SUPABASE_SERVICE_ROLE: str = os.getenv("SUPABASE_SERVICE_ROLE")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY")

    # Database (Supabase Postgres)
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # Auth settings (optional)
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret")

settings = Settings()