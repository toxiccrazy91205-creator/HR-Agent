import os
import json
import logging
from django.utils import timezone
from api.models import Candidate, JobRole, Interview
from services.llm_service import LLMService
from .recruitment import RecruitmentAgent
from .scheduling import SchedulingAgent
from .email_agent import EmailAgent
from .memory import MemoryAgent

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    @classmethod
    def process_message(cls, message_text, session_id="default"):
        """
        Receives HR user input, runs classification intent tool, routes to target agent,
        constructs response, and updates chat memory.
        """
        logger.info(f"Orchestrator processing message for session '{session_id}': '{message_text}'")
        
        # 1. Retrieve memory context
        history_context = MemoryAgent.get_conversation_context(session_id, limit=6)
        
        # Save user message immediately to DB
        MemoryAgent.save_chat_message(role='user', message=message_text, session_id=session_id)

        # 2. Intent Classification and Entity Extraction via LLM
        system_prompt = (
            "You are the central orchestrator for an Autonomous HR Agent System.\n"
            "Analyze the HR user's input and classify it into one of these intents:\n"
            "- analyze_resumes: User wants to extract, parse, or evaluate uploaded resumes for a job position.\n"
            "- search_candidates: User is explicitly searching/filtering candidates (e.g. 'Who knows Django?', 'Find Python engineers').\n"
            "- schedule_interview: User wants to schedule or reschedule an interview (e.g. 'Schedule Rahul tomorrow at 4pm').\n"
            "- send_email: User wants to send automated emails (rejection/shortlist/follow-up) to candidates.\n"
            "- conversational_reply: General greeting, candidate comparisons, explanation of decisions, or questions about database state (e.g. 'Compare Neha and Priya', 'Show me the React candidate from yesterday').\n\n"
            "Return output STRICTLY as a JSON object with keys:\n"
            "- intent: (one of the 5 strings above)\n"
            "- parameters: (dict containing extracted parameters such as 'candidate_name', 'time_phrase', 'job_role_title', 'query', 'target_group')\n"
        )

        user_content = (
            f"=== CONVERSATION HISTORY ===\n{history_context}\n\n"
            f"=== CURRENT USER MESSAGE ===\n{message_text}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        intent = "conversational_reply"
        params = {}
        tool_execution_logs = []

        try:
            raw_response = LLMService.query(messages, json_response=True)
            clean_res = raw_response.strip()
            if clean_res.startswith("```json"):
                clean_res = clean_res[7:]
            if clean_res.endswith("```"):
                clean_res = clean_res[:-3]
            clean_res = clean_res.strip()
            
            data = json.loads(clean_res)
            intent = data.get("intent", "conversational_reply")
            params = data.get("parameters", {})
            logger.info(f"Classified Intent: {intent}, Params: {params}")
        except Exception as e:
            logger.error(f"Error parsing orchestrator classification: {str(e)}. Raw: {raw_response}")

        # 3. Route to agents
        response_text = ""

        if intent == "analyze_resumes":
            tool_execution_logs.append("🔍 Ingesting newly uploaded resumes...")
            job_title = params.get("job_role_title", "")
            # Find candidate files with no scores yet to run matching
            unparsed = Candidate.objects.filter(score__isnull=True)
            if unparsed.exists():
                tool_execution_logs.append(f"🤖 Evaluating {unparsed.count()} candidates against role: {job_title or 'active role'}...")
                # In real flow, resume processing runs asynchronously on upload.
                # Here we can trigger ranking for them
                from tasks.async_tasks import process_resume_task
                job_role = JobRole.objects.filter(title__icontains=job_title).first() if job_title else JobRole.objects.first()
                for cand in unparsed:
                    process_resume_task.delay(str(cand.id), str(job_role.id) if job_role else None)
                response_text = f"I have scheduled background tasks to analyze {unparsed.count()} candidates against the '{job_role.title if job_role else 'specified'} role'. They will appear in the dashboard once completed."
            else:
                response_text = "All uploaded resumes have already been parsed. Please upload new resumes in the file upload panel."

        elif intent == "search_candidates":
            query = params.get("query") or message_text
            tool_execution_logs.append(f"🔍 Searching vector database for query: '{query}'...")
            response_text = RecruitmentAgent.search(query)

        elif intent == "schedule_interview":
            cand_name = params.get("candidate_name")
            time_phrase = params.get("time_phrase")
            
            if not cand_name or not time_phrase:
                # LLM failed to extract parameters, let LLM ask for details
                intent = "conversational_reply"
            else:
                tool_execution_logs.append(f"📅 Requesting Google Calendar API schedule for {cand_name}...")
                response_text = SchedulingAgent.schedule(cand_name, time_phrase)

        elif intent == "send_email":
            target_group = params.get("target_group")
            cand_name = params.get("candidate_name")
            
            tool_execution_logs.append(f"✉️ Composing customized emails for: {cand_name or target_group}...")
            response_text = EmailAgent.send_templated_emails(target_group, cand_name)

        # Fallback to conversational response with DB knowledge context
        if intent == "conversational_reply" or not response_text:
            tool_execution_logs.append("🧠 Recalling context & database metrics...")
            response_text = cls._generate_conversational_response(message_text, history_context)

        # 4. Save assistant response and tool execution logs to DB
        MemoryAgent.save_chat_message(
            role='assistant', 
            message=response_text, 
            session_id=session_id, 
            tool_execution={"logs": tool_execution_logs}
        )

        return {
            "response": response_text,
            "logs": tool_execution_logs
        }

    @classmethod
    def _generate_conversational_response(cls, user_message, history_context):
        """
        Feeds database stats and conversation history to the LLM to get a contextual reply.
        """
        # Collect context metrics to feed the LLM
        candidates_count = Candidate.objects.count()
        interviews_count = Interview.objects.count()
        recent_candidates = list(Candidate.objects.order_by('-created_at')[:5].values('name', 'score', 'status'))
        recent_interviews = list(Interview.objects.order_by('-scheduled_time')[:3].values('candidate__name', 'scheduled_time', 'status'))

        db_context = (
            f"=== DATABASE CURRENT METRICS ===\n"
            f"- Total Candidates: {candidates_count}\n"
            f"- Scheduled Interviews: {interviews_count}\n"
            f"- Recent Candidates: {json.dumps(recent_candidates)}\n"
            f"- Upcoming Interviews: {json.dumps(recent_interviews, default=str)}\n"
        )

        system_prompt = (
            "You are 'HR-Bot', an intelligent, conversational Autonomous HR AI Assistant.\n"
            "You help HR schedule interviews, analyze candidate skills, write emails, and check dashboard state.\n"
            "Use the provided Database Metrics and Conversation History to answer the HR User's query.\n"
            "Always be helpful, professional, and explain details clearly using markdown formatting.\n"
            "If the user asks for comparison or details of specific candidates, search candidate lists in the metrics."
        )

        user_content = (
            f"{db_context}\n\n"
            f"=== CONVERSATION HISTORY ===\n{history_context}\n\n"
            f"=== CURRENT USER MESSAGE ===\n{user_message}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        return LLMService.query(messages, temperature=0.5)
