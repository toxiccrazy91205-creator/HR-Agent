import logging
from celery import shared_task
from django.db import transaction
from api.models import Candidate, JobRole
from services.resume_parser import ResumeParserService
from services.vector_service import VectorService
from services.email_service import EmailService

logger = logging.getLogger(__name__)

@shared_task
def process_resume_task(candidate_id, job_role_id=None):
    """
    Asynchronously parses a resume PDF, clean text, evaluates against job role using LLM,
    updates candidate info, and indexes embedding in FAISS.
    """
    logger.info(f"Celery processing resume for candidate ID: {candidate_id}")
    try:
        candidate = Candidate.objects.get(id=candidate_id)
        if not candidate.resume_file:
            logger.error(f"Candidate {candidate_id} does not have a resume file uploaded.")
            return False

        # 1. Extract text from PDF
        pdf_path = candidate.resume_file.path
        raw_text = ResumeParserService.extract_text_from_pdf(pdf_path)
        cleaned_text = ResumeParserService.clean_text(raw_text)

        # 2. Get Job Role Context
        job_title = "General Software Engineer"
        job_desc = ""
        if job_role_id:
            try:
                job = JobRole.objects.get(id=job_role_id)
                job_title = job.title
                job_desc = job.description
            except JobRole.DoesNotExist:
                logger.warning(f"Job Role {job_role_id} not found. Evaluation will proceed with default values.")

        # 3. Analyze and Parse Resume metadata via LLM
        parsed_data = ResumeParserService.parse_resume_with_llm(
            resume_text=cleaned_text,
            job_title=job_title,
            job_description=job_desc
        )

        # 4. Save updates atomically to database
        with transaction.atomic():
            candidate.resume_text = cleaned_text
            candidate.name = parsed_data.get("name") or candidate.name or "Unknown Candidate"
            candidate.email = parsed_data.get("email") or candidate.email
            candidate.phone = parsed_data.get("phone") or candidate.phone
            candidate.extracted_skills = parsed_data.get("skills") or []
            candidate.score = parsed_data.get("score") or 0
            candidate.match_explanation = parsed_data.get("match_explanation") or ""
            
            # Auto status assignment
            if candidate.score >= 60:
                candidate.status = "Shortlisted"
            else:
                candidate.status = "New"
                
            candidate.save()

        # 5. Ingest into local FAISS Vector database
        # We index the candidate name + skills + experience for semantic search match
        skills_str = ", ".join(candidate.extracted_skills)
        text_to_embed = f"Candidate Name: {candidate.name}. Skills: {skills_str}. Experience: {parsed_data.get('experience')}."
        VectorService.add_candidate(candidate.id, text_to_embed)

        logger.info(f"Successfully processed and indexed candidate: {candidate.name}")
        return True
    except Exception as e:
        logger.error(f"Failed processing task for candidate {candidate_id}: {str(e)}")
        return False

@shared_task
def send_email_async_task(candidate_id, subject, body):
    """
    Celery task to send emails asynchronously.
    """
    logger.info(f"Sending email task for candidate ID: {candidate_id}")
    return EmailService.send_candidate_email(candidate_id, subject, body)
