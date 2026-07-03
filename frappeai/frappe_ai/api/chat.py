import time

import frappe
import requests

from frappeai.frappe_ai.ai_engine.formatter import format_context
from frappeai.frappe_ai.ai_engine.intent_parser import detect_intent
from frappeai.frappe_ai.ai_engine.query_builder import get_context_data

GENERIC_ERROR_REPLY = "Sorry, something went wrong while processing your request. Please try again."


@frappe.whitelist(methods=["POST"])
def ask_ai(message, session_id=None, context_type="general"):
	start_time = time.time()

	message = (message or "").strip()
	if not message:
		frappe.throw("Message cannot be empty")

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
- Present each record from the ERP Data section as a separate bullet point,
  preserving its fields (name, customer, status, dates, amounts, etc.) --
  do NOT collapse multiple records into a single summary sentence.
- Keep any commentary around the data brief; the data itself should stay
  in the same structured, itemized format shown in the ERP Data section.
- Use ERP data only
- Be professional
- The "ERP Data" section above is the ONLY source of truth. If it contains
  records, you MUST describe them -- never say data is "not available" or
  "couldn't be found" when records are listed above.
- Only say no data was found if the ERP Data section literally says
  "No ERP data found" or is empty.
"""

		# -------------------------------------------------
		# Ollama Request
		# -------------------------------------------------
		# num_predict caps how many tokens Ollama is allowed to generate.
		# A fixed low value (was 120) cut replies off mid-sentence once there
		# was more than a couple of records to describe. Scale it with the
		# amount of ERP data we're feeding in, balanced against response time
		# -- local generation is sequential, so higher caps directly add to
		# latency. 400 is enough for ~15-20 rows without ballooning wait time.
		num_predict = min(max(150, len(formatted_context) // 3), 400)

		payload = {
			"model": settings.default_model,
			"prompt": prompt,
			"stream": False,
			"options": {
				"temperature": 0.1,
				"num_predict": num_predict,
				"top_p": 0.9,
			},
		}

		try:
			response = requests.post(
				f"{settings.base_url}/api/generate",
				json=payload,
				timeout=60,
			)
			response.raise_for_status()
			data = response.json()
		except requests.exceptions.ConnectionError:
			frappe.log_error(frappe.get_traceback(), "AI Chat Error - Ollama unreachable")
			return {"reply": "AI service is currently unreachable. Please check that Ollama is running."}
		except requests.exceptions.Timeout:
			frappe.log_error(frappe.get_traceback(), "AI Chat Error - Ollama timeout")
			return {"reply": "AI service took too long to respond. Please try again."}
		except requests.exceptions.RequestException:
			frappe.log_error(frappe.get_traceback(), "AI Chat Error - Ollama request failed")
			return {"reply": GENERIC_ERROR_REPLY}

		ai_reply = (data.get("response") or "").strip()
		if not ai_reply:
			ai_reply = "I couldn't generate a response for that. Please try rephrasing your question."

		# -------------------------------------------------
		# Create / Load Session (with ownership check)
		# -------------------------------------------------
		session = _get_or_create_session(session_id, message, context_type, settings.default_model)

		# -------------------------------------------------
		# Save Messages
		# -------------------------------------------------
		save_message(session.name, "User", message, round(time.time() - start_time, 2))
		save_message(session.name, "Assistant", ai_reply, round(time.time() - start_time, 2))

		# -------------------------------------------------
		# Update Session
		# -------------------------------------------------
		session.last_activity = frappe.utils.now()
		session.total_messages = (session.total_messages or 0) + 2
		session.save(ignore_permissions=True)

		frappe.db.commit()

		return {
			"reply": ai_reply,
			"session_id": session.name,
			"intent": intent,
		}

	except frappe.PermissionError:
		# Re-raise permission errors as-is so the user gets a clear message
		# instead of the generic fallback below.
		raise

	except Exception:
		frappe.log_error(frappe.get_traceback(), "AI Chat Error")
		return {"reply": GENERIC_ERROR_REPLY}


def _get_or_create_session(session_id, message, context_type, model):
	"""
	Load an existing session if session_id is provided, otherwise create a
	new one. Verifies the session belongs to the current user -- without
	this check, any logged-in user could pass an arbitrary session_id and
	read/append messages to someone else's chat session.
	"""
	if session_id:
		try:
			session = frappe.get_doc("AI Chat Session", session_id)
		except frappe.DoesNotExistError:
			return create_new_session(message, context_type, model)

		if session.user != frappe.session.user:
			frappe.throw("You do not have permission to access this chat session", frappe.PermissionError)

		return session

	return create_new_session(message, context_type, model)


# =========================================================
# Create New Session
# =========================================================

def create_new_session(message, context_type, model):
	title = message[:60] + "..." if len(message) > 60 else message

	session = frappe.get_doc({
		"doctype": "AI Chat Session",
		"session_title": title,
		"user": frappe.session.user,
		"context_type": context_type,
		"status": "Active",
		"started_on": frappe.utils.now(),
		"last_activity": frappe.utils.now(),
		"total_messages": 0,
		"model": model,
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
		"response_time": response_time,
	})

	doc.insert(ignore_permissions=True)