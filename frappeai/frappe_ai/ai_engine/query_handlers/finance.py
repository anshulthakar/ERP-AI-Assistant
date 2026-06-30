import frappe
from frappe.utils import add_days, getdate

from frappeai.frappe_ai.ai_engine.entity_parser import extract_filters
from frappeai.frappe_ai.ai_engine.intent_parser import SALES_ORDER_AS_FINANCE_KEYWORDS
from frappeai.frappe_ai.ai_engine.query_handlers.sales_order import get_sales_order_data

SALES_INVOICE_FIELDS = [
	"name",
	"customer",
	"status",
	"posting_date",
	"due_date",
	"grand_total",
	"outstanding_amount",
]


def _is_sales_order_query(message_lc: str) -> bool:
	if any(k in message_lc for k in SALES_ORDER_AS_FINANCE_KEYWORDS):
		return True
	return "so-" in message_lc


def _parse_customer(message: str):
	"""
	Heuristic-only customer name extraction (LLM-friendly, not NER).
	Examples: "for customer ABC", "customer ABC", "customer is ABC"
	"""
	msg = (message or "").lower()
	for token in ["for customer", "customer is", "customer"]:
		if token in msg:
			idx = msg.find(token)
			tail = (message or "")[idx + len(token):].strip()
			for sep in [" on ", " with ", " whose ", " where ", " and ", " today", " tomorrow", " last ", " this ", " "]:
				if sep in tail:
					tail = tail.split(sep)[0]
			tail = tail.strip(" ,;:.")
			if tail:
				return tail
	return None


def _parse_date_window(message: str) -> dict:
	"""Returns Frappe filters for posting_date/due_date on Sales Invoice."""
	msg = (message or "").lower()
	today = getdate(frappe.utils.today())

	if "today" in msg:
		return {"posting_date": ["between", [str(today), str(today)]]}

	if "last 7" in msg or "last seven" in msg:
		start = add_days(today, -7)
		return {"posting_date": ["between", [str(start), str(today)]]}

	if "last month" in msg:
		this_month_start = today.replace(day=1)
		last_month_end = add_days(this_month_start, -1)
		last_month_start = last_month_end.replace(day=1)
		return {"posting_date": ["between", [str(last_month_start), str(last_month_end)]]}

	if "this year" in msg or "current year" in msg:
		start = today.replace(month=1, day=1)
		return {"posting_date": ["between", [str(start), str(today)]]}

	if "due" in msg and ("next 7" in msg or "next seven" in msg):
		end = add_days(today, 7)
		return {"due_date": ["between", [str(today), str(end)]]}

	return {}


def get_finance_data(message):
	"""
	Finance intent handler. Sales Order questions are delegated to the
	centralized sales_order.py handler (status/date/amount/delivery/item/
	summary parsing all live there). Everything else defaults to Sales
	Invoice handling below.
	"""
	message_lc = (message or "").lower()

	if _is_sales_order_query(message_lc):
		return get_sales_order_data(message)

	parsed = extract_filters(message, intent="finance")
	doctype = parsed.get("doctype") or "Sales Invoice"

	filters = {"docstatus": 1}
	filters.update(parsed.get("filters", {}))

	customer = _parse_customer(message)
	if customer:
		filters["customer"] = customer

	filters.update(_parse_date_window(message))

	if doctype == "Sales Invoice":
		if not filters.get("status"):
			if any(k in message_lc for k in ["overdue", "late"]):
				filters["status"] = "Overdue"
			elif any(k in message_lc for k in ["unpaid", "outstanding", "receivable", "due"]):
				filters["status"] = "Unpaid"
			elif any(k in message_lc for k in ["paid", "completed"]):
				filters["status"] = "Paid"

		if filters.get("status") == "Overdue":
			order_by, top_n = "due_date asc", 10
		elif filters.get("status") == "Unpaid":
			order_by, top_n = "outstanding_amount desc, due_date asc", 10
		else:
			order_by, top_n = "posting_date desc", 5

		records = frappe.get_all(
			doctype,
			filters=filters,
			fields=SALES_INVOICE_FIELDS,
			order_by=order_by,
			limit=top_n,
		)

		summary = {
			"count": len(records),
			"sum_grand_total": sum(row.get("grand_total") or 0 for row in records),
			"sum_outstanding_amount": sum(row.get("outstanding_amount") or 0 for row in records),
		}

		return {"doctype": doctype, "applied_filters": filters, "summary": summary, "data": records}

	# Fallback: query whatever doctype was detected by extract_filters.
	records = frappe.get_all(doctype, filters=filters, fields=["name"], limit=10)
	return {
		"doctype": doctype,
		"applied_filters": filters,
		"summary": {"count": len(records)},
		"data": records,
	}