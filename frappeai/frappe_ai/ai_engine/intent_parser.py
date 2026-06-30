"""
Intent Parser
-------------
Classifies a raw user message into one of the supported ERP domains:
finance, sales, inventory, hr — or "general" if nothing matches.

Uses whole-word matching (not naive substring matching) to avoid false
positives like "order" matching inside "border", or "so-" matching
inside an unrelated word.
"""

import re

# Sales Order queries are treated as finance intent because they involve
# status / due / delivery / billing style analytics handled by the
# finance query handler.
SALES_ORDER_AS_FINANCE_KEYWORDS = [
	"sales order",
	"sales orders",
	"pending sales order",
	"pending sales orders",
	"awaiting delivery",
	"awaiting billing",
	"overdue sales order",
	"overdue sales orders",
]

FINANCE_KEYWORDS = ["outstanding", "overdue", "invoice", "payment", "receivable"]
SALES_KEYWORDS = ["sales", "customer", "revenue", "order"]
INVENTORY_KEYWORDS = ["stock", "inventory", "item", "warehouse"]
HR_KEYWORDS = ["employee", "leave", "salary", "attendance"]


def _contains_any(msg: str, keywords: list[str]) -> bool:
	"""
	Check if any keyword appears in msg as a whole word/phrase
	(word-boundary match), not as a loose substring.
	"""
	for keyword in keywords:
		pattern = r"\b" + re.escape(keyword) + r"\b"
		if re.search(pattern, msg):
			return True
	return False


def detect_intent(message: str) -> str:
	"""
	Classify a user message into an intent string.

	Args:
		message: Raw user message.

	Returns:
		One of "finance", "sales", "inventory", "hr", or "general".
	"""
	if not message:
		return "general"

	msg = message.lower()

	# Sales Order phrasing also matches the "so-" style document name prefix
	# (e.g. "SO-00123"), checked separately since it's not a clean word boundary.
	if _contains_any(msg, SALES_ORDER_AS_FINANCE_KEYWORDS) or "so-" in msg:
		return "finance"

	if _contains_any(msg, FINANCE_KEYWORDS):
		return "finance"

	if _contains_any(msg, SALES_KEYWORDS):
		return "sales"

	if _contains_any(msg, INVENTORY_KEYWORDS):
		return "inventory"

	if _contains_any(msg, HR_KEYWORDS):
		return "hr"

	return "general"