import frappe


def get_sales_data(message):

    orders = frappe.get_all(
        "Sales Order",
        filters={
            "docstatus": 1
        },
        fields=[
            "name",
            "customer",
            "grand_total",
            "transaction_date"
        ],
        order_by="creation desc",
        limit=10
    )

    return {
        "recent_sales_orders": orders
    }