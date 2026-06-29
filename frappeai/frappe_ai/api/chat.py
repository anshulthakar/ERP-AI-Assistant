import frappe
import requests
import time

from frappeai.frappe_ai.ai_engine.intent_parser import detect_intent
from frappeai.frappe_ai.ai_engine.query_builder import get_context_data
from frappeai.frappe_ai.ai_engine.formatter import format_context


@frappe.whitelist()
def ask_ai(message, session_id=None, context_type="general"):

    start_time = time.time()

    settings = frappe.get_single("AI Assistant Settings")

    if not settings.enable_ai:
        frappe.throw("AI Assistant is disabled")

    try:

        # -------------------------------------------------
        # Detect User Intent
        # -------------------------------------------------

        intent = detect_intent(message)

        # -------------------------------------------------
        # Fetch ERP Context Data
        # -------------------------------------------------

        context_data = get_context_data(intent, message)

        # -------------------------------------------------
        # Format ERP Data (VERY IMPORTANT FOR PERFORMANCE)
        # -------------------------------------------------

        formatted_context = format_context(context_data)

        # -------------------------------------------------
        # Build Prompt
        # -------------------------------------------------

        system_prompt = settings.system_prompt or ""

        prompt = f"""
{system_prompt}

You are an ERPNext AI Assistant.

User Intent:
{intent}

ERP Data:
{formatted_context}

Question:
{message}

Instructions:
- Answer briefly
- Use ERP data only
- Be professional
- If no data found say clearly
"""

        # -------------------------------------------------
        # Ollama Request
        # -------------------------------------------------

        payload = {
            "model": settings.default_model,
            "prompt": prompt,
            "stream": False,

            "options": {
                "temperature": 0.3,
                "num_predict": 120,
                "top_p": 0.9
            }
        }

        response = requests.post(
            f"{settings.base_url}/api/generate",
            json=payload,
            timeout=60
        )

        response.raise_for_status()

        data = response.json()

        ai_reply = data.get("response", "").strip()

        # -------------------------------------------------
        # Create / Load Session
        # -------------------------------------------------

        if session_id:

            try:
                session = frappe.get_doc(
                    "AI Chat Session",
                    session_id
                )

            except frappe.DoesNotExistError:

                session = create_new_session(
                    message,
                    context_type,
                    settings.default_model
                )

        else:

            session = create_new_session(
                message,
                context_type,
                settings.default_model
            )

        # -------------------------------------------------
        # Save User Message
        # -------------------------------------------------

        save_message(
            session.name,
            "User",
            message,
            round(time.time() - start_time, 2)
        )

        # -------------------------------------------------
        # Save Assistant Message
        # -------------------------------------------------

        save_message(
            session.name,
            "Assistant",
            ai_reply,
            round(time.time() - start_time, 2)
        )

        # -------------------------------------------------
        # Update Session
        # -------------------------------------------------

        session.last_activity = frappe.utils.now()

        session.total_messages = (
            session.total_messages or 0
        ) + 2

        session.save(ignore_permissions=True)

        frappe.db.commit()

        # -------------------------------------------------
        # Final Response
        # -------------------------------------------------

        return {
            "reply": ai_reply,
            "session_id": session.name,
            "intent": intent
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "AI Chat Error"
        )

        return {
            "reply": f"AI Error: {str(e)}"
        }


# =========================================================
# Create New Session
# =========================================================

def create_new_session(message, context_type, model):

    title = (
        message[:60] + "..."
        if len(message) > 60
        else message
    )

    session = frappe.get_doc({
        "doctype": "AI Chat Session",
        "session_title": title,
        "user": frappe.session.user,
        "context_type": context_type,
        "status": "Active",
        "started_on": frappe.utils.now(),
        "last_activity": frappe.utils.now(),
        "total_messages": 0,
        "model": model
    })

    session.insert(ignore_permissions=True)

    return session


# =========================================================
# Save Messages
# =========================================================

def save_message(session_id, role, message, response_time=0):

    doc = frappe.get_doc({
        "doctype": "AI Chat Message",
        "session": session_id,
        "role": role,
        "message": message,
        "response_time": response_time
    })

    doc.insert(ignore_permissions=True)