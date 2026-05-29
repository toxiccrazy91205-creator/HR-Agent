from rest_framework import serializers
from .models import JobRole, Candidate, Interview, EmailLog, ChatHistory

class JobRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobRole
        fields = '__all__'

class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = '__all__'

class InterviewSerializer(serializers.ModelSerializer):
    candidate_name = serializers.ReadOnlyField(source='candidate.name')

    class Meta:
        model = Interview
        fields = '__all__'

class EmailLogSerializer(serializers.ModelSerializer):
    candidate_name = serializers.ReadOnlyField(source='candidate.name')

    class Meta:
        model = EmailLog
        fields = '__all__'

class ChatHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatHistory
        fields = '__all__'
