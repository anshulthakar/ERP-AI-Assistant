import frappe


def get_hr_data(message):

    employees = frappe.get_all(
        "Employee",
        fields=[
            "employee_name",
            "department",
            "status"
        ],
        limit=10
    )

    return {
        "employees": employees
    }