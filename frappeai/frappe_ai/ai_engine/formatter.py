def format_context(context_data):

    if not context_data:
        return "No ERP data found."

    if isinstance(context_data, str):
        return context_data

    lines = []

    if isinstance(context_data, dict):

        for key, value in context_data.items():

            lines.append(f"{key}: {value}")

    elif isinstance(context_data, list):

        for row in context_data[:5]:

            lines.append(str(row))

    return "\n".join(lines)