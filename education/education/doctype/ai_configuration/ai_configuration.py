# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document
from frappe.utils import get_time, now_datetime


class AIConfiguration(Document):
    def validate(self):
        """Validate configuration settings."""
        self.validate_ai_settings()
        self.validate_business_hours()
        self.validate_thresholds()

    def validate_ai_settings(self):
        """Validate AI provider settings."""
        if self.enable_ai_processing:
            if not self.ai_provider:
                frappe.throw("AI Provider is required when AI Processing is enabled")

            if (
                self.ai_provider in ["OpenAI", "Anthropic", "Google"]
                and not self.api_key
            ):
                frappe.throw(f"API Key is required for {self.ai_provider}")

            if not self.model_name:
                frappe.throw("Model Name is required")

            if self.max_tokens and self.max_tokens <= 0:
                frappe.throw("Max Tokens must be greater than 0")

            if self.timeout_seconds and self.timeout_seconds <= 0:
                frappe.throw("Timeout must be greater than 0")

    def validate_business_hours(self):
        """Validate business hours settings."""
        if self.business_hours_only:
            if not self.business_hours_start or not self.business_hours_end:
                frappe.throw("Business hours start and end times are required")

            start_time = get_time(self.business_hours_start)
            end_time = get_time(self.business_hours_end)

            if start_time >= end_time:
                frappe.throw("Business hours start time must be before end time")

    def validate_thresholds(self):
        """Validate threshold values."""
        if self.auto_response_confidence_threshold:
            if not (0 <= self.auto_response_confidence_threshold <= 1):
                frappe.throw(
                    "Auto Response Confidence Threshold must be between 0 and 1"
                )

        if self.escalation_threshold:
            if not (0 <= self.escalation_threshold <= 1):
                frappe.throw("Escalation Threshold must be between 0 and 1")

        if self.temperature:
            if not (0 <= self.temperature <= 2):
                frappe.throw("Temperature must be between 0 and 2")

    def is_business_hours(self):
        """Check if current time is within business hours."""
        if not self.business_hours_only:
            return True

        current_time = now_datetime().time()
        start_time = get_time(self.business_hours_start)
        end_time = get_time(self.business_hours_end)

        return start_time <= current_time <= end_time

    def is_weekend_response_enabled(self):
        """Check if weekend responses are enabled."""
        if not self.weekend_responses:
            current_weekday = now_datetime().weekday()
            # Monday = 0, Sunday = 6
            return current_weekday < 5  # Monday to Friday
        return True

    def should_auto_respond(self, confidence_score=None):
        """Determine if message should get auto response."""
        if not self.enable_auto_responses:
            return False

        if not self.is_business_hours():
            return False

        if not self.is_weekend_response_enabled():
            return False

        if confidence_score and self.auto_response_confidence_threshold:
            return confidence_score >= self.auto_response_confidence_threshold

        return True

    def should_escalate(self, confidence_score=None):
        """Determine if message should be escalated."""
        if not self.enable_escalation:
            return False

        if confidence_score and self.escalation_threshold:
            return confidence_score < self.escalation_threshold

        return False

    def get_system_prompt(self, user_type="default"):
        """Get appropriate system prompt based on user type."""
        prompt_field = f"{user_type.lower()}_system_prompt"

        if hasattr(self, prompt_field) and getattr(self, prompt_field):
            return getattr(self, prompt_field)

        return self.default_system_prompt or "You are a helpful AI assistant."

    def get_ai_provider_config(self):
        """Get AI provider configuration."""
        config = {
            "provider": self.ai_provider,
            "model": self.model_name,
            "max_tokens": self.max_tokens or 1000,
            "temperature": self.temperature or 0.7,
            "timeout": self.timeout_seconds or 30,
        }

        if self.api_key:
            config["api_key"] = self.get_password("api_key")

        if self.api_endpoint:
            config["api_endpoint"] = self.api_endpoint

        return config

    def test_ai_connection(self):
        """Test connection to AI provider."""
        try:
            from education.education.ai_services.base_ai_service import \
                get_ai_service

            ai_service = get_ai_service(self.get_ai_provider_config())
            test_result = ai_service.test_connection()

            return {
                "success": True,
                "message": "Connection successful",
                "details": test_result,
            }

        except Exception as e:
            return {"success": False, "message": f"Connection failed: {str(e)}"}

    def get_notification_settings(self):
        """Get notification configuration."""
        return {
            "email_enabled": self.enable_email_notifications,
            "sms_enabled": self.enable_sms_notifications,
            "push_enabled": self.enable_push_notifications,
            "notification_template": self.notification_template,
            "escalation_template": self.escalation_email_template,
            "response_template": self.response_email_template,
        }

    def get_analytics_settings(self):
        """Get analytics configuration."""
        return {
            "conversation_analytics": self.enable_conversation_analytics,
            "sentiment_analysis": self.enable_sentiment_analysis,
            "intent_classification": self.enable_intent_classification,
            "feedback_collection": self.enable_feedback_collection,
        }

    def update_usage_stats(self, stat_type, value=1):
        """Update usage statistics."""
        try:
            metadata = json.loads(self.get("metadata") or "{}")
            usage_stats = metadata.get("usage_stats", {})

            current_date = now_datetime().date().isoformat()
            daily_stats = usage_stats.get(current_date, {})

            daily_stats[stat_type] = daily_stats.get(stat_type, 0) + value
            usage_stats[current_date] = daily_stats
            metadata["usage_stats"] = usage_stats

            # Keep only last 30 days of stats
            dates = sorted(usage_stats.keys())
            if len(dates) > 30:
                for old_date in dates[:-30]:
                    del usage_stats[old_date]

            frappe.db.set_value(
                "AI Configuration", self.name, "metadata", json.dumps(metadata)
            )

        except Exception as e:
            frappe.log_error(f"Usage stats update error: {str(e)}", "AI Configuration")


@frappe.whitelist()
def get_ai_config():
    """Get AI configuration for API use."""
    config = frappe.get_single("AI Configuration")

    return {
        "ai_enabled": config.enable_ai_processing,
        "auto_responses": config.enable_auto_responses,
        "business_hours_only": config.business_hours_only,
        "weekend_responses": config.weekend_responses,
        "feedback_enabled": config.enable_feedback_collection,
        "escalation_enabled": config.enable_escalation,
    }


@frappe.whitelist()
def test_ai_connection():
    """Test AI provider connection."""
    config = frappe.get_single("AI Configuration")
    return config.test_ai_connection()


@frappe.whitelist()
def update_ai_settings(settings):
    """Update AI configuration settings."""
    config = frappe.get_single("AI Configuration")

    for key, value in settings.items():
        if hasattr(config, key):
            setattr(config, key, value)

    config.save()
    return {"success": True}


def get_current_config():
    """Get current AI configuration instance."""
    return frappe.get_single("AI Configuration")
