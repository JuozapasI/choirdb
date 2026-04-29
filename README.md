# choirdb  
PostgreSQL-backed web application for managing and searching a choir sheet music database.

## Overview
This project provides a simple web interface for organizing choir materials, including:
- Sheet music (PDFs)
- Metadata (composer, title, voicing, etc.)
- Optional lyrics or annotations

It has both admin and user roles.

It is built with FastAPI, PostgreSQL, and SQLAlchemy.

---

## ⚙️ Setup

### 1. Clone the repository
```bash
git clone https://github.com/JuozapasI/choirdb.git
cd choirdb
```

### 2. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Setup
Set up secret key in .env file and you database location in database.py

### 4. Run
Locally
```bash
uvicorn app.main:app --reload
```
or more production-like
```bash
gunicorn -k uvicorn.workers.UvicornWorker app.main:app --workers 3
```

### 5. Access
Once run, you can access at http://localhost:8000.
