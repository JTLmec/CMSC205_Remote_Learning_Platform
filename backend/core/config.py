import os
from dotenv import load_dotenv
load_dotenv()  # loads backend/.env locally in dev

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mzjphxynfusdiyuoacba.supabase.co")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE")  # must be set in Render (secret)
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")        # optional for frontend/testing