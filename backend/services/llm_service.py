import os
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

class LLMService:
    NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
    DEFAULT_MODEL = "meta/llama-3.1-8b-instruct"

    @classmethod
    def get_api_key(cls):
        return os.environ.get("NVIDIA_API_KEY", "").strip()

    @classmethod
    def query(cls, messages, model=None, temperature=0.1, max_tokens=2048, json_response=False):
        api_key = cls.get_api_key()
        model = model or cls.DEFAULT_MODEL

        # Log query
        logger.info(f"Querying LLM model: {model} (JSON Mode: {json_response})")

        if not api_key:
            logger.warning("NVIDIA_API_KEY not found. Running in MOCK LLM Mode.")
            return cls._mock_response(messages, json_response)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        if json_response:
            payload["response_format"] = {"type": "json_object"}

        # Perform request with retries
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                # Use a shorter timeout to prevent Nginx 504 gateway timeout (max 10s)
                response = requests.post(cls.NVIDIA_URL, headers=headers, json=payload, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.info("LLM query completed successfully.")
                    return content
                elif response.status_code in [401, 403]:
                    logger.error(f"LLM Authentication Error: {response.status_code} - {response.text}")
                    break # Don't retry auth issues
                else:
                    logger.error(f"LLM API Error (Attempt {attempt+1}): {response.status_code} - {response.text}")
            except requests.exceptions.Timeout:
                logger.error(f"LLM Timeout (Attempt {attempt+1})")
                if attempt == max_attempts - 1:
                    break
            except Exception as e:
                logger.error(f"LLM Connection Error (Attempt {attempt+1}): {str(e)}")
                break # Don't retry general connection issues (like DNS or SSL errors)
        
        # Fallback to mock on failures
        logger.warning("LLM API failed or timed out. Falling back to Mock response.")
        return cls._mock_response(messages, json_response)

    @classmethod
    def _mock_response(cls, messages, json_response):
        """
        Generates mock responses simulating Llama model outputs for testing.
        """
        # Try to find user prompt context
        user_message = ""
        for m in reversed(messages):
            if m["role"] == "user":
                user_message = m["content"]
                break

        user_message_lower = user_message.lower()

        if json_response:
            # Check if this looks like a resume extraction prompt
            if "resume" in user_message_lower or "extract" in user_message_lower:
                return json.dumps({
                    "name": "Jane Doe",
                    "email": "jane.doe@example.com",
                    "phone": "+1-555-0199",
                    "skills": ["Python", "Django", "PostgreSQL", "Docker", "Git", "REST APIs"],
                    "experience": "5 years of experience building scalable backend services with Django.",
                    "education": "B.S. in Computer Science from Stanford University",
                    "score": 85,
                    "match_explanation": "Jane has solid Python and Django skills, with direct experience setting up PostgreSQL and Docker containers. She lacks Kubernetes which was preferred but has all key requirements."
                })
            # Check if this is an intent parser prompt
            elif "intent" in user_message_lower or "classify" in user_message_lower or "orchestrator" in user_message_lower:
                return json.dumps({
                    "intent": "conversational_reply",
                    "parameters": {}
                })
            # Default mock JSON
            return json.dumps({
                "candidate_name": "Mock Candidate",
                "score": 80,
                "matching_skills": ["Python", "Django"],
                "missing_skills": ["Kubernetes"],
                "recommendation": "Shortlist"
            })
        else:
            # Conversational text response
            if "schedule" in user_message_lower:
                return "I've processed your scheduling request. I can schedule an interview for the candidate via Google Calendar."
            elif "email" in user_message_lower:
                return "I can draft and send candidate notifications using SMTP. Please let me know who should receive it."
            elif "hello" in user_message_lower or "hi" in user_message_lower:
                return "Hello! I am your AI HR Assistant. How can I help you manage your candidates, jobs, and interviews today?"
            return f"I analyzed your request: '{user_message[:100]}'. I'm ready to perform recruiting actions, search the database, or schedule interviews."
