# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import re

import frappe
from frappe.model.document import Document
from frappe.utils import cstr, now


class AIMessageTemplate(Document):
    def before_insert(self):
        """Set default values before inserting."""
        if not self.created_by:
            self.created_by = frappe.session.user
        if not self.language:
            self.language = "en"
        if not self.priority:
            self.priority = 1

    def validate(self):
        """Validate template data."""
        self.validate_template_content()
        self.validate_keywords()
        self.validate_conditions()

    def validate_template_content(self):
        """Validate template content and variables."""
        if not self.template_content:
            frappe.throw("Template content is required")

        # Check for valid variable syntax
        variables = re.findall(r"\{\{(\w+)\}\}", self.template_content)
        if variables and not self.variables:
            frappe.msgprint(
                f"Template contains variables {variables} but no variable definitions provided"
            )

    def validate_keywords(self):
        """Validate trigger keywords."""
        if self.trigger_keywords:
            keywords = [k.strip() for k in self.trigger_keywords.split(",")]
            if len(keywords) > 50:
                frappe.throw("Maximum 50 trigger keywords allowed")

    def validate_conditions(self):
        """Validate template conditions."""
        if self.conditions:
            try:
                conditions = (
                    json.loads(self.conditions)
                    if isinstance(self.conditions, str)
                    else self.conditions
                )
                if not isinstance(conditions, dict):
                    frappe.throw("Conditions must be a valid JSON object")
            except json.JSONDecodeError:
                frappe.throw("Invalid JSON format in conditions")

    def matches_intent(self, intent, confidence=None):
        """Check if template matches the given intent."""
        if not self.is_active:
            return False

        if self.intent_patterns:
            patterns = [
                p.strip() for p in self.intent_patterns.split("\n") if p.strip()
            ]
            for pattern in patterns:
                if re.search(pattern, intent, re.IGNORECASE):
                    return True

        return False

    def matches_keywords(self, message_content):
        """Check if template matches keywords in message."""
        if not self.is_active or not self.trigger_keywords:
            return False

        keywords = [k.strip().lower() for k in self.trigger_keywords.split(",")]
        message_lower = message_content.lower()

        for keyword in keywords:
            if keyword in message_lower:
                return True

        return False

    def matches_conditions(self, context_data):
        """Check if template matches the given conditions."""
        if not self.conditions:
            return True

        try:
            conditions = (
                json.loads(self.conditions)
                if isinstance(self.conditions, str)
                else self.conditions
            )

            for key, expected_value in conditions.items():
                actual_value = context_data.get(key)

                if isinstance(expected_value, dict):
                    # Handle operators like {"$gt": 100}, {"$in": ["value1", "value2"]}
                    for operator, value in expected_value.items():
                        if operator == "$gt" and actual_value <= value:
                            return False
                        elif operator == "$lt" and actual_value >= value:
                            return False
                        elif operator == "$in" and actual_value not in value:
                            return False
                        elif operator == "$nin" and actual_value in value:
                            return False
                        elif operator == "$eq" and actual_value != value:
                            return False
                        elif operator == "$ne" and actual_value == value:
                            return False
                else:
                    # Direct value comparison
                    if actual_value != expected_value:
                        return False

            return True

        except Exception as e:
            frappe.log_error(
                f"Template condition evaluation error: {str(e)}", "AI Message Template"
            )
            return False

    def render_template(self, context_data=None):
        """Render template with provided context data."""
        if not context_data:
            context_data = {}

        content = self.template_content

        # Get available variables
        variables = json.loads(self.variables) if self.variables else {}

        # Merge context data with template variables
        render_context = {**variables, **context_data}

        # Replace variables in template
        for key, value in render_context.items():
            placeholder = f"{{{{{key}}}}}"
            content = content.replace(placeholder, cstr(value))

        # Update usage statistics
        self.update_usage_stats()

        return content

    def update_usage_stats(self):
        """Update template usage statistics."""
        frappe.db.set_value(
            "AI Message Template",
            self.name,
            {"usage_count": (self.usage_count or 0) + 1, "last_used": now()},
        )

    def update_feedback(self, rating, success=True):
        """Update template feedback and success rate."""
        current_usage = self.usage_count or 0
        current_feedback = self.feedback_score or 0
        current_success_rate = self.success_rate or 0

        # Update feedback score (weighted average)
        if current_usage > 0:
            new_feedback = ((current_feedback * current_usage) + rating) / (
                current_usage + 1
            )
        else:
            new_feedback = rating

        # Update success rate
        if current_usage > 0:
            success_count = (current_success_rate / 100) * current_usage
            if success:
                success_count += 1
            new_success_rate = (success_count / (current_usage + 1)) * 100
        else:
            new_success_rate = 100 if success else 0

        frappe.db.set_value(
            "AI Message Template",
            self.name,
            {"feedback_score": new_feedback, "success_rate": new_success_rate},
        )

    def get_template_variables(self):
        """Get list of available template variables."""
        variables = json.loads(self.variables) if self.variables else {}

        # Add common system variables
        system_variables = {
            "user_name": "Current user's name",
            "user_email": "Current user's email",
            "current_date": "Current date",
            "current_time": "Current time",
            "institution_name": "Institution name",
        }

        return {**system_variables, **variables}


@frappe.whitelist()
def get_matching_templates(
    message_content, intent=None, user_type=None, context_data=None
):
    """Get templates that match the given criteria."""
    if context_data and isinstance(context_data, str):
        context_data = json.loads(context_data)

    filters = {"is_active": 1}
    if user_type and user_type != "All":
        filters["user_type"] = ["in", [user_type, "All"]]

    templates = frappe.get_all(
        "AI Message Template",
        filters=filters,
        fields=["name", "template_name", "template_type", "priority", "category"],
        order_by="priority desc, usage_count desc",
    )

    matching_templates = []

    for template_data in templates:
        template = frappe.get_doc("AI Message Template", template_data.name)

        # Check keyword match
        keyword_match = template.matches_keywords(message_content)

        # Check intent match
        intent_match = template.matches_intent(intent) if intent else False

        # Check conditions
        condition_match = template.matches_conditions(context_data or {})

        if (keyword_match or intent_match) and condition_match:
            matching_templates.append(
                {
                    "name": template.name,
                    "template_name": template.template_name,
                    "template_type": template.template_type,
                    "category": template.category,
                    "priority": template.priority,
                    "match_type": "keyword" if keyword_match else "intent",
                }
            )

    return matching_templates


@frappe.whitelist()
def render_template(template_name, context_data=None):
    """Render a specific template with context data."""
    if context_data and isinstance(context_data, str):
        context_data = json.loads(context_data)

    template = frappe.get_doc("AI Message Template", template_name)
    return template.render_template(context_data)


@frappe.whitelist()
def create_default_templates():
    """Create default message templates."""
    default_templates = [
        {
            "template_name": "Welcome Message",
            "template_type": "Welcome",
            "category": "General Inquiry",
            "template_content": "Hello {{user_name}}! Welcome to {{institution_name}}. How can I help you today?",
            "trigger_keywords": "hello, hi, welcome, start",
            "user_type": "All",
            "variables": json.dumps(
                {
                    "user_name": "User's display name",
                    "institution_name": "Institution name",
                }
            ),
        },
        {
            "template_name": "Fees Inquiry Response",
            "template_type": "Auto Response",
            "category": "Fees",
            "template_content": "For fees information, please check your student portal or contact the accounts department at accounts@institution.edu. Current fee structure is available at {{fees_link}}.",
            "trigger_keywords": "fees, payment, cost, tuition, charges",
            "user_type": "Student",
            "variables": json.dumps({"fees_link": "Link to fees information"}),
        },
        {
            "template_name": "Course Schedule Response",
            "template_type": "Auto Response",
            "category": "Schedule",
            "template_content": "Your course schedule is available in the student portal. For specific timing queries, please check the academic calendar or contact your course coordinator.",
            "trigger_keywords": "schedule, timetable, timing, class, course time",
            "user_type": "Student",
        },
        {
            "template_name": "Technical Support Escalation",
            "template_type": "Escalation",
            "category": "Technical Support",
            "template_content": "I'm transferring your technical issue to our IT support team. They will contact you within 24 hours. Reference ID: {{ticket_id}}",
            "trigger_keywords": "technical, IT, system, login, password, error",
            "user_type": "All",
            "variables": json.dumps({"ticket_id": "Support ticket reference ID"}),
        },
        {
            "template_name": "Admission Inquiry Response",
            "template_type": "Auto Response",
            "category": "Admission",
            "template_content": "Thank you for your interest in {{institution_name}}! Admission information is available at {{admission_link}}. Application deadline is {{deadline}}. For specific queries, contact admissions@institution.edu.",
            "trigger_keywords": "admission, apply, application, enrollment, join",
            "user_type": "All",
            "variables": json.dumps(
                {
                    "institution_name": "Institution name",
                    "admission_link": "Admission information link",
                    "deadline": "Application deadline",
                }
            ),
        },
    ]

    created_templates = []

    for template_data in default_templates:
        # Check if template already exists
        if not frappe.db.exists("AI Message Template", template_data["template_name"]):
            template = frappe.get_doc(
                {"doctype": "AI Message Template", **template_data}
            )
            template.insert()
            created_templates.append(template.name)

    return {
        "success": True,
        "created_templates": created_templates,
        "message": f"Created {len(created_templates)} default templates",
    }
