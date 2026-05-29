import re
import json
import fitz  # PyMuPDF
import logging
from .llm_service import LLMService

logger = logging.getLogger(__name__)

# Initialize nlp as None, loaded dynamically if needed
nlp = None

class ResumeParserService:
    @classmethod
    def extract_text_from_pdf(cls, file_path):
        """
        Extracts all raw text from a PDF file using PyMuPDF.
        """
        logger.info(f"Extracting text from PDF: {file_path}")
        text = ""
        try:
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text()
            doc.close()
        except Exception as e:
            logger.error(f"Error reading PDF {file_path}: {str(e)}")
            raise e
        return text

    @classmethod
    def clean_text(cls, text):
        """
        Cleans extracted text by stripping double spaces, tabs, and unnecessary characters.
        """
        if not text:
            return ""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Optionally process through spaCy loaded dynamically
        global nlp
        if nlp is None:
            try:
                import spacy
                nlp = spacy.load("en_core_web_sm")
            except Exception as e:
                logger.warning(f"Could not load spaCy: {str(e)}")
                nlp = None

        if nlp:
            doc = nlp(text[:100000])  # Cap size to prevent spaCy overhead
            # Join tokens that are not punctuation or spaces
            cleaned = " ".join([token.text for token in doc if not token.is_space])
            return cleaned
        return text

    @classmethod
    def regex_extract_email_phone(cls, text):
        """
        Quick regex extraction for email and phone numbers as backups.
        """
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        phone_pattern = r'\+?\d[\d\-\s\(\)]{7,15}\d'

        emails = re.findall(email_pattern, text)
        phones = re.findall(phone_pattern, text)

        email = emails[0] if emails else None
        phone = phones[0] if phones else None

        return email, phone

    @classmethod
    def parse_resume_with_llm(cls, resume_text, job_title=None, job_description=None):
        """
        Sends resume text and job description to the LLM to get a structured JSON extraction and score.
        """
        job_title = job_title or "General Software Engineer"
        job_description = job_description or "General software engineering role requiring programming, system design, and collaboration skills."

        system_prompt = (
            "You are an expert HR recruitment agent. Your task is to extract information from a resume "
            "and compare it to a Job Description to evaluate candidate suitability. "
            "Return the output STRICTLY as a JSON object. Do not include any markdown or code blocks except the JSON itself. "
            "The JSON must have the following keys:\n"
            "- name (string, candidate full name)\n"
            "- email (string, email address)\n"
            "- phone (string, phone number)\n"
            "- skills (list of strings, technical/soft skills)\n"
            "- experience (string, brief summary of work experience)\n"
            "- education (string, education history summary)\n"
            "- score (integer from 0 to 100, indicating how well the candidate matches the job description)\n"
            "- match_explanation (string, a paragraph detailing why the candidate received this score and whether they are suitable)"
        )

        user_content = (
            f"=== JOB DEFINITION ===\n"
            f"Title: {job_title}\n"
            f"Description: {job_description}\n\n"
            f"=== RESUME CONTENT ===\n"
            f"{resume_text[:8000]}"  # Limit to avoid token capacity issues
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        logger.info(f"Parsing resume via LLM for job: {job_title}")
        raw_response = LLMService.query(messages, json_response=True)
        
        # Clean response string of markdown block delimiters if present
        clean_res = raw_response.strip()
        if clean_res.startswith("```json"):
            clean_res = clean_res[7:]
        if clean_res.endswith("```"):
            clean_res = clean_res[:-3]
        clean_res = clean_res.strip()

        try:
            parsed_json = json.loads(clean_res)
            
            # Use regex backup if LLM missed email/phone
            reg_email, reg_phone = cls.regex_extract_email_phone(resume_text)
            if not parsed_json.get("email") and reg_email:
                parsed_json["email"] = reg_email
            if not parsed_json.get("phone") and reg_phone:
                parsed_json["phone"] = reg_phone
                
            return parsed_json
        except Exception as e:
            logger.error(f"Failed to parse LLM JSON response: {str(e)}. Raw response was: {raw_response}")
            # Return basic schema on failure
            reg_email, reg_phone = cls.regex_extract_email_phone(resume_text)
            return {
                "name": "Unknown",
                "email": reg_email or "",
                "phone": reg_phone or "",
                "skills": [],
                "experience": "",
                "education": "",
                "score": 0,
                "match_explanation": "Failed to parse LLM structured data."
            }
