import frappe

def get_context(context):
	"""Get context for AI chat page."""
	context.no_cache = 1
	
	# Check if user is logged in
	if frappe.session.user == "Guest":
		frappe.throw("Please login to access AI Chat", frappe.PermissionError)
	
	# Get AI configuration
	try:
		ai_config = frappe.get_single("AI Configuration")
		context.ai_enabled = ai_config.enable_ai_processing
		context.auto_responses = ai_config.enable_auto_responses
	except:
		context.ai_enabled = False
		context.auto_responses = False
	
	# Get user information
	user = frappe.get_doc("User", frappe.session.user)
	context.user_name = user.full_name or user.name
	context.user_email = user.email
	
	# Determine user type
	context.user_type = get_user_type(frappe.session.user)
	
	return context

def get_user_type(user):
	"""Determine user type based on roles and linked documents."""
	if user == "Administrator":
		return "Admin"
	
	# Check if user is a student
	student = frappe.db.get_value("Student", {"user": user}, "name")
	if student:
		return "Student"
	
	# Check if user is an instructor
	instructor = frappe.db.get_value("Instructor", {"user": user}, "name")
	if instructor:
		return "Instructor"
	
	# Check if user is a guardian
	guardian = frappe.db.get_value("Guardian", {"user": user}, "name")
	if guardian:
		return "Guardian"
	
	# Default to Admin for other users
	return "Admin"

