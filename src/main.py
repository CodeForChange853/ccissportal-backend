from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.modules.auth.router import auth_router
from src.modules.enrollment.router import enrollment_router
from src.modules.faculty.router import faculty_router
from src.modules.document_processing.router import document_router
from src.modules.dashboards.router import dashboards_router
from src.modules.support.router import support_router
from src.modules.settings.router import settings_router
from src.modules.audit.router import audit_router
from src.modules.notifications.router import router as notifications_router

from src.core.database_setup import SessionLocal
from src.modules.settings.models import SystemSettings

app = FastAPI(
    title="University Campus System API (v2)",
    description="A highly scalable, modular monolith for Enrollment and Faculty Management.",
    version="2.0.0",
)

# --- ROUTES ---
app.include_router(auth_router)
app.include_router(enrollment_router)
app.include_router(faculty_router)
app.include_router(document_router)
app.include_router(dashboards_router)
app.include_router(support_router)
app.include_router(settings_router)
app.include_router(audit_router)
app.include_router(notifications_router)

# --- MAINTENANCE MIDDLEWARE ---
@app.middleware("http")
async def maintenance_mode_middleware(request: Request, call_next):
    # 1. Skip preflight OPTIONS requests immediately
    if request.method == "OPTIONS":
        return await call_next(request)

    # 2. Exempt paths that must remain open for admins to fix the system
    exempt_paths = [
        "/authentication/login",
        "/settings",
        "/system-init-secure-99",
        "/", # Health check
    ]
    
    if any(request.url.path == p or request.url.path.startswith(p + "/") for p in exempt_paths):
        return await call_next(request)

    # 3. Check maintenance status from DB
    db = SessionLocal()
    try:
        sys_settings = db.query(SystemSettings).filter(SystemSettings.settings_id == 1).first()
        
        if sys_settings and sys_settings.is_maintenance_mode:
            # Check for Admin Authorization to bypass maintenance
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                try:
                    from jose import jwt
                    from src.core.config import settings
                    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                    if payload.get("role") == "ADMIN":
                        return await call_next(request)
                except Exception:
                    pass

            return JSONResponse(
                status_code=503,
                content={
                    "maintenance": True,
                    "reason": sys_settings.maintenance_reason or "Neural Infrastructure Recalibration",
                    "message": sys_settings.maintenance_message or "The system is currently undergoing maintenance. Please try again later."
                }
            )
    except Exception:
        pass
    finally:
        db.close()

    return await call_next(request)

# --- UTILITY ROUTES ---
@app.get("/system-init-secure-99")
def emergency_setup():
    from src.core.create_tables import initialize_database
    from src.core.seed_database import seed_database
    try:
        initialize_database()
        seed_database()
        return {"status": "SUCCESS", "message": "Database tables created and Admin seeded!"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

@app.get("/")
def check_system_health():
    db = SessionLocal()
    m_status = False
    m_reason = ""
    try:
        s = db.query(SystemSettings).filter(SystemSettings.settings_id == 1).first()
        if s:
            m_status = s.is_maintenance_mode
            m_reason = s.maintenance_reason
    except Exception:
        pass
    finally:
        db.close()
        
    return {
        "system_status": "Maintenance" if m_status else "Online",
        "maintenance_mode": m_status,
        "maintenance_reason": m_reason,
        "allowed_origins": settings.allowed_origins_list,
    }

# --- CORS CONFIGURATION (Outermost Layer) ---
# We register this LAST so it wraps around ALL other middlewares, including maintenance mode.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ccissportal-frontend.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
    ] + settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)