from frappeai.frappe_ai.ai_engine.query_handlers.finance import get_finance_data
from frappeai.frappe_ai.ai_engine.query_handlers.sales import get_sales_data
from frappeai.frappe_ai.ai_engine.query_handlers.inventory import get_inventory_data
from frappeai.frappe_ai.ai_engine.query_handlers.hr import get_hr_data


def get_context_data(intent, message):

    if intent == "finance":
        return get_finance_data(message)

    elif intent == "sales":
        return get_sales_data(message)

    elif intent == "inventory":
        return get_inventory_data(message)

    elif intent == "hr":
        return get_hr_data(message)

    return {}