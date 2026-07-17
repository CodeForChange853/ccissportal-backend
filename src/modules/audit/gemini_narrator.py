# SE-08 — AI-Generated Audit Anomaly Narratives

from src.core.config import settings


def generate_narrative(event) -> str:
    """
    Calls Gemini to produce a plain-English security narrative for a flagged audit event.
    Returns a concise narrative string, or raises on failure so the caller can mark FAILED.
    """
    from google import genai
    from google.genai import types

    hour = event.created_at.hour if event.created_at else "unknown"
    time_label = f"{hour:02d}:xx UTC" if isinstance(hour, int) else "unknown time"
    score_label = (
        "HIGH RISK (off-hours + sensitive operation)"
        if event.anomaly_score >= 70
        else "MODERATE RISK (off-hours or sensitive operation)"
    )

    payload_str = ""
    if event.payload:
        interesting = {k: v for k, v in event.payload.items() if k not in ("threat_mitigation_engaged", "action_taken")}
        if interesting:
            payload_str = f"\nAdditional context: {interesting}"

    prompt = (
        "You are a university security analyst AI. Summarize the following audit event "
        "in 2-3 sentences for an administrator. Be direct and factual. "
        "Mention what happened, who did it, why it is flagged, and any automated action taken. "
        "Do not use markdown, bullet points, or headers — plain prose only.\n\n"
        f"Event type: {event.event_type}\n"
        f"Actor: {event.actor_email or 'anonymous'}\n"
        f"Target: {event.target_type or 'N/A'} #{event.target_id or 'N/A'}\n"
        f"Time: {time_label}\n"
        f"Anomaly classification: {score_label}\n"
        f"Automated action: {event.payload.get('action_taken', 'none') if event.payload else 'none'}"
        f"{payload_str}"
    )

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=200,
            temperature=0.3,
        ),
    )
    return response.text.strip()
