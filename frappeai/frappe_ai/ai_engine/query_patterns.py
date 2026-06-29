FINANCE_PATTERNS = {

    "paid_invoices": {
        "keywords": [
            "paid invoice",
            "completed invoice",
            "paid sales invoice"
        ],
        "doctype": "Sales Invoice",
        "filters": {
            "status": "Paid"
        }
    },

    "overdue_invoices": {
        "keywords": [
            "overdue invoice",
            "late invoice",
            "pending invoice"
        ],
        "doctype": "Sales Invoice",
        "filters": {
            "status": "Overdue"
        }
    },

    "unpaid_invoices": {
        "keywords": [
            "unpaid invoice",
            "outstanding invoice"
        ],
        "doctype": "Sales Invoice",
        "filters": {
            "status": "Unpaid"
        }
    }

}