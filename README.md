# SeedSync ⚡

Standalone lead ingestion and notification system.

## 📁 Repository Structure

- **/api**: FastAPI backend for client management and status.
- **/worker**: Python background worker for Google Sheets monitoring and WhatsApp notifications.
- **/admin**: React dashboard for monitoring.

## 🚀 Quick Start (Local)

### 1. Requirements
- Python 3.10+
- Node.js (for Admin)

### 2. Environment Setup
The worker requires a `.env` file and a `google-service-account.json` inside the `/worker` directory. 

### 3. Run Worker
```bash
cd worker
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

## 🔒 Security
Sensitive files (`.env`, `*.json`) are explicitly ignored via `.gitignore` to prevent leaks to GitHub.
