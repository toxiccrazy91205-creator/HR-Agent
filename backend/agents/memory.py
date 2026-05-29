import logging
from api.models import ChatHistory

logger = logging.getLogger(__name__)

class MemoryAgent:
    @classmethod
    def get_conversation_context(cls, session_id="default", limit=10):
        """
        Retrieves the last `limit` messages from ChatHistory and formats them for the LLM.
        """
        try:
            # Django filter ordered by timestamp descending
            history = ChatHistory.objects.filter(session_id=session_id).order_by('-timestamp')[:limit]
            history = list(reversed(history))  # Put back in chronological order

            formatted_context = ""
            for chat in history:
                role_label = "HR User" if chat.role == "user" else "AI Assistant"
                formatted_context += f"{role_label}: {chat.message}\n"
            
            return formatted_context.strip()
        except Exception as e:
            logger.error(f"Error fetching conversation context: {str(e)}")
            return ""

    @classmethod
    def save_chat_message(cls, role, message, session_id="default", tool_execution=None):
        """
        Saves a message (either user or assistant) into ChatHistory.
        """
        try:
            chat = ChatHistory.objects.create(
                session_id=session_id,
                role=role,
                message=message,
                tool_execution=tool_execution
            )
            return chat
        except Exception as e:
            logger.error(f"Error saving chat message: {str(e)}")
            return None
