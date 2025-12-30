# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from abc import ABC, abstractmethod
import json


class BaseAIService(ABC):
	"""Base class for AI service providers."""
	
	def __init__(self, config):
		self.config = config
		self.provider = config.get("provider")
		self.model = config.get("model")
		self.api_key = config.get("api_key")
		self.api_endpoint = config.get("api_endpoint")
		self.max_tokens = config.get("max_tokens", 1000)
		self.temperature = config.get("temperature", 0.7)
		self.timeout = config.get("timeout", 30)
	
	@abstractmethod
	def generate_response(self, prompt, system_prompt=None, context=None):
		"""Generate AI response for given prompt."""
		pass
	
	@abstractmethod
	def classify_intent(self, message):
		"""Classify the intent of a message."""
		pass
	
	@abstractmethod
	def analyze_sentiment(self, message):
		"""Analyze sentiment of a message."""
		pass
	
	@abstractmethod
	def test_connection(self):
		"""Test connection to AI provider."""
		pass
	
	def format_context(self, context_data):
		"""Format context data for AI processing."""
		if not context_data:
			return ""
		
		formatted_context = []
		for key, value in context_data.items():
			if value is not None:
				formatted_context.append(f"{key}: {value}")
		
		return "\n".join(formatted_context)
	
	def extract_keywords(self, text, max_keywords=10):
		"""Extract keywords from text (basic implementation)."""
		# This is a simple implementation - can be enhanced with NLP libraries
		import re
		
		# Remove common stop words
		stop_words = {
			'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
			'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 
			'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
		}
		
		# Extract words
		words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
		
		# Filter stop words and count frequency
		word_freq = {}
		for word in words:
			if word not in stop_words:
				word_freq[word] = word_freq.get(word, 0) + 1
		
		# Sort by frequency and return top keywords
		sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
		return [word for word, freq in sorted_words[:max_keywords]]


class OpenAIService(BaseAIService):
	"""OpenAI service implementation."""
	
	def __init__(self, config):
		super().__init__(config)
		self.base_url = config.get("api_endpoint", "https://api.openai.com/v1")
	
	def generate_response(self, prompt, system_prompt=None, context=None):
		"""Generate response using OpenAI API."""
		try:
			import requests
			
			headers = {
				"Authorization": f"Bearer {self.api_key}",
				"Content-Type": "application/json"
			}
			
			messages = []
			
			if system_prompt:
				messages.append({"role": "system", "content": system_prompt})
			
			if context:
				context_str = self.format_context(context)
				messages.append({"role": "system", "content": f"Context: {context_str}"})
			
			messages.append({"role": "user", "content": prompt})
			
			data = {
				"model": self.model,
				"messages": messages,
				"max_tokens": self.max_tokens,
				"temperature": self.temperature
			}
			
			response = requests.post(
				f"{self.base_url}/chat/completions",
				headers=headers,
				json=data,
				timeout=self.timeout
			)
			
			if response.status_code == 200:
				result = response.json()
				return {
					"success": True,
					"response": result["choices"][0]["message"]["content"],
					"usage": result.get("usage", {}),
					"model": result.get("model")
				}
			else:
				return {
					"success": False,
					"error": f"API Error: {response.status_code} - {response.text}"
				}
		
		except Exception as e:
			return {
				"success": False,
				"error": f"OpenAI Service Error: {str(e)}"
			}
	
	def classify_intent(self, message):
		"""Classify intent using OpenAI."""
		system_prompt = """
		Classify the intent of the following message into one of these categories:
		- admission_inquiry
		- fees_inquiry
		- course_inquiry
		- schedule_inquiry
		- technical_support
		- complaint
		- feedback
		- general_inquiry
		
		Respond with only the category name and a confidence score (0-1).
		Format: category_name|confidence_score
		"""
		
		result = self.generate_response(message, system_prompt)
		
		if result["success"]:
			try:
				response = result["response"].strip()
				if "|" in response:
					intent, confidence = response.split("|")
					return {
						"intent": intent.strip(),
						"confidence": float(confidence.strip())
					}
			except:
				pass
		
		return {"intent": "general_inquiry", "confidence": 0.5}
	
	def analyze_sentiment(self, message):
		"""Analyze sentiment using OpenAI."""
		system_prompt = """
		Analyze the sentiment of the following message.
		Respond with: sentiment|confidence_score
		Where sentiment is one of: positive, negative, neutral
		And confidence_score is between 0 and 1.
		"""
		
		result = self.generate_response(message, system_prompt)
		
		if result["success"]:
			try:
				response = result["response"].strip()
				if "|" in response:
					sentiment, confidence = response.split("|")
					return {
						"sentiment": sentiment.strip(),
						"confidence": float(confidence.strip())
					}
			except:
				pass
		
		return {"sentiment": "neutral", "confidence": 0.5}
	
	def test_connection(self):
		"""Test OpenAI connection."""
		try:
			result = self.generate_response("Hello, this is a test message.")
			return result
		except Exception as e:
			return {
				"success": False,
				"error": f"Connection test failed: {str(e)}"
			}


class MockAIService(BaseAIService):
	"""Mock AI service for testing and development."""
	
	def generate_response(self, prompt, system_prompt=None, context=None):
		"""Generate mock response."""
		return {
			"success": True,
			"response": f"This is a mock AI response to: {prompt[:50]}...",
			"usage": {"total_tokens": 50},
			"model": "mock-model"
		}
	
	def classify_intent(self, message):
		"""Mock intent classification."""
		# Simple keyword-based classification for demo
		message_lower = message.lower()
		
		if any(word in message_lower for word in ["fee", "payment", "cost", "tuition"]):
			return {"intent": "fees_inquiry", "confidence": 0.8}
		elif any(word in message_lower for word in ["course", "subject", "curriculum"]):
			return {"intent": "course_inquiry", "confidence": 0.8}
		elif any(word in message_lower for word in ["schedule", "timetable", "timing"]):
			return {"intent": "schedule_inquiry", "confidence": 0.8}
		elif any(word in message_lower for word in ["admission", "apply", "enrollment"]):
			return {"intent": "admission_inquiry", "confidence": 0.8}
		elif any(word in message_lower for word in ["problem", "issue", "error", "bug"]):
			return {"intent": "technical_support", "confidence": 0.7}
		elif any(word in message_lower for word in ["complaint", "complain", "unhappy"]):
			return {"intent": "complaint", "confidence": 0.7}
		elif any(word in message_lower for word in ["feedback", "suggestion", "improve"]):
			return {"intent": "feedback", "confidence": 0.7}
		else:
			return {"intent": "general_inquiry", "confidence": 0.6}
	
	def analyze_sentiment(self, message):
		"""Mock sentiment analysis."""
		message_lower = message.lower()
		
		positive_words = ["good", "great", "excellent", "happy", "satisfied", "love", "like"]
		negative_words = ["bad", "terrible", "awful", "unhappy", "hate", "dislike", "problem"]
		
		positive_count = sum(1 for word in positive_words if word in message_lower)
		negative_count = sum(1 for word in negative_words if word in message_lower)
		
		if positive_count > negative_count:
			return {"sentiment": "positive", "confidence": 0.7}
		elif negative_count > positive_count:
			return {"sentiment": "negative", "confidence": 0.7}
		else:
			return {"sentiment": "neutral", "confidence": 0.6}
	
	def test_connection(self):
		"""Mock connection test."""
		return {
			"success": True,
			"message": "Mock AI service is working",
			"model": "mock-model"
		}


def get_ai_service(config=None):
	"""Factory function to get appropriate AI service."""
	if not config:
		from education.education.doctype.ai_configuration.ai_configuration import get_current_config
		ai_config = get_current_config()
		config = ai_config.get_ai_provider_config()
	
	provider = config.get("provider", "Mock")
	
	if provider == "OpenAI":
		return OpenAIService(config)
	elif provider == "Mock":
		return MockAIService(config)
	else:
		# Default to mock service for unsupported providers
		frappe.log_error(f"Unsupported AI provider: {provider}", "AI Service")
		return MockAIService(config)

