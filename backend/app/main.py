from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from app.database import engine, Base
from app.routers import telemetry, reports, dashboard, notifications

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Создаем таблицы (в продакшене лучше использовать Alembic миграции)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Опционально: создаем гипертаблицу TimescaleDB (если расширение установлено)
        # try:
        #     await conn.execute("SELECT create_hypertable('telemetry', 'timestamp', if_not_exists => TRUE);")
        # except Exception as e:
        #     print(f"TimescaleDB warning: {e}")
            
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(
    title="SkyShield IoT Server",
    description="Backend for RF Monitoring & Drone Detection System",
    version="2.0.0",
    lifespan=lifespan
)

app.include_router(telemetry.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(dashboard.router)
app.include_router(notifications.router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "skyshield-backend"}

@app.get("/", response_class=HTMLResponse)
async def root():
    html = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="0; url=/dashboard">
        <title>SkyShield — Redirecting...</title>
    </head>
    <body>
        <p>Redirecting to <a href="/dashboard">Dashboard</a>...</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
