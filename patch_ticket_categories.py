# backend-v2/patch_ticket_categories.py
from src.core.database_setup import SessionLocal
from src.modules.support.models import SupportTicket
from src.modules.auth.models import UserAccount

def patch_categories():
    db = SessionLocal()
    try:
        # Mapping old categories to new standard departments
        mapping = {
            "technical": "IT SUPPORT",
            "student affairs": "ACADEMIC AFFAIRS",
            "GENERAL_SUPPORT": "ACADEMIC AFFAIRS",
            "registrar": "REGISTRAR",
            "finance": "FINANCE"
        }

        print("Patching ticket categories in database...")
        tickets = db.query(SupportTicket).all()
        updated_count = 0

        for ticket in tickets:
            old_cat = ticket.ai_predicted_category
            if old_cat in mapping:
                ticket.ai_predicted_category = mapping[old_cat]
                updated_count += 1
            elif old_cat not in ["IT SUPPORT", "REGISTRAR", "FINANCE", "ACADEMIC AFFAIRS"]:
                # Default anything else to ACADEMIC AFFAIRS to avoid dashboard bugs
                ticket.ai_predicted_category = "ACADEMIC AFFAIRS"
                updated_count += 1

        db.commit()
        print(f"Updated {updated_count} tickets to standard departments.")

    except Exception as e:
        print(f"Error during patch: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    patch_categories()
