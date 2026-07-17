from sqlalchemy.orm import Session
from . import repository, schemas
from .search_engine import parse_command_intent, strip_verb_prefix, score_by_tfidf


def run_omni_search(db: Session, q: str) -> list[schemas.OmniSearchResult]:
    action_type, target_name = parse_command_intent(q)

    if action_type in ("MAINTENANCE_ON", "MAINTENANCE_OFF"):
        label = "Enable Maintenance Mode" if action_type == "MAINTENANCE_ON" else "Disable Maintenance Mode"
        return [schemas.OmniSearchResult(
            result_type="ACTION",
            result_id=0,
            primary_text=label,
            secondary_text="System — takes effect immediately",
            relevance_score=1.0,
            action_type=action_type,
        )]

    search_term = target_name if (action_type and target_name) else strip_verb_prefix(q)
    term = f"%{search_term}%"
    results: list[schemas.OmniSearchResult] = []

    for user, profile in repository.search_students(db, term):
        full_name = f"{profile.first_name} {profile.last_name}".strip()
        results.append(schemas.OmniSearchResult(
            result_type=   "ACTION" if action_type else "STUDENT",
            result_id=     user.account_id,
            primary_text=  full_name or user.email_address,
            secondary_text=profile.student_number or user.email_address,
            action_type=   action_type,
        ))

    for fp in repository.search_faculty(db, term):
        results.append(schemas.OmniSearchResult(
            result_type=   "ACTION" if action_type else "FACULTY",
            result_id=     fp.faculty_account_id,
            primary_text=  f"{fp.first_name} {fp.last_name}",
            secondary_text=fp.academic_department,
            action_type=   action_type,
        ))

    if not action_type:
        for subj in repository.search_subjects(db, term):
            results.append(schemas.OmniSearchResult(
                result_type=   "SUBJECT",
                result_id=     subj.subject_id,
                primary_text=  subj.subject_code,
                secondary_text=subj.subject_title,
            ))

    if not results:
        return []

    texts  = [f"{r.primary_text} {r.secondary_text or ''}" for r in results]
    scores = score_by_tfidf(search_term, texts)
    for result, score in zip(results, scores):
        result.relevance_score = score

    results.sort(key=lambda r: r.relevance_score, reverse=True)
    return results[:15]
