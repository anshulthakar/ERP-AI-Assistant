"""
Context Formatter
------------------
Converts raw context data returned by query handlers (dict, list of dicts,
or plain string) into a clean, readable plain-text block that can be
injected into the LLM prompt or shown directly to the user.
"""

MAX_ROWS_SHOWN = 5


def format_context(context_data) -> str:
	"""
	Format context data into a human-readable string.

	Args:
		context_data: dict, list, str, or falsy value returned by a
		              query handler in query_builder.py.

	Returns:
		A plain-text representation, never None.
	"""
	if not context_data:
		return "No ERP data found."

	if isinstance(context_data, str):
		return context_data

	if isinstance(context_data, dict):
		return _format_dict(context_data)

	if isinstance(context_data, list):
		return _format_list(context_data)

	# Fallback for any other type (int, float, etc.)
	return str(context_data)


def _format_dict(data: dict) -> str:
	lines = [f"{key}: {_format_value(value)}" for key, value in data.items()]
	return "\n".join(lines)


def _format_list(rows: list) -> str:
	if not rows:
		return "No ERP data found."

	lines = []
	shown_rows = rows[:MAX_ROWS_SHOWN]

	for row in shown_rows:
		if isinstance(row, dict):
			row_text = ", ".join(f"{k}: {_format_value(v)}" for k, v in row.items())
			lines.append(f"- {row_text}")
		else:
			lines.append(f"- {row}")

	remaining = len(rows) - len(shown_rows)
	if remaining > 0:
		lines.append(f"... and {remaining} more record(s) not shown")

	return "\n".join(lines)


def _format_value(value) -> str:
	"""Recursively stringify nested dicts/lists instead of dumping raw repr."""
	if isinstance(value, dict):
		return "{" + ", ".join(f"{k}: {_format_value(v)}" for k, v in value.items()) + "}"
	if isinstance(value, list):
		return "[" + ", ".join(_format_value(v) for v in value) + "]"
	return str(value)