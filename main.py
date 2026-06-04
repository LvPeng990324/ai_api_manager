import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from models import Base
from routers import admin, proxy
from utils.db import engine

app = FastAPI(title="AI Token Proxy", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(proxy.router)
app.include_router(admin.router)

# 静态文件
static_dir = os.path.join(os.path.dirname(__file__), "static", "admin")
os.makedirs(static_dir, exist_ok=True)
app.mount("/admin/static", StaticFiles(directory=static_dir), name="admin_static")


@app.get("/admin/")
async def admin_page():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
