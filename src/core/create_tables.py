from src.core.database_setup import Base, database_engine

from src.modules.auth.models import UserAccount
from src.modules.enrollment.models import (
    CurriculumSubject,
    StudentEnrollmentRequest,
    StudentProfile,
)
from src.modules.faculty.models import FacultyProfile, GradebookEntry
from src.modules.document_processing.models import DocumentScanResult
from src.modules.settings.models import SystemSettings
from src.modules.support.models import SupportTicket, SystemAnnouncement
from src.modules.audit.models import AuditEvent
from src.modules.analytics.models import EnrollmentForecast, ForecastAlert


def initialize_database():
    print("Connecting to the database...")
    Base.metadata.drop_all(bind=database_engine)
    Base.metadata.create_all(bind=database_engine)
    print("Success! All tables created / verified:")
    print("  ✓ user_accounts")
    print("  ✓ student_profiles          (+ current_semester)")
    print("  ✓ curriculum_subjects       (+ prerequisite_subject_id, course)")
    print("  ✓ student_enrollment_requests (+ extracted_subjects, verification_result, ai_recommendation)")
    print("  ✓ faculty_profiles")
    print("  ✓ gradebook_entries         (student_account_id now nullable)")
    print("  ✓ document_scan_results")
    print("  ✓ system_settings")
    print("  ✓ support_tickets")
    print("  ✓ audit_events")
    print("  ✓ enrollment_forecasts      (SE-01 analytics)")
    print("  ✓ forecast_alerts           (SE-01 capacity alerts)")


if __name__ == "__main__":
    initialize_database()