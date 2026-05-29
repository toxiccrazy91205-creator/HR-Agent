import os
import smtplib
import logging
from django.core.mail import send_mail
from django.conf import settings
from api.models import EmailLog, Candidate

logger = logging.getLogger(__name__)

class EmailService:
    @classmethod
    def get_smtp_config(cls):
        return {
            "host": os.environ.get("SMTP_HOST", ""),
            "port": int(os.environ.get("SMTP_PORT", 587)),
            "user": os.environ.get("SMTP_USER", ""),
            "password": os.environ.get("SMTP_PASSWORD", "")
        }

    @classmethod
    def send_candidate_email(cls, candidate_id, subject, body):
        """
        Sends email to candidate and logs in the database.
        """
        candidate = None
        recipient = "unknown@example.com"
        
        if candidate_id:
            try:
                candidate = Candidate.objects.get(id=candidate_id)
                recipient = candidate.email or recipient
            except Candidate.DoesNotExist:
                logger.error(f"Candidate {candidate_id} not found for email logging.")

        config = cls.get_smtp_config()
        
        # Check if email config is present
        if not config["host"] or not config["user"]:
            logger.warning("SMTP Configuration missing. Simulating email send (Mock Mode).")
            # Write to EmailLog with status Sent (mocked)
            log = EmailLog.objects.create(
                candidate=candidate,
                subject=subject,
                body=body,
                status='Sent'
            )
            logger.info(f"Mock Email Sent to {recipient}:\nSubject: {subject}\nBody: {body}")
            return True

        # Send actual email using Django's SMTP backend or custom connection
        try:
            # Dynamically override settings if configured via environment variables
            # standard django settings can be configured at runtime
            settings.EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
            settings.EMAIL_HOST = config["host"]
            settings.EMAIL_PORT = config["port"]
            settings.EMAIL_HOST_USER = config["user"]
            settings.EMAIL_HOST_PASSWORD = config["password"]
            settings.EMAIL_USE_TLS = True
            
            logger.info(f"Sending email to {recipient} via {config['host']}")
            
            send_mail(
                subject,
                body,
                config["user"],
                [recipient],
                fail_silently=False,
            )

            # Log to DB
            EmailLog.objects.create(
                candidate=candidate,
                subject=subject,
                body=body,
                status='Sent'
            )
            logger.info(f"Email sent successfully to {recipient}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {str(e)}")
            EmailLog.objects.create(
                candidate=candidate,
                subject=subject,
                body=body,
                status='Failed'
            )
            return False
