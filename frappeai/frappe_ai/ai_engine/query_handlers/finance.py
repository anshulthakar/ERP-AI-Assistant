import frappe

from frappeai.frappe_ai.ai_engine.entity_parser import extract_filters


def get_finance_data(message):

    parsed = extract_filters(message)

    doctype = parsed.get("doctype") or "Sales Invoice"

    filters = {
        "docstatus": 1
    }

    filters.update(parsed.get("filters", {}))

    invoices = frappe.get_all(
        doctype,
        filters=filters,
        fields=[
            "name",
            "customer",
            "status",
            "posting_date",
            "due_date",
            "grand_total",
            "outstanding_amount"
        ],
        order_by="posting_date desc",
        limit=5
    )

    return {
        "doctype": doctype,
        "filters": filters,
        "data": invoices
    }