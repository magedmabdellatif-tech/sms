# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now, time_diff_in_seconds
import json


class AIMessage(Document):
	def before_insert(self):
		"""Set default values before inserting the document."""
		if not self.status:
			self.status = "Draft"
		if not self.priority:
			self.priority = "Medium"
		
		# Set conversation if not provided
		if not self.conversation and self.sender and self.recipient:
			self.conversation = self.get_or_create_conversation()
	
	def before_save(self):
		"""Validate and process the message before saving."""
		self.validate_message()
		
		# Update processed timestamp when status changes to Processed
		if self.status == "Processed" and not self.processed_at:
			self.processed_at = now()
			
		# Calculate response time if this is an AI response
		if self.message_type == "Outgoing" and self.sender_type == "AI" and self.processed_at:
			original_message = self.get_original_message()
			if original_message:
				self.response_time = time_diff_in_seconds(self.processed_at, original_message.creation)
	
	def validate_message(self):
		"""Validate message data."""
		if not self.message_content:
			frappe.throw("Message content is required")
		
		# Validate sender and recipient types
		valid_types = ["Student", "Instructor", "Guardian", "Admin", "System", "AI"]
		if self.sender_type and self.sender_type not in valid_types:
			frappe.throw(f"Invalid sender type: {self.sender_type}")
		if self.recipient_type and self.recipient_type not in valid_types:
			frappe.throw(f"Invalid recipient type: {self.recipient_type}")
	
	def get_or_create_conversation(self):
		"""Get existing conversation or create a new one."""
		# Try to find existing conversation between sender and recipient
		existing_conversation = frappe.db.get_value(
			"AI Conversation",
			{
				"participants": ["like", f"%{self.sender}%"],
				"status": ["!=", "Closed"]
			},
			"name"
		)
		
		if existing_conversation:
			# Verify the recipient is also in this conversation
			conversation_doc = frappe.get_doc("AI Conversation", existing_conversation)
			participants = json.loads(conversation_doc.participants or "[]")
			participant_ids = [p.get("id") for p in participants]
			
			if self.recipient in participant_ids:
				return existing_conversation
		
		# Create new conversation
		conversation = frappe.get_doc({
			"doctype": "AI Conversation",
			"title": self.subject or f"Conversation between {self.sender} and {self.recipient}",
			"participants": json.dumps([
				{"type": self.sender_type, "id": self.sender},
				{"type": self.recipient_type, "id": self.recipient}
			]),
			"status": "Active"
		})
		conversation.insert()
		return conversation.name
	
	def get_original_message(self):
		"""Get the original message this is responding to."""
		if not self.conversation:
			return None
		
		# Find the most recent incoming message in this conversation
		original = frappe.db.get_value(
			"AI Message",
			{
				"conversation": self.conversation,
				"message_type": "Incoming",
				"creation": ["<", self.creation]
			},
			["name", "creation"],
			order_by="creation desc"
		)
		
		if original:
			return frappe.get_doc("AI Message", original[0])
		return None
	
	def process_with_ai(self):
		"""Process the message with AI and generate response."""
		try:
			self.status = "Processing"
			self.save()
			
			# Import AI service (will be created in next step)
			from education.education.ai_services.message_processor import MessageProcessor
			
			processor = MessageProcessor()
			result = processor.process_message(self)
			
			if result.get("success"):
				self.ai_response = result.get("response")
				self.intent = result.get("intent")
				self.confidence_score = result.get("confidence")
				self.status = "Processed"
				
				# Create response message if AI generated one
				if self.ai_response:
					self.create_ai_response()
			else:
				self.status = "Failed"
				self.requires_human_review = 1
			
			self.save()
			
		except Exception as e:
			frappe.log_error(f"AI Processing Error: {str(e)}", "AI Message Processing")
			self.status = "Failed"
			self.requires_human_review = 1
			self.save()
	
	def create_ai_response(self):
		"""Create an AI response message."""
		if not self.ai_response:
			return
		
		response_message = frappe.get_doc({
			"doctype": "AI Message",
			"conversation": self.conversation,
			"message_type": "Outgoing",
			"sender_type": "AI",
			"sender": "AI Assistant",
			"recipient_type": self.sender_type,
			"recipient": self.sender,
			"subject": f"Re: {self.subject}" if self.subject else "AI Response",
			"message_content": self.ai_response,
			"status": "Processed",
			"is_automated": 1,
			"processed_at": now()
		})
		response_message.insert()
		return response_message
	
	def escalate_to_human(self):
		"""Escalate message to human review."""
		self.status = "Escalated"
		self.requires_human_review = 1
		self.save()
		
		# Create notification for human reviewers
		self.notify_human_reviewers()
	
	def notify_human_reviewers(self):
		"""Send notification to human reviewers."""
		# Get users with Education Manager role
		reviewers = frappe.get_all(
			"Has Role",
			filters={"role": "Education Manager"},
			fields=["parent"]
		)
		
		for reviewer in reviewers:
			frappe.get_doc({
				"doctype": "Notification Log",
				"subject": f"AI Message requires review: {self.name}",
				"email_content": f"Message from {self.sender} requires human review.<br><br>Content: {self.message_content[:200]}...",
				"for_user": reviewer.parent,
				"type": "Alert",
				"document_type": "AI Message",
				"document_name": self.name
			}).insert()


@frappe.whitelist()
def send_message(recipient_type, recipient, message_content, subject=None):
	"""API endpoint to send a new message."""
	sender = frappe.session.user
	sender_type = get_user_type(sender)
	
	message = frappe.get_doc({
		"doctype": "AI Message",
		"message_type": "Incoming",
		"sender_type": sender_type,
		"sender": sender,
		"recipient_type": recipient_type,
		"recipient": recipient,
		"subject": subject,
		"message_content": message_content,
		"status": "Draft"
	})
	message.insert()
	
	# Process with AI if enabled
	ai_config = frappe.get_single("AI Configuration")
	if ai_config and ai_config.enable_ai_processing:
		frappe.enqueue(
			"education.education.doctype.ai_message.ai_message.process_message_async",
			message_name=message.name,
			queue="default"
		)
	
	return message.name


@frappe.whitelist()
def get_conversation_messages(conversation_name, limit=50):
	"""Get messages for a conversation."""
	messages = frappe.get_all(
		"AI Message",
		filters={"conversation": conversation_name},
		fields=["name", "message_type", "sender_type", "sender", "message_content", 
				"ai_response", "creation", "status", "is_automated"],
		order_by="creation asc",
		limit=limit
	)
	return messages


def process_message_async(message_name):
	"""Async function to process message with AI."""
	message = frappe.get_doc("AI Message", message_name)
	message.process_with_ai()


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

