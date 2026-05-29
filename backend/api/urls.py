from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    JobRoleViewSet, CandidateViewSet, InterviewViewSet, 
    EmailLogViewSet, ChatHistoryViewSet, chat_view, 
    upload_resume_view, schedule_interview_view, send_email_view
)

router = DefaultRouter()
router.register(r'job-roles', JobRoleViewSet, basename='jobrole')
router.register(r'candidates', CandidateViewSet, basename='candidate')
router.register(r'interviews', InterviewViewSet, basename='interview')
router.register(r'email-logs', EmailLogViewSet, basename='emaillog')
router.register(r'chat-history', ChatHistoryViewSet, basename='chathistory')

urlpatterns = [
    path('', include(router.urls)),
    path('chat/', chat_view, name='chat'),
    path('upload-resume/', upload_resume_view, name='upload-resume'),
    path('schedule-interview/', schedule_interview_view, name='schedule-interview'),
    path('send-email/', send_email_view, name='send-email'),
]
