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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(enrollment_router)
app.include_router(faculty_router)
app.include_router(document_router)
app.include_router(dashboards_router)
app.include_router(support_router)
app.include_router(settings_router)
app.include_router(audit_router)                           


@app.get("/")
def check_system_health():
    return {
        "system_status": "Online",
        "message": "University Campus AI System v2.0 is running.",
    }