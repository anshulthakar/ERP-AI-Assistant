frappe.pages['ai-chat'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'SmartOps AI Assistant',
		single_column: true
	});
}