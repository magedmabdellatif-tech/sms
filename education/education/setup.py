# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def setup_ai_messaging():
    """Setup AI messaging system with default configuration and templates."""

    # Create AI Configuration if it doesn't exist
    if not frappe.db.exists("AI Configuration", "AI Configuration"):
        ai_config = frappe.get_doc(
            {
                "doctype": "AI Configuration",
                "enable_ai_processing": 1,
                "ai_provider": "Mock",  # Start with mock service
                "model_name": "mock-model",
                "enable_auto_responses": 1,
                "auto_response_confidence_threshold": 0.8,
                "enable_escalation": 1,
                "escalation_threshold": 0.5,
                "enable_email_notifications": 1,
                "enable_push_notifications": 1,
                "enable_conversation_analytics": 1,
                "enable_sentiment_analysis": 1,
                "enable_intent_classification": 1,
                "max_conversation_length": 100,
                "conversation_timeout_hours": 24,
                "enable_feedback_collection": 1,
                "default_system_prompt": "You are an AI assistant for an educational institution. Help users with their questions about courses, enrollment, fees, and general inquiries. Be helpful, professional, and concise.",
                "student_system_prompt": "You are an AI assistant helping students. Provide information about courses, schedules, assignments, fees, and academic support. Be encouraging and supportive.",
                "instructor_system_prompt": "You are an AI assistant helping instructors. Provide information about course management, student progress, administrative tasks, and teaching resources.",
                "admin_system_prompt": "You are an AI assistant helping administrators. Provide information about system management, reports, user management, and institutional operations.",
            }
        )
        ai_config.insert()
        frappe.db.commit()
        print("✅ AI Configuration created")

    # Create default message templates
    try:
        from education.education.doctype.ai_message_template.ai_message_template import (
            create_default_templates,
        )

        result = create_default_templates()
        if result.get("success"):
            print(
                f"✅ Created {len(result.get('created_templates', []))} default message templates"
            )
        else:
            print("ℹ️ Default templates already exist")
    except Exception as e:
        print(f"⚠️ Error creating default templates: {str(e)}")

    # Add custom fields to existing doctypes for AI integration
    setup_custom_fields()

    # Create default roles and permissions
    setup_roles_and_permissions()

    print("🚀 AI Messaging system setup completed!")


def setup_custom_fields():
    """Add custom fields to existing doctypes for AI integration."""

    custom_fields = {
        "Student": [
            {
                "fieldname": "ai_preferences",
                "label": "AI Preferences",
                "fieldtype": "Section Break",
                "insert_after": "student_email_id",
            },
            {
                "fieldname": "enable_ai_assistance",
                "label": "Enable AI Assistance",
                "fieldtype": "Check",
                "default": "1",
                "insert_after": "ai_preferences",
            },
            {
                "fieldname": "preferred_language",
                "label": "Preferred Language",
                "fieldtype": "Data",
                "default": "en",
                "insert_after": "enable_ai_assistance",
            },
        ],
        "Instructor": [
            {
                "fieldname": "ai_preferences",
                "label": "AI Preferences",
                "fieldtype": "Section Break",
                "insert_after": "email",
            },
            {
                "fieldname": "enable_ai_assistance",
                "label": "Enable AI Assistance",
                "fieldtype": "Check",
                "default": "1",
                "insert_after": "ai_preferences",
            },
            {
                "fieldname": "ai_notification_level",
                "label": "AI Notification Level",
                "fieldtype": "Select",
                "options": "All\nImportant Only\nNone",
                "default": "Important Only",
                "insert_after": "enable_ai_assistance",
            },
        ],
        "Guardian": [
            {
                "fieldname": "ai_preferences",
                "label": "AI Preferences",
                "fieldtype": "Section Break",
                "insert_after": "email_address",
            },
            {
                "fieldname": "enable_ai_assistance",
                "label": "Enable AI Assistance",
                "fieldtype": "Check",
                "default": "1",
                "insert_after": "ai_preferences",
            },
        ],
    }

    try:
        create_custom_fields(custom_fields, update=True)
        print("✅ Custom fields added for AI integration")
    except Exception as e:
        print(f"⚠️ Error adding custom fields: {str(e)}")


def setup_roles_and_permissions():
    """Setup roles and permissions for AI messaging system."""

    # Create AI Manager role if it doesn't exist
    if not frappe.db.exists("Role", "AI Manager"):
        ai_manager_role = frappe.get_doc(
            {"doctype": "Role", "role_name": "AI Manager", "desk_access": 1}
        )
        ai_manager_role.insert()
        print("✅ AI Manager role created")

    # Add AI Manager role to System Manager
    if not frappe.db.exists(
        "Has Role", {"parent": "Administrator", "role": "AI Manager"}
    ):
        frappe.get_doc(
            {
                "doctype": "Has Role",
                "parent": "Administrator",
                "parenttype": "User",
                "parentfield": "roles",
                "role": "AI Manager",
            }
        ).insert()

    print("✅ Roles and permissions configured")


def create_sample_data():
    """Create sample conversations and messages for demonstration."""

    # Only create sample data in development
    if frappe.conf.get("developer_mode"):
        try:
            # Create a sample conversation
            if not frappe.db.exists(
                "AI Conversation", {"title": "Sample Student Inquiry"}
            ):
                conversation = frappe.get_doc(
                    {
                        "doctype": "AI Conversation",
                        "title": "Sample Student Inquiry",
                        "conversation_type": "Inquiry",
                        "status": "Active",
                        "participants": '[{"type": "Student", "id": "Administrator", "name": "Sample Student"}]',
                    }
                )
                conversation.insert()

                # Create sample messages
                sample_message = frappe.get_doc(
                    {
                        "doctype": "AI Message",
                        "conversation": conversation.name,
                        "message_type": "Incoming",
                        "sender_type": "Student",
                        "sender": "Administrator",
                        "recipient_type": "AI",
                        "recipient": "AI Assistant",
                        "subject": "Fee Payment Inquiry",
                        "message_content": "Hi, I need help with my fee payment. When is the deadline?",
                        "status": "Processed",
                        "intent": "fees_inquiry",
                        "confidence_score": 0.9,
                    }
                )
                sample_message.insert()

                # Create AI response
                ai_response = frappe.get_doc(
                    {
                        "doctype": "AI Message",
                        "conversation": conversation.name,
                        "message_type": "Outgoing",
                        "sender_type": "AI",
                        "sender": "AI Assistant",
                        "recipient_type": "Student",
                        "recipient": "Administrator",
                        "subject": "Re: Fee Payment Inquiry",
                        "message_content": "Hello! The fee payment deadline for this semester is typically 30 days from the start of classes. You can check your exact deadline in the student portal under 'Fees' section. If you need an extension, please contact the accounts department.",
                        "status": "Processed",
                        "is_automated": 1,
                    }
                )
                ai_response.insert()

                print("✅ Sample conversation and messages created")

        except Exception as e:
            print(f"⚠️ Error creating sample data: {str(e)}")


if __name__ == "__main__":
    setup_ai_messaging()
    create_sample_data()
