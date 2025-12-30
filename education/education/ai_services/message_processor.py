# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe

from education.education.ai_services.base_ai_service import get_ai_service
from education.education.doctype.ai_configuration.ai_configuration import \
    get_current_config


class MessageProcessor:
    """Main class for processing AI messages."""

    def __init__(self):
        self.ai_config = get_current_config()
        self.ai_service = get_ai_service()

    def process_message(self, message_doc):
        """Process a message with AI and return response."""
        try:
            # Check if AI processing is enabled
            if not self.ai_config.enable_ai_processing:
                return {"success": False, "error": "AI processing is disabled"}

            # Get context data for the message
            context_data = self.build_context(message_doc)

            # Classify intent
            intent_result = self.ai_service.classify_intent(message_doc.message_content)
            intent = intent_result.get("intent", "general_inquiry")
            confidence = intent_result.get("confidence", 0.5)

            # Analyze sentiment
            sentiment_result = self.ai_service.analyze_sentiment(
                message_doc.message_content
            )

            # Check if we should auto-respond
            should_respond = self.ai_config.should_auto_respond(confidence)
            should_escalate = self.ai_config.should_escalate(confidence)

            response = None

            if should_respond:
                # Try to find matching template first
                template_response = self.get_template_response(
                    message_doc.message_content,
                    intent,
                    message_doc.sender_type,
                    context_data,
                )

                if template_response:
                    response = template_response
                else:
                    # Generate AI response
                    ai_response = self.generate_ai_response(
                        message_doc.message_content,
                        intent,
                        message_doc.sender_type,
                        context_data,
                    )
                    response = (
                        ai_response.get("response")
                        if ai_response.get("success")
                        else None
                    )

            # Update message metadata
            metadata = {
                "intent_classification": intent_result,
                "sentiment_analysis": sentiment_result,
                "context_data": context_data,
                "processing_timestamp": frappe.utils.now(),
                "should_escalate": should_escalate,
            }

            return {
                "success": True,
                "response": response,
                "intent": intent,
                "confidence": confidence,
                "sentiment": sentiment_result.get("sentiment"),
                "should_escalate": should_escalate,
                "metadata": metadata,
            }

        except Exception as e:
            frappe.log_error(
                f"Message processing error: {str(e)}", "AI Message Processor"
            )
            return {"success": False, "error": str(e)}

    def build_context(self, message_doc):
        """Build context data for AI processing."""
        context = {}

        try:
            # Get sender information
            if message_doc.sender_type == "Student":
                student = frappe.get_doc("Student", message_doc.sender)
                context.update(
                    {
                        "sender_name": student.student_name,
                        "sender_email": student.student_email_id,
                        "program": getattr(student, "program", None),
                        "student_batch": getattr(student, "student_batch_name", None),
                    }
                )

                # Get enrollment information
                enrollments = frappe.get_all(
                    "Program Enrollment",
                    filters={"student": message_doc.sender, "docstatus": 1},
                    fields=["program", "academic_year", "enrollment_date"],
                    limit=1,
                )
                if enrollments:
                    context["current_program"] = enrollments[0].program
                    context["academic_year"] = enrollments[0].academic_year

            elif message_doc.sender_type == "Instructor":
                instructor = frappe.get_doc("Instructor", message_doc.sender)
                context.update(
                    {
                        "sender_name": instructor.instructor_name,
                        "sender_email": instructor.email,
                        "department": getattr(instructor, "department", None),
                    }
                )

            elif message_doc.sender_type == "Guardian":
                guardian = frappe.get_doc("Guardian", message_doc.sender)
                context.update(
                    {
                        "sender_name": guardian.guardian_name,
                        "sender_email": guardian.email_address,
                    }
                )

                # Get ward information
                wards = frappe.get_all(
                    "Student Guardian",
                    filters={"guardian": message_doc.sender},
                    fields=["student"],
                    limit=5,
                )
                if wards:
                    context["wards"] = [ward.student for ward in wards]

            # Add current time context
            context.update(
                {
                    "current_date": frappe.utils.today(),
                    "current_time": frappe.utils.now(),
                    "current_academic_year": frappe.defaults.get_defaults().get(
                        "academic_year"
                    ),
                    "institution_name": frappe.defaults.get_defaults().get("company")
                    or "Institution",
                }
            )

            # Add message-specific context
            if message_doc.conversation:
                conversation = frappe.get_doc(
                    "AI Conversation", message_doc.conversation
                )
                context["conversation_type"] = conversation.conversation_type
                context["conversation_status"] = conversation.status

        except Exception as e:
            frappe.log_error(
                f"Context building error: {str(e)}", "AI Message Processor"
            )

        return context

    def get_template_response(self, message_content, intent, user_type, context_data):
        """Get response from matching template."""
        try:
            from education.education.doctype.ai_message_template.ai_message_template import \
                get_matching_templates

            templates = get_matching_templates(
                message_content, intent, user_type, context_data
            )

            if templates:
                # Use the highest priority template
                template_name = templates[0]["name"]
                template_doc = frappe.get_doc("AI Message Template", template_name)

                # Render template with context
                response = template_doc.render_template(context_data)

                return response

        except Exception as e:
            frappe.log_error(
                f"Template response error: {str(e)}", "AI Message Processor"
            )

        return None

    def generate_ai_response(self, message_content, intent, user_type, context_data):
        """Generate AI response using the AI service."""
        try:
            # Get appropriate system prompt
            system_prompt = self.ai_config.get_system_prompt(user_type)

            # Enhance system prompt with intent and context
            enhanced_prompt = f"""
			{system_prompt}

			Current context:
			- User type: {user_type}
			- Detected intent: {intent}
			- Institution: {context_data.get('institution_name', 'Institution')}

			Please provide a helpful, professional response to the user's message.
			Keep responses concise and actionable.
			"""

            # Generate response
            result = self.ai_service.generate_response(
                message_content, enhanced_prompt, context_data
            )

            return result

        except Exception as e:
            frappe.log_error(
                f"AI response generation error: {str(e)}", "AI Message Processor"
            )
            return {"success": False, "error": str(e)}

    def generate_conversation_summary(self, messages):
        """Generate AI summary of conversation."""
        try:
            if not messages:
                return None

            # Prepare conversation text
            conversation_text = []
            for msg in messages:
                content = msg.get("message_content", "")
                if msg.get("ai_response"):
                    content += f"\nAI Response: {msg.get('ai_response')}"
                conversation_text.append(content)

            full_conversation = "\n\n".join(conversation_text)

            # Generate summary
            system_prompt = """
			Please provide a concise summary of this conversation between a user and an AI assistant.
			Focus on:
			1. Main topics discussed
			2. Key issues or questions raised
			3. Actions taken or recommended
			4. Current status/resolution

			Keep the summary under 200 words.
			"""

            result = self.ai_service.generate_response(full_conversation, system_prompt)

            if result.get("success"):
                return result.get("response")

        except Exception as e:
            frappe.log_error(
                f"Conversation summary error: {str(e)}", "AI Message Processor"
            )

        return None

    def analyze_conversation_patterns(self, conversation_name):
        """Analyze patterns in a conversation."""
        try:
            messages = frappe.get_all(
                "AI Message",
                filters={"conversation": conversation_name},
                fields=[
                    "message_content",
                    "intent",
                    "sentiment",
                    "feedback_rating",
                    "creation",
                ],
                order_by="creation asc",
            )

            if not messages:
                return {}

            # Analyze patterns
            intents = [msg.get("intent") for msg in messages if msg.get("intent")]
            sentiments = [
                msg.get("sentiment") for msg in messages if msg.get("sentiment")
            ]
            ratings = [
                msg.get("feedback_rating")
                for msg in messages
                if msg.get("feedback_rating")
            ]

            analysis = {
                "message_count": len(messages),
                "unique_intents": list(set(intents)),
                "dominant_intent": (
                    max(set(intents), key=intents.count) if intents else None
                ),
                "sentiment_distribution": {
                    "positive": sentiments.count("positive"),
                    "negative": sentiments.count("negative"),
                    "neutral": sentiments.count("neutral"),
                },
                "average_rating": sum(ratings) / len(ratings) if ratings else None,
                "conversation_duration": None,
            }

            # Calculate conversation duration
            if len(messages) > 1:
                start_time = frappe.utils.get_datetime(messages[0]["creation"])
                end_time = frappe.utils.get_datetime(messages[-1]["creation"])
                duration = end_time - start_time
                analysis["conversation_duration"] = (
                    duration.total_seconds() / 3600
                )  # hours

            return analysis

        except Exception as e:
            frappe.log_error(
                f"Conversation analysis error: {str(e)}", "AI Message Processor"
            )
            return {}


@frappe.whitelist()
def process_message_manually(message_name):
    """Manually process a message with AI."""
    message = frappe.get_doc("AI Message", message_name)
    processor = MessageProcessor()
    result = processor.process_message(message)

    if result.get("success"):
        # Update message with AI response
        message.ai_response = result.get("response")
        message.intent = result.get("intent")
        message.confidence_score = result.get("confidence")
        message.status = "Processed"

        if result.get("should_escalate"):
            message.escalate_to_human()
        else:
            message.save()

            # Create AI response message if response was generated
            if result.get("response"):
                message.create_ai_response()

    return result


@frappe.whitelist()
def get_conversation_analytics(conversation_name):
    """Get analytics for a conversation."""
    processor = MessageProcessor()
    return processor.analyze_conversation_patterns(conversation_name)
