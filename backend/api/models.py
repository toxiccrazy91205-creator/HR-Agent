import uuid
from django.db import models

class JobRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    required_skills = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Candidate(models.Model):
    STATUS_CHOICES = [
        ('New', 'New'),
        ('Shortlisted', 'Shortlisted'),
        ('Interview Scheduled', 'Interview Scheduled'),
        ('Rejected', 'Rejected'),
        ('Offered', 'Offered'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    resume_text = models.TextField(null=True, blank=True)
    extracted_skills = models.JSONField(default=list, null=True, blank=True)
    score = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='New')
    match_explanation = models.TextField(null=True, blank=True)
    resume_file = models.FileField(upload_to='resumes/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or f"Candidate {self.id}"

class Interview(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Rescheduled', 'Rescheduled'),
        ('Cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='interviews')
    scheduled_time = models.DateTimeField()
    meeting_link = models.URLField(max_length=500, null=True, blank=True)
    google_event_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Interview with {self.candidate.name} at {self.scheduled_time}"

class EmailLog(models.Model):
    STATUS_CHOICES = [
        ('Sent', 'Sent'),
        ('Failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.SET_NULL, null=True, blank=True, related_name='emails')
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Sent')
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Email to {self.candidate.name if self.candidate else 'Unknown'} - {self.subject}"

class ChatHistory(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_id = models.CharField(max_length=255, default='default')
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    message = models.TextField()
    tool_execution = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role.capitalize()}: {self.message[:50]}..."
