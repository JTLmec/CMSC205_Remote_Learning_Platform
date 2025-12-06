from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE")
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///learning.db")

settings = Settings()