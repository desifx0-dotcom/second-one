"""
Email notification service
Handles sending transactional emails, notifications, and alerts
"""

import asyncio
import logging
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List, Optional, Union
import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape
import markdown

from src.core.base import BaseService, ProcessingResult
from src.core.exceptions import VideoAIError, ExternalServiceError
from src.core.constants import ErrorCodes

logger = logging.getLogger(__name__)

class EmailService(BaseService):
    """
    Production email service supporting multiple providers and templates
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Email configuration
        self.smtp_host = config.get('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = config.get('SMTP_PORT', 587)
        self.smtp_username = config.get('SMTP_USERNAME', '')
        self.smtp_password = config.get('SMTP_PASSWORD', '')
        self.use_tls = config.get('SMTP_USE_TLS', True)
        self.use_ssl = config.get('SMTP_USE_SSL', False)
        
        # Sender information
        self.default_sender = config.get('DEFAULT_SENDER', 'noreply@videoai.example.com')
        self.sender_name = config.get('SENDER_NAME', 'Video AI SaaS')
        
        # Template configuration
        self.template_dir = config.get('EMAIL_TEMPLATE_DIR', 'templates/emails')
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Email providers (fallback configuration)
        self.providers = [
            {
                'name': 'primary',
                'host': self.smtp_host,
                'port': self.smtp_port,
                'username': self.smtp_username,
                'password': self.smtp_password,
                'use_tls': self.use_tls,
                'use_ssl': self.use_ssl
            }
        ]
        
        # Queue for batch processing
        self.email_queue = asyncio.Queue()
        self.is_processing = False
        
        # Statistics
        self.stats = {
            'total_sent': 0,
            'total_failed': 0,
            'sent_today': 0,
            'by_type': {},
            'by_provider': {},
            'queue_size': 0,
            'last_reset': datetime.now().date()
        }
        
        # Email templates cache
        self.template_cache = {}
    
    def initialize(self) -> bool:
        """Initialize email service and start background processor"""
        try:
            logger.info("Initializing EmailService...")
            
            # Verify SMTP configuration
            if not self.smtp_host or not self.smtp_username:
                logger.warning("SMTP configuration incomplete")
                # Service can still work with other providers or queue emails
            
            # Load email templates
            self._load_templates()
            
            # Start background email processor
            asyncio.create_task(self._process_email_queue())
            
            logger.info("EmailService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"EmailService initialization failed: {str(e)}")
            return False
    
    async def send_email(
        self,
        to_email: Union[str, List[str]],
        subject: str,
        template_name: str = None,
        template_data: Dict[str, Any] = None,
        html_content: str = None,
        text_content: str = None,
        sender: str = None,
        cc: List[str] = None,
        bcc: List[str] = None,
        attachments: List[Dict[str, Any]] = None,
        priority: str = 'normal',
        send_immediately: bool = True
    ) -> ProcessingResult:
        """
        Send an email
        
        Args:
            to_email: Recipient email(s)
            subject: Email subject
            template_name: Template name (optional)
            template_data: Template data (optional)
            html_content: HTML content (optional)
            text_content: Text content (optional)
            sender: Sender email (optional)
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            attachments: Attachments (optional)
            priority: 'high', 'normal', or 'low'
            send_immediately: Send now or queue for batch processing
            
        Returns:
            ProcessingResult: Email sending result
        """
        start_time = datetime.now()
        
        try:
            # Normalize recipients
            if isinstance(to_email, str):
                recipients = [to_email]
            else:
                recipients = list(to_email)
            
            # Validate recipients
            valid_recipients = []
            for email in recipients:
                if self._validate_email(email):
                    valid_recipients.append(email)
                else:
                    logger.warning(f"Invalid email address skipped: {email}")
            
            if not valid_recipients:
                return ProcessingResult(
                    success=False,
                    error="No valid recipients"
                )
            
            # Prepare email data
            email_data = {
                'to': valid_recipients,
                'subject': subject,
                'template_name': template_name,
                'template_data': template_data or {},
                'html_content': html_content,
                'text_content': text_content,
                'sender': sender or self.default_sender,
                'sender_name': self.sender_name,
                'cc': cc or [],
                'bcc': bcc or [],
                'attachments': attachments or [],
                'priority': priority,
                'created_at': datetime.now().isoformat()
            }
            
            # Generate content if template provided
            if template_name and not (html_content or text_content):
                generated_content = await self._generate_email_content(
                    template_name, template_data
                )
                
                if generated_content:
                    email_data['html_content'] = generated_content.get('html')
                    email_data['text_content'] = generated_content.get('text')
            
            # Ensure we have content
            if not email_data['html_content'] and not email_data['text_content']:
                return ProcessingResult(
                    success=False,
                    error="No email content provided"
                )
            
            # Send or queue email
            if send_immediately:
                # Send immediately
                send_result = await self._send_email_now(email_data)
                
                # Update statistics
                email_type = template_name or 'custom'
                self._update_statistics(
                    email_type,
                    send_result.success,
                    len(valid_recipients)
                )
                
                duration = (datetime.now() - start_time).total_seconds()
                
                if send_result.success:
                    logger.info(f"Email sent to {len(valid_recipients)} recipients")
                    return ProcessingResult(
                        success=True,
                        data={
                            'message_id': send_result.data.get('message_id'),
                            'recipients': valid_recipients,
                            'queued': False
                        },
                        duration=duration
                    )
                else:
                    logger.error(f"Email sending failed: {send_result.error}")
                    return ProcessingResult(
                        success=False,
                        error=send_result.error,
                        error_details=send_result.error_details,
                        duration=duration
                    )
            else:
                # Queue for batch processing
                await self.email_queue.put(email_data)
                self.stats['queue_size'] = self.email_queue.qsize()
                
                logger.info(f"Email queued for {len(valid_recipients)} recipients")
                
                return ProcessingResult(
                    success=True,
                    data={
                        'queued': True,
                        'queue_position': self.stats['queue_size'],
                        'recipients': valid_recipients
                    }
                )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"Email preparation failed: {str(e)}", exc_info=True)
            
            return ProcessingResult(
                success=False,
                error=f"Email preparation failed: {str(e)}",
                error_details={'exception_type': type(e).__name__},
                duration=duration
            )
    
    async def send_bulk_emails(
        self,
        emails_data: List[Dict[str, Any]],
        batch_size: int = 50,
        delay_between_batches: float = 1.0
    ) -> ProcessingResult:
        """
        Send bulk emails
        
        Args:
            emails_data: List of email data dictionaries
            batch_size: Emails per batch
            delay_between_batches: Delay between batches in seconds
            
        Returns:
            ProcessingResult: Bulk sending result
        """
        start_time = datetime.now()
        
        try:
            total_emails = len(emails_data)
            successful = 0
            failed = []
            
            logger.info(f"Starting bulk email send: {total_emails} emails")
            
            # Process in batches
            for i in range(0, total_emails, batch_size):
                batch = emails_data[i:i + batch_size]
                batch_number = (i // batch_size) + 1
                
                logger.info(f"Processing batch {batch_number}: {len(batch)} emails")
                
                # Create tasks for batch
                tasks = []
                for email_data in batch:
                    task = asyncio.create_task(
                        self._send_email_now(email_data)
                    )
                    tasks.append(task)
                
                # Wait for batch completion
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        failed.append({
                            'index': i + j,
                            'error': str(result)
                        })
                        logger.error(f"Email {i + j} failed: {str(result)}")
                    elif result.success:
                        successful += 1
                    else:
                        failed.append({
                            'index': i + j,
                            'error': result.error
                        })
                
                # Delay between batches
                if i + batch_size < total_emails:
                    await asyncio.sleep(delay_between_batches)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Update statistics
            self.stats['total_sent'] += successful
            self.stats['total_failed'] += len(failed)
            
            result_data = {
                'total': total_emails,
                'successful': successful,
                'failed': len(failed),
                'failure_details': failed,
                'duration': duration,
                'average_time_per_email': duration / total_emails if total_emails > 0 else 0
            }
            
            logger.info(f"Bulk email send completed: {successful}/{total_emails} successful")
            
            return ProcessingResult(
                success=True,
                data=result_data,
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"Bulk email sending failed: {str(e)}", exc_info=True)
            
            return ProcessingResult(
                success=False,
                error=f"Bulk email sending failed: {str(e)}",
                duration=duration
            )
    
    async def send_template_email(
        self,
        template_name: str,
        to_email: Union[str, List[str]],
        template_data: Dict[str, Any],
        subject: Optional[str] = None,
        **kwargs
    ) -> ProcessingResult:
        """
        Send email using template
        
        Args:
            template_name: Template name
            to_email: Recipient email(s)
            template_data: Template data
            subject: Custom subject (optional)
            **kwargs: Additional send_email parameters
            
        Returns:
            ProcessingResult: Email sending result
        """
        # Get template configuration
        template_config = self._get_template_config(template_name)
        if not template_config:
            return ProcessingResult(
                success=False,
                error=f"Template not found: {template_name}"
            )
        
        # Use template subject if not provided
        if subject is None:
            subject = template_config.get('subject', '')
        
        # Render subject with template data
        try:
            subject = self._render_template_string(subject, template_data)
        except Exception as e:
            logger.warning(f"Failed to render subject: {str(e)}")
        
        # Send email
        return await self.send_email(
            to_email=to_email,
            subject=subject,
            template_name=template_name,
            template_data=template_data,
            **kwargs
        )
    
    async def get_email_status(self, message_id: str) -> ProcessingResult:
        """
        Get email delivery status
        
        Args:
            message_id: Email message ID
            
        Returns:
            ProcessingResult: Email status
        """
        # In production, integrate with email tracking service
        # For now, return basic status
        
        return ProcessingResult(
            success=True,
            data={
                'message_id': message_id,
                'status': 'sent',  # Would be 'sent', 'delivered', 'opened', etc.
                'last_updated': datetime.now().isoformat()
            }
        )
    
    async def validate_email_address(self, email: str) -> ProcessingResult:
        """
        Validate email address
        
        Args:
            email: Email address to validate
            
        Returns:
            ProcessingResult: Validation result
        """
        is_valid = self._validate_email(email)
        
        if is_valid:
            # Optional: Check MX records
            mx_valid = await self._check_mx_records(email)
            
            return ProcessingResult(
                success=True,
                data={
                    'email': email,
                    'is_valid': True,
                    'mx_valid': mx_valid,
                    'suggestions': []
                }
            )
        else:
            # Try to suggest corrections
            suggestions = self._suggest_email_corrections(email)
            
            return ProcessingResult(
                success=False,
                error="Invalid email address",
                data={
                    'email': email,
                    'is_valid': False,
                    'suggestions': suggestions
                }
            )
    
    # ========== PRIVATE METHODS ==========
    
    def _load_templates(self):
        """Load email templates"""
        try:
            # Core templates
            core_templates = {
                'welcome': {
                    'subject': 'Welcome to Video AI SaaS!',
                    'description': 'Welcome email for new users',
                    'variables': ['user', 'verification_token', 'verification_url']
                },
                'verify_email': {
                    'subject': 'Verify Your Email Address',
                    'description': 'Email verification',
                    'variables': ['user', 'verification_token', 'verification_url']
                },
                'reset_password': {
                    'subject': 'Reset Your Password',
                    'description': 'Password reset request',
                    'variables': ['user', 'reset_token', 'reset_url']
                },
                'password_changed': {
                    'subject': 'Password Changed Successfully',
                    'description': 'Password change confirmation',
                    'variables': ['user']
                },
                'payment_receipt': {
                    'subject': 'Payment Receipt - {{invoice_number}}',
                    'description': 'Payment receipt',
                    'variables': ['user', 'invoice', 'payment_details']
                },
                'payment_failed': {
                    'subject': 'Payment Failed - Action Required',
                    'description': 'Payment failure notification',
                    'variables': ['user', 'invoice', 'retry_url']
                },
                'subscription_updated': {
                    'subject': 'Subscription Updated',
                    'description': 'Subscription change confirmation',
                    'variables': ['user', 'old_plan', 'new_plan', 'change_details']
                },
                'subscription_cancelled': {
                    'subject': 'Subscription Cancelled',
                    'description': 'Subscription cancellation confirmation',
                    'variables': ['user', 'cancellation_date', 'ends_at']
                },
                'video_processing_started': {
                    'subject': 'Video Processing Started',
                    'description': 'Video processing started notification',
                    'variables': ['user', 'video', 'estimated_time']
                },
                'video_processing_completed': {
                    'subject': 'Video Processing Completed!',
                    'description': 'Video processing completed notification',
                    'variables': ['user', 'video', 'results_url']
                },
                'video_processing_failed': {
                    'subject': 'Video Processing Failed',
                    'description': 'Video processing failure notification',
                    'variables': ['user', 'video', 'error_message', 'retry_url']
                },
                'monthly_report': {
                    'subject': 'Your Monthly Activity Report - {{month}}',
                    'description': 'Monthly activity report',
                    'variables': ['user', 'month', 'stats', 'videos_processed']
                },
                'admin_alert': {
                    'subject': 'Admin Alert: {{alert_type}}',
                    'description': 'Administrator alert',
                    'variables': ['alert_type', 'alert_message', 'timestamp', 'details']
                }
            }
            
            self.template_cache.update(core_templates)
            
            logger.info(f"Loaded {len(core_templates)} email templates")
            
        except Exception as e:
            logger.error(f"Failed to load email templates: {str(e)}")
    
    def _get_template_config(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get template configuration"""
        return self.template_cache.get(template_name)
    
    async def _generate_email_content(
        self,
        template_name: str,
        template_data: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        """Generate email content from template"""
        try:
            # Try to load HTML template
            html_template_path = f"{template_name}.html"
            text_template_path = f"{template_name}.txt"
            
            html_content = None
            text_content = None
            
            # Load HTML template
            try:
                html_template = self.jinja_env.get_template(html_template_path)
                html_content = html_template.render(**template_data)
            except Exception as e:
                logger.warning(f"HTML template not found or error: {str(e)}")
            
            # Load text template
            try:
                text_template = self.jinja_env.get_template(text_template_path)
                text_content = text_template.render(**template_data)
            except Exception as e:
                logger.warning(f"Text template not found or error: {str(e)}")
                # Generate text from HTML if available
                if html_content and not text_content:
                    text_content = self._html_to_text(html_content)
            
            # If no template files, use default template
            if not html_content and not text_content:
                html_content = self._generate_default_template(template_name, template_data)
                text_content = self._html_to_text(html_content)
            
            return {
                'html': html_content,
                'text': text_content
            }
            
        except Exception as e:
            logger.error(f"Failed to generate email content: {str(e)}")
            return None
    
    def _generate_default_template(
        self,
        template_name: str,
        template_data: Dict[str, Any]
    ) -> str:
        """Generate default HTML template"""
        template_config = self._get_template_config(template_name)
        subject = template_config.get('subject', 'Notification') if template_config else 'Notification'
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{subject}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .footer {{ text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #777; font-size: 12px; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Video AI SaaS</h1>
                <p>{subject}</p>
            </div>
            <div class="content">
                <h2>{subject}</h2>
                <p>This is an automated message from Video AI SaaS.</p>
                
                <h3>Details:</h3>
                <pre style="background: #f0f0f0; padding: 15px; border-radius: 5px; overflow-x: auto;">
{self._format_template_data(template_data)}
                </pre>
                
                <p>If you have any questions, please contact our support team.</p>
                
                <div style="text-align: center; margin-top: 30px;">
                    <a href="https://app.videoai.example.com" class="button">Go to Dashboard</a>
                </div>
            </div>
            <div class="footer">
                <p>&copy; {datetime.now().year} Video AI SaaS. All rights reserved.</p>
                <p>This is an automated message, please do not reply to this email.</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _format_template_data(self, data: Dict[str, Any]) -> str:
        """Format template data for display"""
        import json
        return json.dumps(data, indent=2, default=str)
    
    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text"""
        try:
            # Simple HTML to text conversion
            import re
            
            # Remove script and style tags
            html = re.sub(r'<(script|style).*?>.*?</\1>', '', html, flags=re.DOTALL)
            
            # Replace common HTML tags
            html = re.sub(r'<br\s*/?>', '\n', html)
            html = re.sub(r'<p.*?>', '\n\n', html)
            html = re.sub(r'</p>', '', html)
            html = re.sub(r'<div.*?>', '\n', html)
            html = re.sub(r'</div>', '', html)
            html = re.sub(r'<h[1-6].*?>', '\n\n', html)
            html = re.sub(r'</h[1-6]>', '\n\n', html)
            html = re.sub(r'<li.*?>', '• ', html)
            html = re.sub(r'</li>', '\n', html)
            html = re.sub(r'<ul.*?>', '\n', html)
            html = re.sub(r'</ul>', '\n', html)
            
            # Remove all other tags
            html = re.sub(r'<.*?>', '', html)
            
            # Decode HTML entities
            import html as html_module
            html = html_module.unescape(html)
            
            # Collapse multiple newlines
            html = re.sub(r'\n\s*\n', '\n\n', html)
            
            # Trim whitespace
            html = html.strip()
            
            return html
            
        except Exception as e:
            logger.warning(f"HTML to text conversion failed: {str(e)}")
            return html
    
    async def _send_email_now(self, email_data: Dict[str, Any]) -> ProcessingResult:
        """Send email immediately"""
        try:
            # Try providers in order
            for provider in self.providers:
                try:
                    result = await self._send_with_provider(email_data, provider)
                    if result.success:
                        return result
                except Exception as e:
                    logger.warning(f"Provider {provider['name']} failed: {str(e)}")
                    continue
            
            # All providers failed
            return ProcessingResult(
                success=False,
                error="All email providers failed",
                error_details={'code': ErrorCodes.SYSTEM_EXTERNAL_API_ERROR}
            )
            
        except Exception as e:
            logger.error(f"Email sending failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Email sending failed: {str(e)}"
            )
    
    async def _send_with_provider(
        self,
        email_data: Dict[str, Any],
        provider_config: Dict[str, Any]
    ) -> ProcessingResult:
        """Send email using specific provider"""
        try:
            # Create message
            message = self._create_email_message(email_data)
            
            # Send using SMTP
            if provider_config.get('use_ssl'):
                # SSL connection
                context = ssl.create_default_context()
                
                async with aiosmtplib.SMTP(
                    hostname=provider_config['host'],
                    port=provider_config['port'],
                    use_tls=provider_config['use_tls'],
                    tls_context=context
                ) as smtp:
                    await smtp.login(
                        provider_config['username'],
                        provider_config['password']
                    )
                    
                    response = await smtp.send_message(message)
                    
            else:
                # TLS connection
                async with aiosmtplib.SMTP(
                    hostname=provider_config['host'],
                    port=provider_config['port']
                ) as smtp:
                    if provider_config['use_tls']:
                        await smtp.starttls()
                    
                    await smtp.login(
                        provider_config['username'],
                        provider_config['password']
                    )
                    
                    response = await smtp.send_message(message)
            
            # Extract message ID from response
            message_id = None
            if response and hasattr(response, 'message_id'):
                message_id = response.message_id
            
            # Update provider statistics
            provider_name = provider_config['name']
            if provider_name not in self.stats['by_provider']:
                self.stats['by_provider'][provider_name] = {
                    'sent': 0,
                    'failed': 0
                }
            self.stats['by_provider'][provider_name]['sent'] += 1
            
            return ProcessingResult(
                success=True,
                data={
                    'message_id': message_id,
                    'provider': provider_name
                }
            )
            
        except Exception as e:
            # Update provider failure statistics
            provider_name = provider_config['name']
            if provider_name not in self.stats['by_provider']:
                self.stats['by_provider'][provider_name] = {
                    'sent': 0,
                    'failed': 0
                }
            self.stats['by_provider'][provider_name]['failed'] += 1
            
            raise e
    
    def _create_email_message(self, email_data: Dict[str, Any]) -> MIMEMultipart:
        """Create MIME email message"""
        # Create message container
        msg = MIMEMultipart('alternative')
        msg['Subject'] = email_data['subject']
        msg['From'] = f"{email_data['sender_name']} <{email_data['sender']}>"
        msg['To'] = ', '.join(email_data['to'])
        
        if email_data['cc']:
            msg['Cc'] = ', '.join(email_data['cc'])
        
        if email_data['bcc']:
            msg['Bcc'] = ', '.join(email_data['bcc'])
        
        # Add headers
        msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
        msg['Message-ID'] = self._generate_message_id()
        msg['X-Mailer'] = 'VideoAI SaaS Email Service'
        msg['X-Priority'] = self._get_priority_header(email_data['priority'])
        
        # Add text/plain part
        if email_data['text_content']:
            text_part = MIMEText(email_data['text_content'], 'plain', 'utf-8')
            msg.attach(text_part)
        
        # Add text/html part
        if email_data['html_content']:
            html_part = MIMEText(email_data['html_content'], 'html', 'utf-8')
            msg.attach(html_part)
        
        # Add attachments
        for attachment in email_data['attachments']:
            self._add_attachment(msg, attachment)
        
        return msg
    
    def _add_attachment(self, msg: MIMEMultipart, attachment: Dict[str, Any]):
        """Add attachment to email message"""
        try:
            from email.mime.base import MIMEBase
            from email import encoders
            import mimetypes
            
            filename = attachment.get('filename', 'attachment')
            content = attachment.get('content')
            content_type = attachment.get('content_type')
            
            if not content:
                return
            
            # Determine content type
            if not content_type:
                content_type, encoding = mimetypes.guess_type(filename)
                if not content_type:
                    content_type = 'application/octet-stream'
            
            maintype, subtype = content_type.split('/', 1)
            
            if maintype == 'text':
                # Text attachment
                part = MIMEText(content, _subtype=subtype, _charset='utf-8')
            else:
                # Binary attachment
                part = MIMEBase(maintype, subtype)
                part.set_payload(content)
                encoders.encode_base64(part)
            
            part.add_header(
                'Content-Disposition',
                'attachment',
                filename=filename
            )
            
            msg.attach(part)
            
        except Exception as e:
            logger.warning(f"Failed to add attachment: {str(e)}")
    
    def _generate_message_id(self) -> str:
        """Generate unique message ID"""
        import socket
        import time
        import random
        
        timestamp = int(time.time() * 1000)
        random_part = random.randint(1000, 9999)
        hostname = socket.gethostname()
        
        return f"<{timestamp}.{random_part}@{hostname}>"
    
    def _get_priority_header(self, priority: str) -> str:
        """Get X-Priority header value"""
        priority_map = {
            'high': '1 (Highest)',
            'normal': '3 (Normal)',
            'low': '5 (Lowest)'
        }
        return priority_map.get(priority, '3 (Normal)')
    
    def _validate_email(self, email: str) -> bool:
        """Validate email address format"""
        import re
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    async def _check_mx_records(self, email: str) -> bool:
        """Check MX records for email domain"""
        try:
            import dns.resolver
            
            domain = email.split('@')[1]
            
            try:
                answers = dns.resolver.resolve(domain, 'MX')
                return len(answers) > 0
            except dns.resolver.NoAnswer:
                return False
            except dns.resolver.NXDOMAIN:
                return False
                
        except ImportError:
            # DNS resolver not available
            return True
        except Exception:
            return True  # Assume valid if check fails
    
    def _suggest_email_corrections(self, email: str) -> List[str]:
        """Suggest corrections for invalid email"""
        suggestions = []
        
        # Common domain corrections
        common_typos = {
            'gmail.com': ['gmial.com', 'gmal.com', 'gmil.com'],
            'yahoo.com': ['yaho.com', 'yahoo.co', 'yhoo.com'],
            'outlook.com': ['outlok.com', 'outlook.co'],
            'hotmail.com': ['hotmal.com', 'hotmail.co'],
        }
        
        for correct_domain, typos in common_typos.items():
            for typo in typos:
                if email.endswith(f'@{typo}'):
                    suggestion = email.replace(f'@{typo}', f'@{correct_domain}')
                    suggestions.append(suggestion)
        
        return suggestions
    
    def _render_template_string(self, template_string: str, data: Dict[str, Any]) -> str:
        """Render template string with data"""
        try:
            template = self.jinja_env.from_string(template_string)
            return template.render(**data)
        except Exception:
            # Fallback to simple replacement
            result = template_string
            for key, value in data.items():
                placeholder = f'{{{{{key}}}}}'
                result = result.replace(placeholder, str(value))
            return result
    
    async def _process_email_queue(self):
        """Background email queue processor"""
        logger.info("Starting email queue processor...")
        self.is_processing = True
        
        while self.is_processing:
            try:
                # Process emails in batches
                batch_size = 10
                batch = []
                
                for _ in range(batch_size):
                    try:
                        email_data = await asyncio.wait_for(
                            self.email_queue.get(),
                            timeout=1.0
                        )
                        batch.append(email_data)
                    except asyncio.TimeoutError:
                        break
                
                if batch:
                    logger.info(f"Processing batch of {len(batch)} queued emails")
                    
                    # Send batch
                    batch_result = await self.send_bulk_emails(batch)
                    
                    # Update queue size
                    self.stats['queue_size'] = self.email_queue.qsize()
                    
                    if not batch_result.success:
                        logger.error(f"Batch processing failed: {batch_result.error}")
                
                # Sleep before next batch
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                logger.info("Email queue processor cancelled")
                break
            except Exception as e:
                logger.error(f"Email queue processor error: {str(e)}")
                await asyncio.sleep(10)  # Wait before retry
    
    def _update_statistics(self, email_type: str, success: bool, count: int = 1):
        """Update email statistics"""
        # Reset daily counter if new day
        today = datetime.now().date()
        if today != self.stats['last_reset']:
            self.stats['sent_today'] = 0
            self.stats['last_reset'] = today
        
        if success:
            self.stats['total_sent'] += count
            self.stats['sent_today'] += count
        else:
            self.stats['total_failed'] += count
        
        # Update by type
        if email_type not in self.stats['by_type']:
            self.stats['by_type'][email_type] = {
                'sent': 0,
                'failed': 0
            }
        
        if success:
            self.stats['by_type'][email_type]['sent'] += count
        else:
            self.stats['by_type'][email_type]['failed'] += count
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get email service statistics"""
        return {
            **self.stats,
            'timestamp': datetime.now().isoformat(),
            'templates_loaded': len(self.template_cache),
            'providers_configured': len(self.providers),
            'is_processing_queue': self.is_processing
        }
    
    async def stop(self):
        """Stop email service"""
        logger.info("Stopping email service...")
        self.is_processing = False
        
        # Process remaining queue
        remaining = self.stats['queue_size']
        if remaining > 0:
            logger.info(f"Processing {remaining} remaining emails in queue...")
            # In production, you might want to persist remaining emails
    
    def __del__(self):
        """Cleanup on deletion"""
        if self.is_processing:
            asyncio.create_task(self.stop())