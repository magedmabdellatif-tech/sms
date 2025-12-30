# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now
import json


class AIConversation(Document):
	def before_insert(self):
		"""Set default values before inserting."""
		if not self.status:
			self.status = "Active"
		if not self.priority:
			self.priority = "Medium"
		if not self.started_by:
			self.started_by = frappe.session.user
		if not self.last_message_at:
			self.last_message_at = now()
	
	def before_save(self):
		"""Update conversation statistics."""
		self.update_message_count()
		self.update_last_message_time()
	
	def update_message_count(self):
		"""Update the message count for this conversation."""
		count = frappe.db.count("AI Message", {"conversation": self.name})
		self.message_count = count
	
	def update_last_message_time(self):
		"""Update the last message timestamp."""
		last_message = frappe.db.get_value(
			"AI Message",
			{"conversation": self.name},
			"creation",
			order_by="creation desc"
		)
		if last_message:
			self.last_message_at = last_message
	
	def add_participant(self, participant_type, participant_id, participant_name=None):
		"""Add a participant to the conversation."""
		participants = json.loads(self.participants or "[]")
		
		# Check if participant already exists
		for p in participants:
			if p.get("id") == participant_id and p.get("type") == participant_type:
				return
		
		# Add new participant
		participant = {
			"type": participant_type,
			"id": participant_id,
			"name": participant_name or participant_id,
			"joined_at": now()
		}
		participants.append(participant)
		self.participants = json.dumps(participants)
		self.save()
	
	def remove_participant(self, participant_type, participant_id):
		"""Remove a participant from the conversation."""
		participants = json.loads(self.participants or "[]")
		participants = [
			p for p in participants 
			if not (p.get("id") == participant_id and p.get("type") == participant_type)
		]
		self.participants = json.dumps(participants)
		self.save()
	
	def get_participants_list(self):
		"""Get formatted list of participants."""
		participants = json.loads(self.participants or "[]")
		return participants
	
	def close_conversation(self, reason=None):
		"""Close the conversation."""
		self.status = "Closed"
		if reason:
			metadata = json.loads(self.metadata or "{}")
			metadata["close_reason"] = reason
			metadata["closed_at"] = now()
			metadata["closed_by"] = frappe.session.user
			self.metadata = json.dumps(metadata)
		self.save()
	
	def reopen_conversation(self):
		"""Reopen a closed conversation."""
		self.status = "Active"
		metadata = json.loads(self.metadata or "{}")
		metadata["reopened_at"] = now()
		metadata["reopened_by"] = frappe.session.user
		self.metadata = json.dumps(metadata)
		self.save()
	
	def escalate_conversation(self, escalation_reason=None):
		"""Escalate the conversation to human review."""
		self.status = "Escalated"
		self.priority = "High"
		
		metadata = json.loads(self.metadata or "{}")
		metadata["escalated_at"] = now()
		metadata["escalated_by"] = frappe.session.user
		if escalation_reason:
			metadata["escalation_reason"] = escalation_reason
		self.metadata = json.dumps(metadata)
		
		self.save()
		self.notify_escalation()
	
	def notify_escalation(self):
		"""Send notification about conversation escalation."""
		# Get Education Managers for notification
		managers = frappe.get_all(
			"Has Role",
			filters={"role": "Education Manager"},
			fields=["parent"]
		)
		
		for manager in managers:
			frappe.get_doc({
				"doctype": "Notification Log",
				"subject": f"Conversation escalated: {self.title}",
				"email_content": f"Conversation {self.name} has been escalated and requires attention.",
				"for_user": manager.parent,
				"type": "Alert",
				"document_type": "AI Conversation",
				"document_name": self.name
			}).insert()
	
	def assign_to_user(self, user):
		"""Assign conversation to a specific user."""
		self.assigned_to = user
		self.save()
		
		# Send notification to assigned user
		frappe.get_doc({
			"doctype": "Notification Log",
			"subject": f"Conversation assigned: {self.title}",
			"email_content": f"You have been assigned to conversation {self.name}.",
			"for_user": user,
			"type": "Assignment",
			"document_type": "AI Conversation",
			"document_name": self.name
		}).insert()
	
	def generate_summary(self):
		"""Generate AI summary of the conversation."""
		try:
			# Get all messages in conversation
			messages = frappe.get_all(
				"AI Message",
				filters={"conversation": self.name},
				fields=["message_content", "ai_response", "creation"],
				order_by="creation asc"
			)
			
			if not messages:
				return
			
			# Import AI service for summary generation
			from education.education.ai_services.message_processor import MessageProcessor
			
			processor = MessageProcessor()
			summary = processor.generate_conversation_summary(messages)
			
			if summary:
				self.summary = summary
				self.save()
				
		except Exception as e:
			frappe.log_error(f"Summary Generation Error: {str(e)}", "AI Conversation Summary")
	
	def get_conversation_analytics(self):
		"""Get analytics data for the conversation."""
		messages = frappe.get_all(
			"AI Message",
			filters={"conversation": self.name},
			fields=["message_type", "sender_type", "status", "response_time", "feedback_rating"]
		)
		
		analytics = {
			"total_messages": len(messages),
			"incoming_messages": len([m for m in messages if m.message_type == "Incoming"]),
			"outgoing_messages": len([m for m in messages if m.message_type == "Outgoing"]),
			"ai_responses": len([m for m in messages if m.sender_type == "AI"]),
			"avg_response_time": 0,
			"avg_rating": 0
		}
		
		# Calculate average response time
		response_times = [m.response_time for m in messages if m.response_time]
		if response_times:
			analytics["avg_response_time"] = sum(response_times) / len(response_times)
		
		# Calculate average rating
		ratings = [m.feedback_rating for m in messages if m.feedback_rating]
		if ratings:
			analytics["avg_rating"] = sum(ratings) / len(ratings)
		
		return analytics


@frappe.whitelist()
def get_user_conversations(user=None, status=None, limit=20):
	"""Get conversations for a user."""
	if not user:
		user = frappe.session.user
	
	filters = {}
	if status:
		filters["status"] = status
	
	# Get conversations where user is a participant
	conversations = frappe.get_all(
		"AI Conversation",
		filters=filters,
		fields=["name", "title", "status", "priority", "last_message_at", "message_count"],
		order_by="last_message_at desc",
		limit=limit
	)
	
	# Filter conversations where user is a participant
	user_conversations = []
	for conv in conversations:
		conv_doc = frappe.get_doc("AI Conversation", conv.name)
		participants = json.loads(conv_doc.participants or "[]")
		participant_ids = [p.get("id") for p in participants]
		
		if user in participant_ids or conv_doc.started_by == user or conv_doc.assigned_to == user:
			user_conversations.append(conv)
	
	return user_conversations


@frappe.whitelist()
def create_conversation(title, participants, conversation_type="General"):
	"""Create a new conversation."""
	conversation = frappe.get_doc({
		"doctype": "AI Conversation",
		"title": title,
		"conversation_type": conversation_type,
		"participants": json.dumps(participants),
		"started_by": frappe.session.user,
		"status": "Active"
	})
	conversation.insert()
	return conversation.name


@frappe.whitelist()
def close_conversation(conversation_name, reason=None):
	"""Close a conversation."""
	conversation = frappe.get_doc("AI Conversation", conversation_name)
	conversation.close_conversation(reason)
	return {"success": True}


@frappe.whitelist()
def escalate_conversation(conversation_name, reason=None):
	"""Escalate a conversation."""
	conversation = frappe.get_doc("AI Conversation", conversation_name)
	conversation.escalate_conversation(reason)
	return {"success": True}

