import os
import logging
import datetime
import random
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

class CalendarService:
    @classmethod
    def is_mock(cls):
        return os.environ.get("MOCK_CALENDAR", "True").lower() == "true"

    @classmethod
    def get_calendar_service(cls):
        """
        Initializes Google Calendar Client if credentials are provided.
        """
        credentials_json = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS", "")
        if not credentials_json or cls.is_mock():
            return None
        
        try:
            # Parse credentials string or check if it is a file path
            if os.path.exists(credentials_json):
                creds = service_account.Credentials.from_service_account_file(
                    credentials_json, scopes=['https://www.googleapis.com/auth/calendar']
                )
            else:
                info = json.loads(credentials_json)
                creds = service_account.Credentials.from_service_account_info(
                    info, scopes=['https://www.googleapis.com/auth/calendar']
                )
            
            service = build('calendar', 'v3', credentials=creds)
            return service
        except Exception as e:
            logger.error(f"Failed to load Google Calendar Credentials: {str(e)}")
            return None

    @classmethod
    def schedule_interview(cls, summary, description, start_time_str, attendee_email):
        """
        Schedules an interview event and returns (event_id, meeting_link).
        start_time_str should be ISO format (e.g. "2026-05-30T16:00:00")
        """
        service = cls.get_calendar_service()
        
        # Parse ISO datetime
        try:
            start_dt = datetime.datetime.fromisoformat(start_time_str)
        except ValueError:
            # Default to tomorrow if parsing fails
            start_dt = datetime.datetime.now() + datetime.timedelta(days=1)
            
        end_dt = start_dt + datetime.timedelta(hours=1)
        
        start_time_iso = start_dt.isoformat() + 'Z' if not start_dt.tzinfo else start_dt.isoformat()
        end_time_iso = end_dt.isoformat() + 'Z' if not end_dt.tzinfo else end_dt.isoformat()

        if not service:
            logger.info("Running in Mock Calendar mode. Simulating Google Calendar event.")
            # Generate a mock meeting link and event ID
            random_code = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=10))
            meet_link = f"https://meet.google.com/{random_code[:3]}-{random_code[3:7]}-{random_code[7:]}"
            mock_event_id = f"mock_event_{random.randint(100000, 999999)}"
            
            logger.info(f"Mock Event Created: {summary} for {attendee_email} at {start_time_iso}")
            logger.info(f"Mock Meet Link: {meet_link}")
            
            return mock_event_id, meet_link

        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time_iso,
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time_iso,
                'timeZone': 'UTC',
            },
            'attendees': [
                {'email': attendee_email},
            ],
            'conferenceData': {
                'createRequest': {
                    'requestId': f"req_{random.randint(100000, 999999)}",
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            }
        }

        try:
            logger.info(f"Creating Google Calendar event for {attendee_email}")
            event = service.events().insert(
                calendarId='primary', 
                body=event, 
                conferenceDataVersion=1
            ).execute()
            
            meeting_link = event.get('hangoutLink') or event.get('htmlLink')
            event_id = event.get('id')
            
            logger.info(f"Google Calendar event created successfully: {event_id}")
            return event_id, meeting_link
        except Exception as e:
            logger.error(f"Error calling Google Calendar API: {str(e)}")
            # Fallback to mock on API errors
            random_code = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=10))
            meet_link = f"https://meet.google.com/{random_code[:3]}-{random_code[3:7]}-{random_code[7:]}"
            return f"failed_event_{random.randint(1000, 9999)}", meet_link
