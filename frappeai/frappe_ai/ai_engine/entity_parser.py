from frappeai.frappe_ai.ai_engine.query_patterns import FINANCE_PATTERNS


def extract_filters(message):

    msg = message.lower()

    result = {
        "doctype": None,
        "filters": {}
    }

    # Match finance patterns
    for pattern_name, pattern_data in FINANCE_PATTERNS.items():

        for keyword in pattern_data["keywords"]:

            if keyword in msg:

                result["doctype"] = pattern_data["doctype"]

                result["filters"].update(
                    pattern_data["filters"]
                )

                return result

    return result