# MLB Prop Predictor Pro

This version is cleaned up to be **one-click deploy ready for Render Blueprints**.

## What is included

- FastAPI web app with sportsbook-style UI
- async PostgreSQL via SQLAlchemy
- Render Key Value for caching and Celery queues
- Celery worker for background tasks
- cron services for schedule sync, context refresh, and model retraining
- idempotent render bootstrap that creates tables and can seed demo data automatically
- `.python-version`, `.gitignore`, and a ready-to-use `render.yaml`

## One-click deploy flow

1. Push this folder to a GitHub repo.
2. In Render, choose **New + → Blueprint** and connect that repo.
3. Render will read `render.yaml` and provision:
   - web service
   - worker
   - 3 cron jobs
   - Postgres
   - Key Value
4. Add your `ODDS_API_KEY` in Render if you want live sportsbook ingestion.
5. Open the web URL after the first deploy completes.

## Deploy button

After you push to GitHub, replace `YOUR_GITHUB_REPO_URL` below with your repo URL and add this to your repo README if you want a true one-click button:

```md
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=YOUR_GITHUB_REPO_URL)
```

## Render bootstrap behavior

During deploy, `scripts/render_setup.py` will:

- create tables
- optionally seed demo data if the database is empty
- refresh park factors, weather, and lineups
- train baseline models if none exist yet

The defaults in `render.yaml` are set so the first deploy shows a working product immediately.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

docker compose up -d postgres redis
python scripts/render_setup.py
uvicorn app.main:app --reload
```

Open:
- UI: `http://127.0.0.1:8000`
- Docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/healthz`

## Useful env vars

- `SEED_DEMO_DATA=true`
- `TRAIN_MODELS_ON_BOOT=true`
- `SYNC_SCHEDULE_ON_BOOT=false`
- `INGEST_ODDS_ON_BOOT=false`
- `ODDS_API_KEY=`

## Render notes

- Render Blueprints use the repo-root `render.yaml` by default.
- Render recommends setting `autoDeploy: false` for services meant to be launched from a Deploy to Render button.
- Render Key Value instances use `type: keyvalue` in Blueprints, with `redis` supported as a deprecated alias.
- Render lets you pin Python with `PYTHON_VERSION` or a `.python-version` file.
