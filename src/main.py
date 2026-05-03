from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.modules.auth.router import auth_router
from src.modules.enrollment.router import enrollment_router
from src.modules.faculty.router import faculty_router
from src.modules.document_processing.router import document_router
from src.modules.dashboards.router import dashboards_router
from src.modules.support.router import support_router
from src.modules.settings.router import settings_router
from src.modules.audit.router import audit_router          

app = FastAPI(
    title="University Campus System API (v2)",
    description="A highly scalable, modular monolith for Enrollment and Faculty Management.",
    version="2.0.0",
)


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Add your Vercel frontend URL here
origins = [
    "https://ccissportal-frontend.vercel.app",
    "http://localhost:3000", # Optional: Keep this if you test locally
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

app.include_router(auth_router)
app.include_router(enrollment_router)
app.include_router(faculty_router)
app.include_router(document_router)
app.include_router(dashboards_router)
app.include_router(support_router)
app.include_router(settings_router)
app.include_router(audit_router)                           

# --- TEMPORARY SETUP ROUTE ---
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
    return {
        "system_status": "Online",
        "allowed_origins": settings.allowed_origins_list,
    }

    