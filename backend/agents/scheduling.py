import datetime
import logging
import json
from django.utils import timezone
from api.models import Candidate, Interview
from services.calendar_service import CalendarService
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

class SchedulingAgent:
    @classmethod
    def parse_datetime_with_llm(cls, time_phrase):
        """
        Translates a natural language phrase (e.g. 'tomorrow at 4PM') to ISO format.
        """
        ref_time = timezone.now()
        ref_time_str = ref_time.strftime("%A, %Y-%m-%d %H:%M:%S UTC")

        system_prompt = (
            "You are a helpful assistant that parses natural language date/time expressions "
            "and converts them into ISO 8601 formatting (YYYY-MM-DDTHH:MM:SS).\n"
            "Reference Current Time: " + ref_time_str + "\n"
            "Return output STRICTLY as a JSON object with keys:\n"
            "- start_time: (string, YYYY-MM-DDTHH:MM:SS format, assume 24-hour time)\n"
            "- error: (string, if date/time could not be resolved, else null)\n"
        )

        user_content = f"Parse the following phrase: '{time_phrase}'"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        try:
            raw_response = LLMService.query(messages, json_response=True)
            # Remove possible code block wrappers
            clean_res = raw_response.strip()
            if clean_res.startswith("```json"):
                clean_res = clean_res[7:]
            if clean_res.endswith("```"):
                clean_res = clean_res[:-3]
            clean_res = clean_res.strip()
            
            data = json.loads(clean_res)
            
            if data.get("error"):
                logger.warning(f"LLM failed to parse datetime: {data['error']}")
                return None
                
            return data.get("start_time")
        except Exception as e:
            logger.error(f"Error parsing date with LLM: {str(e)}")
            # Default to tomorrow at 10 AM
            tomorrow = datetime.date.today() + datetime.timedelta(days=1)
            return f"{tomorrow.isoformat()}T10:00:00"

    @classmethod
    def schedule(cls, candidate_name_query, time_phrase):
        """
        Locates the candidate, parses the time, calls the Calendar Service, and updates the database.
        """
        logger.info(f"Scheduling request: Candidate '{candidate_name_query}' at '{time_phrase}'")
        
        # 1. Find Candidate
        cand = Candidate.objects.filter(name__icontains=candidate_name_query).first()
        if not cand:
            return f"I couldn't find any candidate matching the name '{candidate_name_query}' to schedule an interview for."

        # 2. Parse Date/Time
        iso_time = cls.parse_datetime_with_llm(time_phrase)
        if not iso_time:
            return f"I wasn't able to understand the requested time: '{time_phrase}'. Could you please be more specific?"

        try:
            # 3. Create Calendar Event
            summary = f"Interview with {cand.name} for Job Opening"
            description = (
                f"Autonomous HR Assistant Scheduled Interview\n"
                f"Candidate: {cand.name}\n"
                f"Email: {cand.email or 'N/A'}\n"
                f"Phone: {cand.phone or 'N/A'}\n"
            )
            
            event_id, meet_link = CalendarService.schedule_interview(
                summary=summary,
                description=description,
                start_time_str=iso_time,
                attendee_email=cand.email or "recipient@example.com"
            )

            # 4. Save to Database
            parsed_dt = datetime.datetime.fromisoformat(iso_time)
            interview = Interview.objects.create(
                candidate=cand,
                scheduled_time=parsed_dt,
                meeting_link=meet_link,
                google_event_id=event_id,
                status='Pending'
            )

            # Update candidate status
            cand.status = 'Interview Scheduled'
            cand.save()

            formatted_time = parsed_dt.strftime("%A, %B %d, %Y at %I:%M %p")
            response = (
                f"### Interview Successfully Scheduled! 🎉\n\n"
                f"* **Candidate:** {cand.name}\n"
                f"* **Scheduled Time:** {formatted_time}\n"
                f"* **Google Meet Link:** [{meet_link}]({meet_link})\n"
                f"* **Calendar Event ID:** `{event_id}`\n\n"
                f"An email invitation has been queued for {cand.name} ({cand.email or 'no email recorded'})."
            )
            return response
        except Exception as e:
            logger.error(f"Failed to schedule interview: {str(e)}")
            return f"An error occurred while scheduling the interview: {str(e)}"

    @classmethod
    def get_interviews_list(cls):
        """
        Retrieves all active scheduled interviews.
        """
        interviews = Interview.objects.all().order_by('-scheduled_time')[:10]
        if not interviews.exists():
            return "There are no interviews currently scheduled."
            
        response = "### Scheduled Interviews\n\n"
        for inter in interviews:
            time_str = inter.scheduled_time.strftime("%Y-%m-%d %H:%M")
            response += f"- **{inter.candidate.name}** - `{time_str}` - Status: `{inter.status}`\n"
            if inter.meeting_link:
                response += f"  - [Meeting Link]({inter.meeting_link})\n"
        return response
