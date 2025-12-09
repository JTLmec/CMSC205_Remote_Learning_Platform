Remote Learning Platform (CMSC205 Project)

Short description: A simple offline-first remote learning platform where teachers upload materials and students can download them. The app demonstrates TCP/UDP concepts in the course and integrates a cloud backend (Supabase) for auth and storage.

Overview

A modular offline-first remote learning platform built with:

Backend: FastAPI (Python)

Frontend: Streamlit (Python)

Storage & Auth: Supabase (Postgres + Storage + Auth)

Hosting: Render (recommended) — two services (backend + frontend)

Tech stack
	•	Python (3.11+ / 3.12 tested)
	•	FastAPI (backend)
	•	Streamlit (frontend)
	•	Supabase (Auth, Storage, Postgres)
	•	Render (hosting)

Features
	•	Signup/login (Supabase Auth)
	•	Teacher / Student roles (profiles table)
	•	Upload materials (teacher-only) stored in Supabase Storage bucket
	•	Download materials with signed URLs
	•	Offline-first frontend cache

Repo layout (summary)

See FOLDER_STRUCTURE.md in this repo (or the section below).

Quick start (local)
	1.	Clone the repo

git clone <repo-url>
cd remote-learning-platform

	2.	Create virtual environments for backend and frontend (optional but recommended)

# backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# backend run: leave running in terminal
uvicorn main:app --reload --port 8000

# in another terminal: frontend
cd frontend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run main.py --server.port 8501

	3.	Configure .env files (see CONFIGURATION section below)

Configuration

Create .env in backend and frontend directories, or set the environment variables in your terminal.

Main variables:

# backend/.env
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_SERVICE_ROLE=<service-role-key>
SUPABASE_ANON_KEY=<anon-key>
DATABASE_URL=<postgres-connection-url>   # optional if using DB
JWT_SECRET=some-secret

# frontend/.env
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
API_BASE=http://127.0.0.1:8000

Security: Never commit .env or keys — put them in .gitignore.

Deploy to Render (short)
	1.	Push code to GitHub
	2.	Create two Render services: backend (web service) & frontend (web service)
	3.	Set Build & Start commands for each (see render.yaml example in this repo)
	4.	Add environment variables to Render dashboard (SUPABASE_* and DATABASE_URL)



