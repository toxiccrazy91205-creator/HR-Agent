import logging
from api.models import Candidate, EmailLog
from services.email_service import EmailService
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

class EmailAgent:
    @classmethod
    def generate_email_body(cls, candidate_name, status, job_title="Software Engineer"):
        """
        Uses LLM to draft a personalized email based on candidate status.
        """
        system_prompt = (
            "You are a professional HR assistant. Draft a polite, clear, and professional email "
            "to a job candidate. Do not include subject line or placeholders. Write the body directly. "
            "Include friendly greetings, clear next steps, and sign off as 'AI HR Operations Team'."
        )

        user_content = f"Write a candidate email for: {candidate_name}. Status: {status}. Job Title: {job_title}."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        logger.info(f"Drafting LLM email for {candidate_name} with status {status}")
        return LLMService.query(messages, temperature=0.5)

    @classmethod
    def send_templated_emails(cls, target_group, name_query=None):
        """
        Handles sending emails to:
        - specific candidate (name_query)
        - group of candidates ('low_score' or 'shortlisted')
        """
        candidates = []
        status_label = "Shortlisted"
        
        if name_query:
            logger.info(f"Targeting specific candidate email to: {name_query}")
            cand = Candidate.objects.filter(name__icontains=name_query).first()
            if cand:
                candidates = [cand]
                status_label = cand.status
            else:
                return f"I couldn't find a candidate with the name '{name_query}' to send an email to."
        elif target_group == 'low_score':
            # Target candidates with score < 60 and not already rejected
            candidates = Candidate.objects.filter(score__lt=60).exclude(status='Rejected')
            status_label = "Rejected"
        elif target_group == 'shortlisted':
            candidates = Candidate.objects.filter(status='Shortlisted')
            status_label = "Shortlisted"

        if not candidates:
            return "No candidates met the criteria for sending emails."

        results = []
        for cand in candidates:
            # 1. Draft body with LLM
            body = cls.generate_email_body(cand.name, status_label)
            subject = f"Update on your application - {status_label}"
            
            # 2. Send via SMTP service
            success = EmailService.send_candidate_email(cand.id, subject, body)
            
            # 3. Update candidate status if rejecting
            if status_label == "Rejected" and success:
                cand.status = 'Rejected'
                cand.save()
                
            results.append(f"- **{cand.name}** ({cand.email or 'No email'}) - {'Sent' if success else 'Failed'}")

        response = f"### Email Automation Summary\n\n"
        response += f"Processed {len(results)} email(s) for group: `{target_group or name_query}`\n\n"
        response += "\n".join(results)
        
        return response
