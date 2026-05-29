import os
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from api.models import JobRole, Candidate, Interview, EmailLog

class Command(BaseCommand):
    help = 'Seeds the database with job roles, candidates, and interviews for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force seeding even if data already exists',
        )

    def handle(self, *args, **options):
        if not options.get('force') and JobRole.objects.exists():
            self.stdout.write("Database already has JobRole data. Skipping seeding. Use --force to override.")
            return

        self.stdout.write("Seeding database...")

        # 1. Clear existing data to avoid duplicates
        Interview.objects.all().delete()
        Candidate.objects.all().delete()
        JobRole.objects.all().delete()
        EmailLog.objects.all().delete()

        self.stdout.write("Cleared existing data.")

        # 2. Create Job Roles
        role_backend = JobRole.objects.create(
            title="Senior Python Backend Developer",
            description="Looking for a Python Developer experienced with Django, Celery, Redis, and PostgreSQL. Experience with Docker and microservices architecture is a plus.",
            required_skills=["Python", "Django", "Celery", "Redis", "PostgreSQL", "Docker"]
        )

        role_frontend = JobRole.objects.create(
            title="React Frontend Developer",
            description="We are seeking a Frontend Engineer skilled in React, TypeScript, HTML5, CSS3, and modern UI design. Experience with responsive layouts and state management is required.",
            required_skills=["React", "TypeScript", "HTML5", "CSS", "Tailwind"]
        )

        role_ai = JobRole.objects.create(
            title="AI / LLM Integration Engineer",
            description="Seeking a software developer to build applications integrating LLMs (e.g. OpenAI, Nvidia NIM) and Vector Databases (FAISS, Chroma). Experience with Python and prompt engineering is essential.",
            required_skills=["Python", "LLMs", "Vector Databases", "Prompt Engineering", "Git"]
        )

        self.stdout.write("Created 3 Job Roles.")

        # 3. Create Candidates
        # Make a dummy resume file on disk inside the media folder
        media_resumes_dir = os.path.join(settings.MEDIA_ROOT, 'resumes')
        os.makedirs(media_resumes_dir, exist_ok=True)
        dummy_file_path = os.path.join(media_resumes_dir, 'seeded_dummy.pdf')
        if not os.path.exists(dummy_file_path):
            with open(dummy_file_path, 'w') as f:
                f.write("%PDF-1.4 ... Dummy resume content ...")

        # Candidate A: Backend match
        cand_a = Candidate.objects.create(
            name="Alice Smith",
            email="alice.smith@example.com",
            phone="+1-555-0101",
            resume_text="Senior Python developer with 6 years of experience building web APIs with Django and Flask. Experienced in task queues with Celery and Redis. Proficient in database optimization for PostgreSQL.",
            extracted_skills=["Python", "Django", "Celery", "Redis", "PostgreSQL", "REST APIs"],
            score=88,
            status="Shortlisted",
            match_explanation="Alice is an excellent fit for the Senior Python role. She has direct production experience with all key tools in our stack (Django, Celery, Redis, PostgreSQL) and has worked on large backend architectures.",
            resume_file="resumes/seeded_dummy.pdf"
        )

        # Candidate B: Frontend match
        cand_b = Candidate.objects.create(
            name="Bob Jones",
            email="bob.jones@example.com",
            phone="+1-555-0102",
            resume_text="Frontend engineer focused on building React apps. Strong experience in TypeScript and state management (Redux, Zustand). Proficient with HTML, CSS, and Tailwind CSS.",
            extracted_skills=["React", "TypeScript", "HTML", "CSS", "Zustand"],
            score=78,
            status="Shortlisted",
            match_explanation="Bob has strong frontend fundamentals and React/TypeScript expertise. He matches the React position well, though he lacks specific Tailwind experience on his resume (has basic CSS).",
            resume_file="resumes/seeded_dummy.pdf"
        )

        # Candidate C: AI match
        cand_c = Candidate.objects.create(
            name="Charlie Brown",
            email="charlie.brown@example.com",
            phone="+1-555-0103",
            resume_text="Software engineer with a focus on AI integrations. Built multiple agentic workflows using OpenAI API and LangChain. Set up vector indexing with FAISS and Chroma DB. Strong Python developer.",
            extracted_skills=["Python", "LLMs", "Vector Databases", "LangChain", "Chroma DB"],
            score=92,
            status="Interview Scheduled",
            match_explanation="Charlie has outstanding experience building LLM integrations and agentic search workflows. His vector database skill set aligns perfectly with our AI integration requirements.",
            resume_file="resumes/seeded_dummy.pdf"
        )

        # Candidate D: Rejected Candidate
        cand_d = Candidate.objects.create(
            name="Diana Prince",
            email="diana.prince@example.com",
            phone="+1-555-0104",
            resume_text="Graphic designer looking to transition to software. Completed a basic HTML and CSS bootcamp. Basic familiarity with JavaScript.",
            extracted_skills=["HTML", "CSS", "Photoshop", "Illustrator"],
            score=35,
            status="Rejected",
            match_explanation="Diana's profile is primarily focused on design. She lacks the necessary backend or frontend engineering experience for our current technical job openings.",
            resume_file="resumes/seeded_dummy.pdf"
        )

        # Candidate E: New Candidate
        cand_e = Candidate.objects.create(
            name="David Miller",
            email="david.miller@example.com",
            phone="+1-555-0105",
            resume_text="Python Backend developer. Good knowledge of REST APIs and Flask. Familiar with Postgres database.",
            extracted_skills=["Python", "Flask", "PostgreSQL", "Git"],
            score=58,
            status="New",
            match_explanation="David is a solid mid-level developer. He knows Python and PostgreSQL, but has no experience with Django or Celery which are required for the senior backend role.",
            resume_file="resumes/seeded_dummy.pdf"
        )

        self.stdout.write("Created 5 Candidates.")

        # 4. Create Interviews
        # Tomorrow at 2 PM
        tomorrow = timezone.now().replace(hour=14, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        Interview.objects.create(
            candidate=cand_c,
            scheduled_time=tomorrow,
            meeting_link="https://meet.google.com/abc-defg-hij",
            status="Pending"
        )

        # Next week at 10 AM (completed)
        last_week = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0) - datetime.timedelta(days=3)
        Interview.objects.create(
            candidate=cand_a,
            scheduled_time=last_week,
            meeting_link="https://meet.google.com/xyz-qprs-tuv",
            status="Completed"
        )

        self.stdout.write("Created 2 Interviews.")
        
        # 5. Populate FAISS Vector Database for these candidates
        from services.vector_service import VectorService
        
        # Clear vector database directories if they exist, to ensure clean indexes
        if os.path.exists(VectorService.INDEX_PATH):
            os.remove(VectorService.INDEX_PATH)
        if os.path.exists(VectorService.MAPPING_PATH):
            os.remove(VectorService.MAPPING_PATH)
            
        for cand in [cand_a, cand_b, cand_c, cand_d, cand_e]:
            skills_str = ", ".join(cand.extracted_skills)
            text_to_embed = f"Candidate Name: {cand.name}. Skills: {skills_str}. Experience: {cand.resume_text[:200]}."
            VectorService.add_candidate(cand.id, text_to_embed)
            
        self.stdout.write("Populated FAISS Vector Database.")
        self.stdout.write(self.style.SUCCESS("Successfully seeded database!"))
