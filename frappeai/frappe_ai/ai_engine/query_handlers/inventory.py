import frappe


def get_inventory_data(message):

    items = frappe.get_all(
        "Bin",
        fields=[
            "item_code",
            "warehouse",
            "actual_qty"
        ],
        order_by="actual_qty asc",
        limit=10
    )

    return {
        "stock_data": items
    }