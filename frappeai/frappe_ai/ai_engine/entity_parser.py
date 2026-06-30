"""
Entity / Filter Extractor
--------------------------
Scans a user message for known keyword patterns and resolves them into a
target Doctype + Frappe filter dict that query handlers can run directly
via frappe.get_all / frappe.get_list.

Intent-aware: pass the detected intent (from intent_parser.detect_intent)
to use the matching pattern set. Falls back to FINANCE_PATTERNS if no
intent is given, for backward compatibility.

NOTE: SALES_PATTERNS / INVENTORY_PATTERNS / HR_PATTERNS may not be defined
yet in query_patterns.py (only FINANCE_PATTERNS exists today). This module
is written to degrade gracefully -- missing pattern sets are treated as
empty dicts instead of raising ImportError, so the app keeps working while
those are filled in incrementally.
"""

from frappeai.frappe_ai.ai_engine import query_patterns

FINANCE_PATTERNS = getattr(query_patterns, "FINANCE_PATTERNS", {})
SALES_PATTERNS = getattr(query_patterns, "SALES_PATTERNS", {})
INVENTORY_PATTERNS = getattr(query_patterns, "INVENTORY_PATTERNS", {})
HR_PATTERNS = getattr(query_patterns, "HR_PATTERNS", {})

PATTERNS_BY_INTENT = {
	"finance": FINANCE_PATTERNS,
	"sales": SALES_PATTERNS,
	"inventory": INVENTORY_PATTERNS,
	"hr": HR_PATTERNS,
}


def extract_filters(message: str, intent: str | None = None) -> dict:
	"""
	Extract a doctype + filters dict from a user message.

	Args:
		message: Raw user message.
		intent: Optional intent string ("finance", "sales", "inventory", "hr").
		        If omitted, defaults to finance patterns for backward
		        compatibility with existing call sites.

	Returns:
		{"doctype": str | None, "filters": dict}
		doctype is None and filters is {} if nothing matched (including
		when the relevant pattern set hasn't been defined yet).
	"""
	result = {"doctype": None, "filters": {}}

	if not message:
		return result

	msg = message.lower()
	patterns = PATTERNS_BY_INTENT.get(intent, FINANCE_PATTERNS)

	for pattern_data in patterns.values():
		for keyword in pattern_data["keywords"]:
			if keyword in msg:
				result["doctype"] = pattern_data["doctype"]
				result["filters"].update(pattern_data["filters"])
				return result

	return result