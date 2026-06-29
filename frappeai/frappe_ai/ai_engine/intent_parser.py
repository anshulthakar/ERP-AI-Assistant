def detect_intent(message):

    msg = message.lower()

    # Finance
    if (
        "outstanding" in msg
        or "overdue" in msg
        or "invoice" in msg
        or "payment" in msg
        or "receivable" in msg
    ):
        return "finance"

    # Sales
    elif (
        "sales" in msg
        or "customer" in msg
        or "revenue" in msg
        or "order" in msg
    ):
        return "sales"

    # Inventory
    elif (
        "stock" in msg
        or "inventory" in msg
        or "item" in msg
        or "warehouse" in msg
    ):
        return "inventory"

    # HR
    elif (
        "employee" in msg
        or "leave" in msg
        or "salary" in msg
        or "attendance" in msg
    ):
        return "hr"

    return "general"