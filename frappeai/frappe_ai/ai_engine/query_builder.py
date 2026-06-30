"""
Query Builder
-------------
Routes a parsed intent to the appropriate domain-specific query handler
and returns structured context data that can be fed back into the LLM
(or formatter) to produce the final user-facing response.

Each handler module (finance, sales, inventory, hr) is responsible for:
    - Interpreting the natural-language `message` for relevant filters
      (dates, customer names, item codes, etc.)
    - Querying Frappe/ERPNext via frappe.db / frappe.get_all
    - Returning a JSON-serializable dict of results

Adding a new domain only requires:
    1. Creating `query_handlers/<domain>.py` with a `get_<domain>_data(message)` function
    2. Registering it in the INTENT_HANDLERS map below
"""

import frappe
from frappe.utils.logger import get_logger

from frappeai.frappe_ai.ai_engine.query_handlers.finance import get_finance_data
from frappeai.frappe_ai.ai_engine.query_handlers.sales import get_sales_data
from frappeai.frappe_ai.ai_engine.query_handlers.inventory import get_inventory_data
from frappeai.frappe_ai.ai_engine.query_handlers.hr import get_hr_data

logger = get_logger("frappeai")

# Maps a recognized intent to its handler function.
# Each handler must accept a single `message: str` argument and
# return a dict (empty dict on no results, never None).
INTENT_HANDLERS = {
	"finance": get_finance_data,
	"sales": get_sales_data,
	"inventory": get_inventory_data,
	"hr": get_hr_data,
}


def get_context_data(intent: str, message: str) -> dict:
	"""
	Resolve and execute the query handler for the given intent.

	Args:
		intent: The classified intent (e.g. "finance", "sales", "inventory", "hr").
		        Expected to come from intent_parser.py.
		message: The original user message, passed through so handlers can
		         extract their own filters (dates, item/customer names, etc.).

	Returns:
		A dict of context data for the handler's domain. Returns an empty
		dict if the intent is unrecognized, the message is empty, or the
		handler raises an error (errors are logged, not propagated, so a
		single bad query doesn't crash the chat response).
	"""
	if not intent or not message:
		return {}

	handler = INTENT_HANDLERS.get(intent.lower().strip())

	if handler is None:
		logger.warning(f"frappeai: no query handler registered for intent '{intent}'")
		return {}

	try:
		data = handler(message)
		return data or {}
	except Exception:
		# Log full traceback to the Frappe error log for debugging,
		# but never let a handler failure break the chat flow.
		frappe.log_error(
			title=f"frappeai: query handler failed for intent '{intent}'",
			message=frappe.get_traceback(),
		)
		logger.error(f"frappeai: error in handler for intent '{intent}'", exc_info=True)
		return {}