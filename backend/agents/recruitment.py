import logging
from django.db.models import Q
from api.models import Candidate, JobRole
from services.vector_service import VectorService
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

class RecruitmentAgent:
    @classmethod
    def search(cls, query_text):
        """
        Performs vector search + SQL search to find matching candidates.
        """
        logger.info(f"Recruitment agent performing search for: '{query_text}'")
        
        # 1. Search vector DB for semantic matches
        candidate_ids = VectorService.search_candidates(query_text, top_k=5)
        
        # 2. Search SQL database as fallback / enhancement (e.g. searching name or skills directly)
        db_candidates = Candidate.objects.filter(
            Q(name__icontains=query_text) | 
            Q(extracted_skills__icontains=query_text) | 
            Q(resume_text__icontains=query_text)
        )[:5]

        # Combine IDs
        final_ids = list(candidate_ids)
        for cand in db_candidates:
            cand_id_str = str(cand.id)
            if cand_id_str not in final_ids:
                final_ids.append(cand_id_str)

        # Retrieve Candidate details
        candidates = Candidate.objects.filter(id__in=final_ids).order_by('-score')
        
        if not candidates.exists():
            return "I couldn't find any candidates matching those skills or keywords in our records."

        # Format markdown response
        response = "### Candidate Match Results\n\n"
        for cand in candidates:
            skills_str = ", ".join(cand.extracted_skills) if cand.extracted_skills else "None listed"
            response += (
                f"- **{cand.name}** (Score: {cand.score}/100) - Status: `{cand.status}`\n"
                f"  - **Skills:** {skills_str}\n"
                f"  - **Match Summary:** {cand.match_explanation or 'No explanation available.'}\n\n"
            )
        return response

    @classmethod
    def compare_candidates(cls, name_a, name_b):
        """
        Retrieves candidates matching name_a and name_b, and gets LLM to compare them.
        """
        logger.info(f"Comparing candidates {name_a} and {name_b}")
        cand_a = Candidate.objects.filter(name__icontains=name_a).first()
        cand_b = Candidate.objects.filter(name__icontains=name_b).first()

        if not cand_a:
            return f"I couldn't find a candidate matching the name '{name_a}' in the system."
        if not cand_b:
            return f"I couldn't find a candidate matching the name '{name_b}' in the system."

        system_prompt = (
            "You are an expert HR recruitment consultant. You are comparing two candidates for a role. "
            "Provide a balanced, highly professional comparison highlight their strengths, gaps, "
            "and make a clear recommendation on which one is a stronger candidate."
        )

        user_content = (
            f"=== Candidate A ===\n"
            f"Name: {cand_a.name}\n"
            f"Skills: {cand_a.extracted_skills}\n"
            f"Experience/Education: {cand_a.resume_text[:2000] if cand_a.resume_text else 'Not available'}\n"
            f"Match Score: {cand_a.score}\n"
            f"Match Explanation: {cand_a.match_explanation}\n\n"
            f"=== Candidate B ===\n"
            f"Name: {cand_b.name}\n"
            f"Skills: {cand_b.extracted_skills}\n"
            f"Experience/Education: {cand_b.resume_text[:2000] if cand_b.resume_text else 'Not available'}\n"
            f"Match Score: {cand_b.score}\n"
            f"Match Explanation: {cand_b.match_explanation}\n"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        comparison_result = LLMService.query(messages, temperature=0.3)
        return comparison_result

    @classmethod
    def get_candidate_details(cls, name_query):
        """
        Finds a candidate and explains why they were rejected or shortlisted.
        """
        cand = Candidate.objects.filter(name__icontains=name_query).first()
        if not cand:
            return f"I couldn't find any candidate matching the name '{name_query}'."

        response = (
            f"### Profile Analysis: {cand.name}\n"
            f"* **Current Status:** `{cand.status}`\n"
            f"* **AI Suitability Score:** {cand.score}/100\n"
            f"* **Extracted Skills:** {', '.join(cand.extracted_skills) if cand.extracted_skills else 'None'}\n\n"
            f"#### Match Summary\n"
            f"{cand.match_explanation or 'No explanation parsed.'}\n"
        )
        return response

    @classmethod
    def get_top_candidates(cls, limit=3):
        """
        Returns top shortlisted candidates based on rating score.
        """
        candidates = Candidate.objects.exclude(score__isnull=True).order_by('-score')[:limit]
        if not candidates.exists():
            return "There are no evaluated candidates in the database yet."

        response = f"### Top {limit} Candidates\n\n"
        for cand in candidates:
            response += f"1. **{cand.name}** (Score: {cand.score}/100) - Status: `{cand.status}`\n"
            response += f"   - *Skills:* {', '.join(cand.extracted_skills) if cand.extracted_skills else 'None'}\n"
            response += f"   - *Match:* {cand.match_explanation[:150]}...\n\n"
        return response
