# DB Management Tool

An internal tool designed for securely managing, exporting, obscuring, and importing database backups seamlessly.

## Features
- **Database Export & Import**: Easily transport database dumps.
- **Data Obscuring**: Securely scrub sensitive information from database dumps to ensure compliance.
- **Environment Management**: Provision test and temporary databases on the fly.
- **Access Control**: Built-in authentication and role management (via Django/FastAPI).
- **Job Tracking**: Monitor background jobs for lengthy database operations.

## Tech Stack
- **Backend**: Python (FastAPI / Django)
- **Database**: MySQL / SQLite
- **Deployment**: Docker-ready (includes `Dockerfile` and `docker-compose.yml`)

## Getting Started Locally

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**
   Copy the example environment file and update it with your credentials:
   ```bash
   cp .env.example .env
   ```

3. **Run the Server**
   ```bash
   uvicorn app:app --reload
   ```

## Docker Deployment
```bash
docker-compose up --build -d
```
