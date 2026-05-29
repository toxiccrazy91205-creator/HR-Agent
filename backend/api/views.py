import logging
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from .models import JobRole, Candidate, Interview, EmailLog, ChatHistory
from .serializers import (
    JobRoleSerializer, CandidateSerializer, InterviewSerializer, 
    EmailLogSerializer, ChatHistorySerializer
)
from agents.orchestrator import AgentOrchestrator
from tasks.async_tasks import process_resume_task, send_email_async_task
from agents.scheduling import SchedulingAgent
from agents.email_agent import EmailAgent

logger = logging.getLogger(__name__)

class JobRoleViewSet(viewsets.ModelViewSet):
    queryset = JobRole.objects.all().order_by('-created_at')
    serializer_class = JobRoleSerializer

class CandidateViewSet(viewsets.ModelViewSet):
    queryset = Candidate.objects.all().order_by('-score', '-created_at')
    serializer_class = CandidateSerializer

    @action(detail=True, methods=['post'], url_path='re-evaluate')
    def re_evaluate(self, request, pk=None):
        """
        Triggers parsing task again.
        """
        candidate = self.get_object()
        job_role_id = request.data.get('job_role_id')
        process_resume_task.delay(str(candidate.id), job_role_id)
        return Response({"message": "Re-evaluation task scheduled."}, status=status.HTTP_202_ACCEPTED)

class InterviewViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Interview.objects.all().order_by('-scheduled_time')
    serializer_class = InterviewSerializer

class EmailLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EmailLog.objects.all().order_by('-sent_at')
    serializer_class = EmailLogSerializer

class ChatHistoryViewSet(viewsets.ModelViewSet):
    queryset = ChatHistory.objects.all().order_by('timestamp')
    serializer_class = ChatHistorySerializer

@api_view(['POST'])
def chat_view(request):
    """
    Handles HR messaging. Uses orchestrator to parse, run tool/agents, and return AI response.
    """
    message_text = request.data.get("message")
    session_id = request.data.get("session_id", "default")

    if not message_text:
        return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = AgentOrchestrator.process_message(message_text, session_id=session_id)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def upload_resume_view(request):
    """
    Handles file upload of multiple PDFs.
    Creates Candidate records and triggers async Celery task for processing.
    """
    files = request.FILES.getlist('resumes')
    job_role_id = request.data.get('job_role_id')

    if not files:
        return Response({"error": "No resume files uploaded"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        candidates_created = []
        for file in files:
            # File validation
            if not file.name.lower().endswith('.pdf'):
                logger.warning(f"Rejected file {file.name}: only PDF allowed.")
                continue

            # Create Candidate record
            candidate = Candidate.objects.create(
                name=file.name.replace(".pdf", "").replace(".PDF", ""),
                resume_file=file,
                status='New'
            )
            candidates_created.append({
                "id": str(candidate.id),
                "filename": file.name
            })

            # Enqueue parsing task
            process_resume_task.delay(str(candidate.id), job_role_id)

        return Response({
            "message": f"Successfully uploaded {len(candidates_created)} resume(s). Parsing initiated in the background.",
            "candidates": candidates_created
        }, status=status.HTTP_202_ACCEPTED)

    except Exception as e:
        logger.error(f"Error uploading resumes: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def schedule_interview_view(request):
    """
    Explicit endpoint for scheduling an interview.
    """
    candidate_name = request.data.get("candidate_name")
    time_phrase = request.data.get("time_phrase")

    if not candidate_name or not time_phrase:
        return Response({"error": "candidate_name and time_phrase are required"}, status=status.HTTP_400_BAD_REQUEST)

    result = SchedulingAgent.schedule(candidate_name, time_phrase)
    return Response({"result": result}, status=status.HTTP_200_OK)

@api_view(['POST'])
def send_email_view(request):
    """
    Explicit endpoint for sending emails.
    """
    target_group = request.data.get("target_group")
    candidate_name = request.data.get("candidate_name")

    if not target_group and not candidate_name:
        return Response({"error": "target_group or candidate_name is required"}, status=status.HTTP_400_BAD_REQUEST)

    result = EmailAgent.send_templated_emails(target_group, candidate_name)
    return Response({"result": result}, status=status.HTTP_200_OK)
