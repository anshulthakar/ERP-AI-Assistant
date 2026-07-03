"""
Sales Order Query Handler
--------------------------
Centralized parsing + querying logic for all Sales Order related natural
language questions. This consolidates logic that was previously duplicated
across finance.py and sales.py into one place.

Supported query categories:
    1. Status-based      - "pending sales orders", "overdue", "cancelled", "closed"
    2. Customer-specific  - "sales orders for customer ABC"
    3. Date/time-based    - "today", "this week", "this month", "last month"
    4. Amount-based       - "above 1 lakh", "more than 50000"
    5. Delivery-related   - "due for delivery next 7 days", "missed delivery date"
    6. Item-specific      - "sales orders for item <item_code>"
    7. Count/summary      - "status breakdown", "how many sales orders this month"

Usage:
    from frappeai.frappe_ai.ai_engine.query_handlers.sales_order import get_sales_order_data
    result = get_sales_order_data(message)
"""

import re

import frappe
from frappe.utils import add_days, add_months, getdate

SALES_ORDER_FIELDS = [
	"name",
	"customer",
	"status",
	"transaction_date",
	"delivery_date",
	"grand_total",
	"per_billed",
	"per_delivered",
]

# Max raw records ever sent into the LLM prompt. Keep this small -- the
# true total/sum is always computed separately via frappe.db.count/sql
# regardless of this cap, so users still get accurate totals even when
# hundreds or thousands of records match.
DISPLAY_LIMIT = 10

STATUS_KEYWORDS = {
	"Cancelled": ["cancel", "cancelled", "canceled"],
	"Closed": ["closed"],
	"Completed": ["completed", "delivered and billed", "fully delivered"],
	"To Deliver and Bill": ["to deliver and bill", "pending delivery and billing"],
	# Checked after "to deliver and bill" so it doesn't partially match it.
	"To Bill": ["to bill", "awaiting billing", "pending billing"],
	"To Deliver": ["to deliver", "awaiting delivery", "pending delivery"],
}

# Indian-style large-number words, used for amount parsing ("1 lakh" = 100,000).
AMOUNT_MULTIPLIERS = {
	"lakh": 100_000,
	"lakhs": 100_000,
	"crore": 10_000_000,
	"crores": 10_000_000,
	"k": 1_000,
}


def _parse_status(msg: str):
	# "overdue" is handled separately (it depends on delivery_date vs today,
	# not a literal ERPNext status value), so skip it here.
	if "overdue" in msg:
		return None

	for status, keywords in STATUS_KEYWORDS.items():
		if any(k in msg for k in keywords):
			return status
	return None


def _parse_customer(message: str):
	msg = (message or "").lower()
	# Order matters: check longer/more specific phrases first so "for customer
	# name X" doesn't get matched by the shorter "for customer" token, which
	# would otherwise leave a stray "name " stuck onto the parsed value.
	for token in ["for customer name", "customer name is", "customer name", "for customer", "customer is", "customer"]:
		if token in msg:
			idx = msg.find(token)
			tail = (message or "")[idx + len(token):].strip()
			for sep in [" on ", " with ", " whose ", " where ", " and ", " today", " tomorrow", " last ", " this ", " above ", " more than ", " "]:
				if sep in tail:
					tail = tail.split(sep)[0]
			tail = tail.strip(" ,;:.")
			if tail:
				return tail
	return None


def _parse_date_window(msg: str) -> dict:
	"""Returns a transaction_date filter based on date phrases."""
	today = getdate(frappe.utils.today())

	if "today" in msg:
		return {"transaction_date": ["between", [str(today), str(today)]]}

	if "this week" in msg:
		start = add_days(today, -today.weekday())
		return {"transaction_date": ["between", [str(start), str(today)]]}

	if "last 7" in msg or "last seven" in msg:
		start = add_days(today, -7)
		return {"transaction_date": ["between", [str(start), str(today)]]}

	if "this month" in msg or "current month" in msg:
		start = today.replace(day=1)
		return {"transaction_date": ["between", [str(start), str(today)]]}

	if "last month" in msg:
		this_month_start = today.replace(day=1)
		last_month_end = add_days(this_month_start, -1)
		last_month_start = last_month_end.replace(day=1)
		return {"transaction_date": ["between", [str(last_month_start), str(last_month_end)]]}

	if "this year" in msg or "current year" in msg:
		start = today.replace(month=1, day=1)
		return {"transaction_date": ["between", [str(start), str(today)]]}

	return {}


def _parse_delivery_window(msg: str) -> dict:
	"""
	Returns a delivery_date filter for upcoming or missed deliveries.
	Distinct from transaction_date filters used for order creation date.
	"""
	today = getdate(frappe.utils.today())

	if "missed delivery" in msg or ("overdue" in msg and "deliver" in msg) or "overdue delivery" in msg:
		# delivery_date in the past, and not yet fully delivered/closed/cancelled
		return {"delivery_date": ["<", str(today)]}

	if ("next 7" in msg or "next seven" in msg or "upcoming" in msg) and "deliver" in msg:
		end = add_days(today, 7)
		return {"delivery_date": ["between", [str(today), str(end)]]}

	return {}


def _parse_amount_threshold(msg: str):
	"""
	Parses phrases like "above 1 lakh", "more than 50000", "over 2 crore",
	and Hinglish equivalents like "1 lakh se zyada", "50000 ke upar" into a
	Frappe filter on grand_total. Returns None if no amount found.
	"""
	# English: keyword BEFORE the number -- "above 1 lakh"
	prefix_pattern = r"(?:above|more than|over|greater than)\s+([\d,.]+)\s*(lakh|lakhs|crore|crores|k)?"
	match = re.search(prefix_pattern, msg)

	# Hinglish: keyword AFTER the number -- "1 lakh se zyada", "50000 ke upar"
	if not match:
		suffix_pattern = r"([\d,.]+)\s*(lakh|lakhs|crore|crores|k)?\s*(?:se zyada|se jyada|zyada|ke upar|se adhik)"
		match = re.search(suffix_pattern, msg)

	if not match:
		return None

	number_str, unit = match.group(1), match.group(2)
	try:
		number = float(number_str.replace(",", ""))
	except ValueError:
		return None

	if unit:
		number *= AMOUNT_MULTIPLIERS.get(unit, 1)

	return ["grand_total", ">", number]


def _parse_item(message: str):
	"""Parses 'for item ITEM-CODE' / 'item ITEM-CODE' style phrases."""
	msg = (message or "").lower()
	for token in ["for item", "item is", "item"]:
		if token in msg:
			idx = msg.find(token)
			tail = (message or "")[idx + len(token):].strip()
			for sep in [" on ", " with ", " whose ", " where ", " and ", " today", " this ", " "]:
				if sep in tail:
					tail = tail.split(sep)[0]
			tail = tail.strip(" ,;:.")
			if tail:
				return tail
	return None


def _is_summary_request(msg: str) -> bool:
	return any(k in msg for k in ["breakdown", "summary", "how many", "count of", "total number"])


def _build_where_clause(filters: dict):
	"""
	Converts our internal filters dict (which may contain plain values or
	Frappe-style operator lists like ["between", [a, b]] / ["<", x] /
	["not in", [...]]) into a parameterized SQL WHERE clause + values list.
	Used for the raw frappe.db.sql breakdown query below, where we can't
	rely on frappe.get_all's filters argument since we need GROUP BY.
	"""
	conditions = []
	values = []

	for key, value in filters.items():
		if isinstance(value, list):
			op = value[0]
			if op == "between":
				conditions.append(f"`{key}` BETWEEN %s AND %s")
				values.extend(value[1])
			elif op in ("in", "not in"):
				placeholders = ", ".join(["%s"] * len(value[1]))
				sql_op = "IN" if op == "in" else "NOT IN"
				conditions.append(f"`{key}` {sql_op} ({placeholders})")
				values.extend(value[1])
			else:
				conditions.append(f"`{key}` {op} %s")
				values.append(value[1])
		else:
			conditions.append(f"`{key}` = %s")
			values.append(value)

	where_clause = " AND ".join(conditions) if conditions else "1=1"
	return where_clause, values


def _resolve_customer(customer_text: str):
	"""
	Resolves a user-typed customer name to the actual Customer doctype ID
	(the `name` field), which is what Sales Order.customer actually stores
	as a Link field -- this may differ from the human-readable customer_name
	depending on the naming series configured for Customer.

	Tries, in order: exact ID match, exact customer_name match, then a
	fuzzy "contains" match on customer_name.
	"""
	if not customer_text:
		return None

	# 1. Maybe the user already typed the exact Customer ID.
	if frappe.db.exists("Customer", customer_text):
		return customer_text

	# 2. Exact match on the display name.
	exact = frappe.db.get_value("Customer", {"customer_name": customer_text}, "name")
	if exact:
		return exact

	# 3. Fuzzy match in case of partial name / minor typos.
	fuzzy = frappe.db.get_value("Customer", {"customer_name": ["like", f"%{customer_text}%"]}, "name")
	return fuzzy


def get_sales_order_data(message: str) -> dict:
	"""
	Main entry point: parses the message and returns Sales Order data.

	Returns a dict shaped as:
		{
			"doctype": "Sales Order",
			"applied_filters": {...},
			"summary": {...},          # always present
			"data": [...],             # record rows (omitted for pure summary requests)
			"status_breakdown": {...}  # only present for "breakdown"-style queries
		}
	"""
	msg = (message or "").lower()

	filters = {"docstatus": 1}

	status = _parse_status(msg)
	if status:
		filters["status"] = status
	elif "pending" in msg:
		# Generic "pending" (without a specific delivery/billing qualifier
		# like "pending delivery") wasn't matching anything in STATUS_KEYWORDS,
		# so queries like "show pending sales orders" returned ALL submitted
		# orders -- including Completed ones. "Pending" really means: not yet
		# Completed, Closed, or Cancelled.
		filters["status"] = ["not in", ["Completed", "Closed", "Cancelled"]]

	customer = _parse_customer(message)
	if customer:
		resolved_customer = _resolve_customer(customer)
		if resolved_customer:
			filters["customer"] = resolved_customer
		else:
			# No matching customer found at all -- short-circuit instead of
			# running a query that's guaranteed to return zero rows, and let
			# the caller know explicitly why.
			return {
				"doctype": "Sales Order",
				"applied_filters": {"customer": customer},
				"summary": {"count": 0},
				"data": [],
				"note": f"No customer matching '{customer}' was found in the system.",
			}

	item_code = _parse_item(message)
	if item_code:
		# Sales Order items live in the child table; query via the item field
		# on Sales Order Item and resolve back to parent Sales Orders.
		so_names = frappe.get_all(
			"Sales Order Item",
			filters={"item_code": item_code},
			pluck="parent",
		)
		if not so_names:
			return {"doctype": "Sales Order", "applied_filters": filters, "summary": {"count": 0}, "data": []}
		filters["name"] = ["in", so_names]

	filters.update(_parse_date_window(msg))
	filters.update(_parse_delivery_window(msg))

	amount_filter = _parse_amount_threshold(msg)

	# "overdue" without "deliver" keyword still means: delivery date passed
	# and order isn't fully delivered/closed/cancelled.
	if "overdue" in msg and "delivery_date" not in filters:
		today = getdate(frappe.utils.today())
		filters["delivery_date"] = ["<", str(today)]
		if "status" not in filters:
			filters["status"] = ["not in", ["Closed", "Cancelled", "Completed"]]

	query_filters = dict(filters)
	if amount_filter:
		# frappe.get_all doesn't accept a bare list of conditions mixed with
		# dict filters directly, so we pass it via the `filters` list form.
		query_filters = [[k, "=", v] if not isinstance(v, list) else [k] + v for k, v in filters.items()]
		query_filters.append(amount_filter)

	if _is_summary_request(msg):
		# Status breakdown: count + sum grouped by status.
		# NOTE: newer Frappe versions block raw SQL aggregate functions
		# (e.g. "count(name) as total_count") inside frappe.get_all's
		# `fields` list as a security measure. We use a parameterized
		# frappe.db.sql query instead -- values are still placeholder-bound
		# (%s), so this remains safe against SQL injection even though we're
		# building the WHERE clause manually from our own controlled filters.
		where_clause, values = _build_where_clause(filters)

		rows = frappe.db.sql(
			f"""
			SELECT status, COUNT(name) as total_count, SUM(grand_total) as total_amount
			FROM `tabSales Order`
			WHERE {where_clause}
			GROUP BY status
			""",
			values,
			as_dict=True,
		)

		status_breakdown = {
			row["status"]: {"count": row["total_count"], "total": row.get("total_amount") or 0}
			for row in rows
		}
		total_count = sum(v["count"] for v in status_breakdown.values())

		return {
			"doctype": "Sales Order",
			"applied_filters": filters,
			"summary": {"count": total_count},
			"status_breakdown": status_breakdown,
		}

	records = frappe.get_all(
		"Sales Order",
		filters=query_filters,
		fields=SALES_ORDER_FIELDS,
		order_by="transaction_date desc",
		limit=DISPLAY_LIMIT,
	)

	# Separately count the TRUE total matching the filters, independent of
	# the DISPLAY_LIMIT cap above. This is critical at scale: if 500 orders
	# match, we never want to pull all 500 into the LLM prompt (slow, eats
	# the context window, and costs more to generate). We show a small
	# sample but always report the real total/sum so the user isn't misled
	# into thinking only DISPLAY_LIMIT records exist.
	total_matching = frappe.db.count("Sales Order", filters=query_filters)
	total_value = frappe.db.sql(
		"""
		SELECT SUM(grand_total) FROM `tabSales Order` WHERE {where}
		""".format(where=_build_where_clause(filters)[0]),
		_build_where_clause(filters)[1],
	)[0][0] or 0

	summary = {
		"count_shown": len(records),
		"total_matching": total_matching,
		"sum_grand_total_shown": sum(row.get("grand_total") or 0 for row in records),
		"sum_grand_total_all_matching": total_value,
	}
	if total_matching > len(records):
		summary["note"] = (
			f"Showing {len(records)} of {total_matching} matching records "
			f"(most recent first). Totals above reflect ALL {total_matching} "
			f"matching records, not just the ones shown."
		)

	return {
		"doctype": "Sales Order",
		"applied_filters": filters,
		"summary": summary,
		"data": records,
	}