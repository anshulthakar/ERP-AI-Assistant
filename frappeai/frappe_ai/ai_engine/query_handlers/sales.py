from frappeai.frappe_ai.ai_engine.intent_parser import SALES_ORDER_AS_FINANCE_KEYWORDS
from frappeai.frappe_ai.ai_engine.query_handlers.sales_order import get_sales_order_data


def _is_sales_order_query(msg: str) -> bool:
	if any(k in msg for k in SALES_ORDER_AS_FINANCE_KEYWORDS):
		return True
	return "so-" in msg


def get_sales_data(message):
	"""
	Sales intent handler. All Sales Order related questions (status,
	customer, date, amount, delivery, item, summary/breakdown) are now
	handled centrally by sales_order.get_sales_order_data, so both the
	"sales" intent and the "finance" intent (via finance.py) return the
	exact same response shape for Sales Order queries.
	"""
	msg = (message or "").lower()

	if _is_sales_order_query(msg):
		return get_sales_order_data(message)

	# Generic "sales" intent that isn't specifically about Sales Orders
	# (e.g. "customer revenue", "top customers") falls back to a recent
	# Sales Order summary until dedicated handling is added for those.
	return get_sales_order_data(message)