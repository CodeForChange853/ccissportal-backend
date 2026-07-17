from contextlib import asynccontextmanager
import time as _maint_time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
# pyrefly: ignore [missing-import]
from slowapi import _rate_limit_exceeded_handler
# pyrefly: ignore [missing-import]
from slowapi.errors import RateLimitExceeded

# ── Maintenance-mode TTL cache ────────────────────────────────────────────────
# Avoids a DB round-trip on every incoming request. Stale by at most 15 seconds,
# which is acceptable given how rarely maintenance mode is toggled.
_MAINT_CACHE: dict = {"mode": False, "reason": "", "message": "", "ts": 0.0}
_MAINT_CACHE_TTL = 15.0  # seconds


def _get_maintenance_state(db_factory) -> dict:
    """Return cached maintenance state; refresh from DB when TTL has expired."""
    now = _maint_time.monotonic()
    if now - _MAINT_CACHE["ts"] < _MAINT_CACHE_TTL:
        return _MAINT_CACHE

    from src.modules.settings.models import SystemSettings as _SS
    db = db_factory()
    try:
        s = db.query(_SS).filter(_SS.settings_id == 1).first()
        _MAINT_CACHE.update({
            "mode":    bool(s and s.is_maintenance_mode),
            "reason":  (s.maintenance_reason  if s else "") or "",
            "message": (s.maintenance_message if s else "") or "",
            "ts":      now,
        })
    except Exception:
        _MAINT_CACHE["ts"] = now  # prevent a storm of retries on DB outage
    finally:
        db.close()

    return _MAINT_CACHE

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
from src.modules.analytics.router import analytics_router
from src.modules.secretariat.ojt.router import ojt_router
from src.modules.secretariat.equipment.router import equipment_router
from src.modules.secretariat.completion.router import completion_router
from src.modules.secretariat.mapping.router import mapping_router
from src.modules.secretariat.petitions.router import petition_router
from src.modules.secretariat.documents.router import documents_router
from src.modules.secretariat.facilities.router import facilities_router
from src.modules.secretariat.cor.router import cor_router
from src.modules.latin_honors.router import honors_router

from src.core.database_setup import SessionLocal
from src.core.limiter import limiter
from src.modules.settings.models import SystemSettings
from src.modules.support.models import SystemAnnouncement


# ── SE-01.05: Scheduled forecast retraining ───────────────────────────────────

def _run_scheduled_forecast() -> None:
    db = SessionLocal()
    try:
        from src.modules.analytics import service as analytics_service
        result = analytics_service.run_forecast(db)
        print(
            f"✅ Scheduled enrollment forecast complete — "
            f"{result.get('forecasts_generated', 0)} subjects, "
            f"{result.get('alerts_generated', 0)} alert(s)."
        )
    except Exception as exc:
        print(f"❌ Scheduled forecast failed: {exc}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Safe analytics table creation (no drops, idempotent) ─────────────────
    try:
        from src.modules.analytics.models import EnrollmentForecast, ForecastAlert
        from src.core.database_setup import Base, database_engine
        Base.metadata.create_all(
            bind=database_engine,
            tables=[EnrollmentForecast.__table__, ForecastAlert.__table__],
            checkfirst=True,
        )
        print("✅ Analytics tables verified.")
    except Exception as exc:
        print(f"⚠️  Could not auto-create analytics tables: {exc}")

    # ── F-13.1 / F-13.5: Secretariat table creation ──────────────────────────
    try:
        from src.modules.secretariat.ojt.models import OJTSubmission
        from src.modules.secretariat.equipment.models import EquipmentInventory, EquipmentCheckout
        from src.modules.secretariat.completion.models import CompletionRequest
        from src.modules.secretariat.mapping.models import SubjectMappingDraft
        from src.modules.secretariat.petitions.models import SubjectPetition
        from src.modules.secretariat.documents.models import DocumentRequest
        from src.modules.secretariat.facilities.models import StudentOrganization, Facility, FacilityBooking
        from src.core.database_setup import Base, database_engine
        Base.metadata.create_all(
            bind=database_engine,
            tables=[
                OJTSubmission.__table__,
                EquipmentInventory.__table__,
                EquipmentCheckout.__table__,
                CompletionRequest.__table__,
                SubjectMappingDraft.__table__,
                SubjectPetition.__table__,
                DocumentRequest.__table__,
                StudentOrganization.__table__,
                Facility.__table__,
                FacilityBooking.__table__,
            ],
            checkfirst=True,
        )
        print("✅ Secretariat tables verified.")
    except Exception as exc:
        print(f"⚠️  Could not auto-create secretariat tables: {exc}")

    # ── Latin Honors table creation ──────────────────────────────────────────
    try:
        from src.modules.latin_honors.models import DeanNote, HonorsRating
        from src.core.database_setup import Base, database_engine
        Base.metadata.create_all(
            bind=database_engine,
            tables=[DeanNote.__table__, HonorsRating.__table__],
            checkfirst=True,
        )
        print("✅ Latin Honors tables verified.")
    except Exception as exc:
        print(f"⚠️  Could not auto-create latin honors tables: {exc}")

    # ── P4-B: Notifications table creation ───────────────────────────────────
    try:
        from src.modules.notifications.models import Notification
        from src.core.database_setup import Base, database_engine
        Base.metadata.create_all(
            bind=database_engine,
            tables=[Notification.__table__],
            checkfirst=True,
        )
        print("✅ Notifications table verified.")
    except Exception as exc:
        print(f"⚠️  Could not auto-create notifications table: {exc}")

    # ── F-13.1: Column migrations for OJT clearance ───────────────────────────
    _ojt_db = SessionLocal()
    try:
        from sqlalchemy import text as _ojt_text
        _ojt_db.execute(_ojt_text(
            "ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS "
            "ojt_clearance_status VARCHAR(20) NOT NULL DEFAULT 'NOT_REQUIRED'"
        ))
        _ojt_db.execute(_ojt_text(
            "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS "
            "ojt_subject_code VARCHAR(50)"
        ))
        _ojt_db.execute(_ojt_text(
            "ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS "
            "equipment_clearance_status VARCHAR(20) NOT NULL DEFAULT 'CLEARED'"
        ))
        _ojt_db.commit()
        print("✅ OJT + equipment clearance columns verified.")
    except Exception as exc:
        _ojt_db.rollback()
        print(f"⚠️  Could not migrate OJT clearance columns: {exc}")
    finally:
        _ojt_db.close()

    # ── SE-08: Safe column migration for audit_events ─────────────────────────
    _mig_db = SessionLocal()
    try:
        from sqlalchemy import text
        _mig_db.execute(text(
            "ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS "
            "anomaly_narrative TEXT"
        ))
        _mig_db.execute(text(
            "ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS "
            "narrative_status VARCHAR(20) NOT NULL DEFAULT 'NONE'"
        ))
        _mig_db.execute(text(
            "ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS "
            "narrative_acknowledged_at TIMESTAMPTZ"
        ))
        _mig_db.commit()
        print("✅ Audit narrative columns verified.")
    except Exception as exc:
        _mig_db.rollback()
        print(f"⚠️  Could not migrate audit_events columns: {exc}")
    finally:
        _mig_db.close()

    # ── COR release columns ───────────────────────────────────────────────────
    _cor_db = SessionLocal()
    try:
        from sqlalchemy import text as _cor_text
        _cor_db.execute(_cor_text(
            "ALTER TABLE student_enrollment_requests ADD COLUMN IF NOT EXISTS "
            "cor_release_status VARCHAR(20) NOT NULL DEFAULT 'PENDING'"
        ))
        _cor_db.execute(_cor_text(
            "ALTER TABLE student_enrollment_requests ADD COLUMN IF NOT EXISTS "
            "cor_released_at TIMESTAMPTZ"
        ))
        _cor_db.execute(_cor_text(
            "ALTER TABLE student_enrollment_requests ADD COLUMN IF NOT EXISTS "
            "cor_released_by_secretary_id INTEGER"
        ))
        _cor_db.commit()
        print("✅ COR release columns verified.")
    except Exception as exc:
        _cor_db.rollback()
        print(f"⚠️  Could not migrate COR release columns: {exc}")
    finally:
        _cor_db.close()

    # ── Support ticket schema migration (removed AI triage columns) ──────────
    _sup_db = SessionLocal()
    try:
        from sqlalchemy import text as _sup_text
        _sup_db.execute(_sup_text(
            "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS "
            "department VARCHAR(50) NOT NULL DEFAULT 'GENERAL'"
        ))
        _sup_db.execute(_sup_text(
            "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS "
            "resolution_note TEXT"
        ))
        # Migrate any existing AI-predicted categories into the new department column
        _sup_db.execute(_sup_text(
            "UPDATE support_tickets SET department = ai_predicted_category "
            "WHERE department = 'GENERAL' AND ai_predicted_category IS NOT NULL AND ai_predicted_category != ''"
        ))
        _sup_db.commit()
        print("✅ Support ticket columns verified.")
    except Exception as exc:
        _sup_db.rollback()
        print(f"⚠️  Could not migrate support_tickets columns: {exc}")
    finally:
        _sup_db.close()

    # ── SE-02: Safe column migration for faculty_profiles ────────────────────
    _fac_db = SessionLocal()
    try:
        from sqlalchemy import text as _text
        _fac_db.execute(_text(
            "ALTER TABLE faculty_profiles ADD COLUMN IF NOT EXISTS "
            "specialization_tags TEXT"
        ))
        _fac_db.execute(_text(
            "ALTER TABLE faculty_profiles ADD COLUMN IF NOT EXISTS "
            "performance_score FLOAT DEFAULT 0.0"
        ))
        _fac_db.commit()
        print("✅ Faculty matching columns verified.")
    except Exception as exc:
        _fac_db.rollback()
        print(f"⚠️  Could not migrate faculty_profiles columns: {exc}")
    finally:
        _fac_db.close()

    # ── APScheduler for SE-01.05 ──────────────────────────────────────────────
    try:
        # pyrefly: ignore [missing-import]
        import apscheduler
        # pyrefly: ignore [missing-import]
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        # Retrain on the 1st of every month at 02:00 — after enrollment closes
        scheduler.add_job(
            _run_scheduled_forecast,
            "cron",
            day=1,
            hour=2,
            minute=0,
            id="enrollment_forecast_retrain",
            replace_existing=True,
        )

        # SE-08: Process pending AI narratives every 5 minutes
        def _run_narrative_processing() -> None:
            db = SessionLocal()
            try:
                from src.modules.audit import service as audit_service
                result = audit_service.process_pending_narratives(db, limit=5)
                if result["generated"] > 0 or result["failed"] > 0:
                    print(
                        f"✅ Audit narratives — "
                        f"generated: {result['generated']}, failed: {result['failed']}"
                    )
            except Exception as exc:
                print(f"❌ Narrative processing failed: {exc}")
            finally:
                db.close()

        scheduler.add_job(
            _run_narrative_processing,
            "interval",
            minutes=5,
            id="audit_narrative_processing",
            replace_existing=True,
        )

        scheduler.start()
        print("✅ Enrollment forecast scheduler started (runs 1st of each month, 02:00).")
    except ImportError:
        scheduler = None
        print("⚠️  apscheduler not installed — auto-retraining disabled. Run: pip install apscheduler")
    yield
    if scheduler:
        scheduler.shutdown()


app = FastAPI(
    title="University Campus System API (v2)",
    description="A highly scalable, modular monolith for Enrollment and Faculty Management.",
    version="2.0.0",
    lifespan=lifespan,
)

# --- RATE LIMITER ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.include_router(analytics_router)
app.include_router(ojt_router)
app.include_router(equipment_router)
app.include_router(completion_router)
app.include_router(mapping_router)
app.include_router(petition_router)
app.include_router(documents_router)
app.include_router(facilities_router)
app.include_router(cor_router)
app.include_router(honors_router)

# --- MAINTENANCE MIDDLEWARE ---
_MAINT_EXEMPT_PATHS = frozenset([
    "/authentication/login",
    "/authentication/refresh",
    "/authentication/logout",
    "/authentication/wall-of-shame",
    "/settings",
    "/system-init-secure-99",
    "/",
    "/announcements",
    "/latin-honors",
])

@app.middleware("http")
async def maintenance_mode_middleware(request: Request, call_next):
    # 1. Skip preflight OPTIONS requests immediately
    if request.method == "OPTIONS":
        return await call_next(request)

    # 2. Exempt paths that must stay open so admins can recover the system
    path = request.url.path
    if path in _MAINT_EXEMPT_PATHS or any(path.startswith(p + "/") for p in _MAINT_EXEMPT_PATHS):
        return await call_next(request)

    # 3. Read from TTL cache — no DB hit unless the cache has expired
    state = _get_maintenance_state(SessionLocal)

    if state["mode"]:
        # Allow ADMIN and SECRETARY to bypass via their JWT
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                from jose import jwt as _jwt
                payload = _jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                if payload.get("role") in ("ADMIN", "SECRETARY"):
                    return await call_next(request)
            except Exception:
                pass

        return JSONResponse(
            status_code=503,
            content={
                "maintenance": True,
                "reason":  state["reason"]  or "Neural Infrastructure Recalibration",
                "message": state["message"] or "The system is currently undergoing maintenance. Please try again later.",
            },
        )

    return await call_next(request)

# --- UTILITY ROUTES ---
@app.get("/system-init-secure-99")
def emergency_setup(request: Request):
    import secrets as _sec
    # Disabled entirely when INIT_SECRET is not configured in .env
    if not settings.INIT_SECRET:
        return JSONResponse(status_code=404, content={"detail": "Not found."})

    provided = request.headers.get("X-Init-Secret", "")
    # compare_digest prevents timing-based enumeration of the secret
    if not _sec.compare_digest(provided, settings.INIT_SECRET):
        return JSONResponse(status_code=404, content={"detail": "Not found."})

    # Idempotency guard — refuse to re-seed a live database
    _check_db = SessionLocal()
    try:
        from src.modules.auth.models import UserAccount as _UA
        if _check_db.query(_UA).first() is not None:
            return {"status": "SKIPPED", "message": "Database already initialized."}
    finally:
        _check_db.close()

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
    e_open = False
    db_up = False
    try:
        s = db.query(SystemSettings).filter(SystemSettings.settings_id == 1).first()
        if s:
            m_status = s.is_maintenance_mode
            m_reason = s.maintenance_reason
            e_open = s.is_enrollment_open
        db_up = True
    except Exception:
        db_up = False
    finally:
        db.close()
        
    return {
        "system_status": "Maintenance" if m_status else "Online",
        "database_status": "ONLINE" if db_up else "OFFLINE",
        "maintenance_mode": m_status,
        "maintenance_reason": m_reason,
        "enrollment_open": e_open,
        "allowed_origins": settings.allowed_origins_list,
    }

@app.get("/announcements")
def get_announcements():
    db = SessionLocal()
    try:
        # Get latest 10 announcements
        announcements = db.query(SystemAnnouncement).order_by(SystemAnnouncement.created_at.desc()).limit(10).all()
        return [
            {
                "id": a.id,
                "title": a.title,
                "body": a.body,
                "type": a.type,
                "status": a.status,
                "created_at": a.created_at.strftime("%B %d, %Y — %I:%M %p")
            } for a in announcements
        ]
    finally:
        db.close()

# --- CORS CONFIGURATION (Outermost Layer) ---
# We register this LAST so it wraps around ALL other middlewares, including maintenance mode.
# Add all allowed origins (including the Vercel URL) to ALLOWED_ORIGINS in .env instead of hardcoding here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)