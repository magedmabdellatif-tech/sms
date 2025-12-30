// AI Messaging JavaScript utilities

class AIMessaging {
    constructor() {
        this.currentConversation = null;
        this.isTyping = false;
        this.config = {};
        this.init();
    }

    async init() {
        await this.loadConfig();
        this.setupEventListeners();
    }

    async loadConfig() {
        try {
            const response = await frappe.call({
                method: 'education.education.api.get_ai_config_public'
            });
            this.config = response.message || {};
        } catch (error) {
            console.error('Failed to load AI config:', error);
        }
    }

    setupEventListeners() {
        // Listen for real-time message updates
        if (frappe.realtime) {
            frappe.realtime.on('ai_message_received', (data) => {
                this.handleNewMessage(data);
            });

            frappe.realtime.on('ai_response_generated', (data) => {
                this.handleAIResponse(data);
            });
        }
    }

    async sendMessage(recipientType, recipient, content, subject = null) {
        if (!content.trim()) {
            frappe.msgprint('Please enter a message');
            return;
        }

        try {
            const response = await frappe.call({
                method: 'education.education.api.send_ai_message',
                args: {
                    recipient_type: recipientType,
                    recipient: recipient,
                    message_content: content,
                    subject: subject
                }
            });

            if (response.message) {
                frappe.show_alert({
                    message: 'Message sent successfully',
                    indicator: 'green'
                });
                return response.message;
            }
        } catch (error) {
            frappe.msgprint('Failed to send message: ' + error.message);
            throw error;
        }
    }

    async getConversations(status = null, limit = 20) {
        try {
            const response = await frappe.call({
                method: 'education.education.api.get_ai_conversations',
                args: {
                    status: status,
                    limit: limit
                }
            });
            return response.message || [];
        } catch (error) {
            console.error('Failed to load conversations:', error);
            return [];
        }
    }

    async getConversationMessages(conversationName, limit = 50) {
        try {
            const response = await frappe.call({
                method: 'education.education.api.get_conversation_messages',
                args: {
                    conversation_name: conversationName,
                    limit: limit
                }
            });
            return response.message || [];
        } catch (error) {
            console.error('Failed to load messages:', error);
            return [];
        }
    }

    async submitFeedback(messageName, rating, comment = null) {
        try {
            const response = await frappe.call({
                method: 'education.education.api.submit_message_feedback',
                args: {
                    message_name: messageName,
                    rating: rating,
                    comment: comment
                }
            });

            if (response.message && response.message.success) {
                frappe.show_alert({
                    message: 'Feedback submitted',
                    indicator: 'green'
                });
            }
            return response.message;
        } catch (error) {
            frappe.msgprint('Failed to submit feedback: ' + error.message);
            throw error;
        }
    }

    async getTemplates(category = null, userType = null) {
        try {
            const response = await frappe.call({
                method: 'education.education.api.get_ai_templates',
                args: {
                    category: category,
                    user_type: userType
                }
            });
            return response.message || [];
        } catch (error) {
            console.error('Failed to load templates:', error);
            return [];
        }
    }

    handleNewMessage(data) {
        // Handle incoming message notification
        if (data.conversation === this.currentConversation) {
            this.displayMessage(data.message);
        } else {
            this.showNotification(data);
        }
    }

    handleAIResponse(data) {
        // Handle AI response
        if (data.conversation === this.currentConversation) {
            this.displayAIResponse(data.response);
        }
        this.hideTypingIndicator();
    }

    displayMessage(message) {
        // Override in specific implementations
        console.log('New message:', message);
    }

    displayAIResponse(response) {
        // Override in specific implementations
        console.log('AI response:', response);
    }

    showNotification(data) {
        frappe.show_alert({
            message: `New message from ${data.sender}`,
            indicator: 'blue'
        });
    }

    showTypingIndicator() {
        this.isTyping = true;
        // Override in specific implementations
    }

    hideTypingIndicator() {
        this.isTyping = false;
        // Override in specific implementations
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    formatDate(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffTime = Math.abs(now - date);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        if (diffDays === 1) {
            return 'Today';
        } else if (diffDays === 2) {
            return 'Yesterday';
        } else if (diffDays <= 7) {
            return date.toLocaleDateString([], { weekday: 'long' });
        } else {
            return date.toLocaleDateString();
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    linkify(text) {
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        return text.replace(urlRegex, '<a href="$1" target="_blank">$1</a>');
    }

    // Quick message templates
    getQuickReplies() {
        return [
            'Thank you for your message',
            'I need more information',
            'Let me check and get back to you',
            'This has been resolved',
            'Please contact the relevant department'
        ];
    }

    // Emoji support
    getCommonEmojis() {
        return ['👍', '👎', '😊', '😔', '❓', '✅', '❌', '📞', '📧', '📅'];
    }
}

// Initialize AI Messaging when DOM is ready
$(document).ready(function() {
    if (typeof frappe !== 'undefined') {
        window.aiMessaging = new AIMessaging();
    }
});

// Utility functions for forms and lists
frappe.ui.form.on('AI Message', {
    refresh: function(frm) {
        if (frm.doc.status === 'Draft' && frm.doc.message_type === 'Incoming') {
            frm.add_custom_button(__('Process with AI'), function() {
                frappe.call({
                    method: 'education.education.ai_services.message_processor.process_message_manually',
                    args: {
                        message_name: frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.msgprint('Message processed successfully');
                            frm.reload_doc();
                        } else {
                            frappe.msgprint('Failed to process message: ' + (r.message.error || 'Unknown error'));
                        }
                    }
                });
            });
        }

        if (frm.doc.status === 'Processed' && frm.doc.requires_human_review) {
            frm.add_custom_button(__('Mark as Reviewed'), function() {
                frm.set_value('requires_human_review', 0);
                frm.save();
            });
        }
    }
});

frappe.ui.form.on('AI Conversation', {
    refresh: function(frm) {
        if (frm.doc.status === 'Active') {
            frm.add_custom_button(__('Close Conversation'), function() {
                frappe.prompt('Reason for closing (optional)', function(data) {
                    frappe.call({
                        method: 'education.education.api.close_conversation',
                        args: {
                            conversation_name: frm.doc.name,
                            reason: data.value
                        },
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                frappe.msgprint('Conversation closed');
                                frm.reload_doc();
                            }
                        }
                    });
                });
            });

            frm.add_custom_button(__('Escalate'), function() {
                frappe.prompt('Escalation reason (optional)', function(data) {
                    frappe.call({
                        method: 'education.education.api.escalate_conversation',
                        args: {
                            conversation_name: frm.doc.name,
                            reason: data.value
                        },
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                frappe.msgprint('Conversation escalated');
                                frm.reload_doc();
                            }
                        }
                    });
                });
            });
        }

        if (frm.doc.message_count > 0) {
            frm.add_custom_button(__('View Messages'), function() {
                frappe.route_options = {
                    'conversation': frm.doc.name
                };
                frappe.set_route('List', 'AI Message');
            });

            frm.add_custom_button(__('Generate Summary'), function() {
                frm.call('generate_summary').then(() => {
                    frappe.msgprint('Summary generated');
                    frm.reload_doc();
                });
            });
        }
    }
});

frappe.ui.form.on('AI Message Template', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Test Template'), function() {
                frappe.prompt([
                    {
                        label: 'Test Message',
                        fieldname: 'message',
                        fieldtype: 'Text',
                        reqd: 1
                    },
                    {
                        label: 'Context Data (JSON)',
                        fieldname: 'context',
                        fieldtype: 'Code',
                        options: 'JSON'
                    }
                ], function(data) {
                    frappe.call({
                        method: 'education.education.doctype.ai_message_template.ai_message_template.render_template',
                        args: {
                            template_name: frm.doc.name,
                            context_data: data.context
                        },
                        callback: function(r) {
                            if (r.message) {
                                frappe.msgprint({
                                    title: 'Template Output',
                                    message: '<pre>' + r.message + '</pre>',
                                    wide: true
                                });
                            }
                        }
                    });
                }, 'Test Template', 'Test');
            });
        }
    }
});

