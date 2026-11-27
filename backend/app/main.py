import os, json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import httpx
from .db import Base, engine, get_db
from .models import User, ApiKey
from .schemas import Credentials, KeyCreate
from .security import (
    hash_password, verify_password, create_access_token,
    decode_access_token, create_api_key, hash_api_key
)

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Neural Hub API", version="0.1.0")

origins = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=False, allow_methods=["*"], allow_headers=["*"]
)

def get_models():
    path = Path(__file__).resolve().parents[1] / "models.txt"
    items = []
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            provider, model = line.split(":", 1)
            if provider.strip() and model.strip():
                items.append({"id": line, "object": "model", "created": 0, "owned_by": provider.strip()})
    return items

def get_provider_config():
    try:
        return json.loads(os.getenv("PROVIDERS_JSON", "{}"))
    except json.JSONDecodeError:
        return {}

def current_user(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization[7:]
    try:
        user_id = decode_access_token(token)
    except Exception:
        raise HTTPException(401, "Invalid or expired session")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(401, "User not found")
    return user

def current_api_key(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer sk-live-"):
        raise HTTPException(401, "Use Authorization: Bearer sk-live-...")
    digest = hash_api_key(authorization[7:])
    key = db.query(ApiKey).filter(ApiKey.key_hash == digest, ApiKey.active.is_(True)).first()
    if not key:
        raise HTTPException(401, "Invalid or revoked API key")
    return key

@app.get("/")
def root():
    return {"name": "Neural Hub API", "docs": "/docs", "status": "ok"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/auth/register")
def register(data: Credentials, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "email": user.email}

@app.post("/auth/login")
def login(data: Credentials, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "email": user.email}

@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "created_at": user.created_at.isoformat()}

@app.get("/keys")
def list_keys(user: User = Depends(current_user), db: Session = Depends(get_db)):
    keys = db.query(ApiKey).filter(ApiKey.user_id == user.id).order_by(ApiKey.id.desc()).all()
    return [{"id": k.id, "name": k.name, "prefix": k.prefix, "active": k.active, "created_at": k.created_at.isoformat()} for k in keys]

@app.post("/keys")
def new_key(data: KeyCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    raw, digest, prefix = create_api_key()
    key = ApiKey(user_id=user.id, name=data.name, prefix=prefix, key_hash=digest)
    db.add(key); db.commit(); db.refresh(key)
    return {"id": key.id, "name": key.name, "api_key": raw, "warning": "Copy this key now. It cannot be shown again."}

@app.delete("/keys/{key_id}")
def revoke_key(key_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == user.id).first()
    if not key:
        raise HTTPException(404, "Key not found")
    key.active = False
    db.commit()
    return {"ok": True}

@app.get("/v1/models")
def models(key: ApiKey = Depends(current_api_key)):
    configured = set(get_provider_config().keys())
    return {"object": "list", "data": [m for m in get_models() if m["owned_by"] in configured]}

@app.post("/v1/chat/completions")
async def chat_completions(payload: dict, key: ApiKey = Depends(current_api_key)):
    model_id = payload.get("model")
    if not isinstance(model_id, str) or ":" not in model_id:
        raise HTTPException(400, "Model must use provider:model format")
    provider, upstream_model = model_id.split(":", 1)
    cfg = get_provider_config().get(provider)
    if not cfg:
        raise HTTPException(400, f"Provider '{provider}' is not configured")
    env_name = cfg.get("api_key_env")
    provider_key = os.getenv(env_name, "") if env_name else ""
    if not provider_key:
        raise HTTPException(503, f"Missing server credential for provider '{provider}'")
    if payload.get("stream"):
        raise HTTPException(400, "Streaming is not enabled in this starter version")
    base_url = cfg.get("base_url", "").rstrip("/")
    if not base_url:
        raise HTTPException(500, f"Provider '{provider}' has no base_url")
    body = dict(payload)
    body["model"] = upstream_model
    timeout = httpx.Timeout(120.0, connect=20.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(
                base_url + "/chat/completions",
                headers={"Authorization": f"Bearer {provider_key}", "Content-Type": "application/json"},
                json=body
            )
        except httpx.RequestError as exc:
            raise HTTPException(502, f"Upstream connection failed: {str(exc)}")
    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:1000]
        raise HTTPException(response.status_code, detail)
    return response.json()
