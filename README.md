# Neural Hub

Static frontend for GitHub Pages + FastAPI backend for Render.

## Architecture
- `frontend/` — static HTML/CSS/JS; deploy this folder to GitHub Pages.
- `backend/` — FastAPI API gateway; deploy this folder as a Render Web Service.
- The backend stores users and hashed gateway API keys in PostgreSQL (recommended) or SQLite (local testing).
- Provider credentials are configured only in Render environment variables. Never put upstream provider keys in frontend files or commit them.

## 1. Create a GitHub repository
Upload the contents of this project to the root of your `neural-hub` repository.

## 2. Deploy backend on Render
Create a **Web Service** from the GitHub repository:
- Root Directory: `backend`
- Runtime: Python 3
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Set environment variables:
- `JWT_SECRET` — a long random secret.
- `DATABASE_URL` — PostgreSQL connection string. Use Render Postgres; SQLite is only for local testing.
- `FRONTEND_ORIGINS` — your GitHub Pages URL, e.g. `https://nametagovskiy-gif.github.io`.
- `PROVIDERS_JSON` — provider adapter configuration (example below).

Example `PROVIDERS_JSON`:
```json
{
  "openai": {
    "base_url": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY"
  },
  "openrouter": {
    "base_url": "https://openrouter.ai/api/v1",
    "api_key_env": "OPENROUTER_API_KEY"
  }
}
```
Then add `OPENAI_API_KEY` and/or `OPENROUTER_API_KEY` as separate Render environment variables. Add only providers for which you have legitimate API credentials and a compatible OpenAI-style API.

## 3. Deploy frontend with GitHub Pages
In GitHub: Settings → Pages → Build and deployment → Deploy from a branch.
Select `main` and folder `/frontend`. Save.
Set the backend URL in `frontend/config.js` to your Render service URL, e.g. `https://YOUR-SERVICE.onrender.com`.

## 4. Model catalog
`backend/models.txt` accepts one model per line in `provider:model` format.
Example:
```
openai:gpt-4.1-mini
openrouter:openai/gpt-4.1-mini
```
Only models whose provider is configured in `PROVIDERS_JSON` can actually be called. The catalog is not proof that a model exists or that access is free. The suffix after `provider:` is sent as the upstream model ID.

## API
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `POST /keys`
- `GET /keys`
- `DELETE /keys/{key_id}`
- `GET /v1/models` (requires `Authorization: Bearer sk-live-...`)
- `POST /v1/chat/completions` (requires gateway API key)

## Important
This is a starter implementation, not a production audit. Before public launch, add email verification, password reset, billing/quotas, abuse monitoring, stricter rate limits, and a managed database with backups. Do not promise unlimited or free upstream inference: provider usage is billed and governed by each provider.
