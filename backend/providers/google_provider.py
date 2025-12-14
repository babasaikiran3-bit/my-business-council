"""Google Gemini provider integration."""

from typing import List, Dict
import google.generativeai as genai
from .base import Provider, ProviderResponse


class GoogleProvider(Provider):
    """Provider for Google's Gemini models."""

    def __init__(self, api_key: str):
        """Initialize Google provider.

        Args:
            api_key: Google API key
        """
        super().__init__(api_key)
        genai.configure(api_key=api_key)

    async def query(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0
    ) -> ProviderResponse:
        """Query Gemini API.

        Args:
            model: Gemini model identifier (e.g., 'gemini-3.0-pro', 'gemini-2.5-flash-lite')
            messages: List of message dicts with 'role' and 'content'
            timeout: Request timeout in seconds

        Returns:
            ProviderResponse with normalized response
        """
        try:
            # Create model instance
            gemini_model = genai.GenerativeModel(model)

            # Convert messages to Gemini format
            # Google uses 'user' and 'model' roles
            gemini_messages = []
            for msg in messages:
                role = msg['role']
                if role == 'assistant':
                    role = 'model'  # Gemini uses 'model' instead of 'assistant'
                gemini_messages.append({
                    'role': role,
                    'parts': [msg['content']]
                })

            # For single user message, use simpler format
            if len(gemini_messages) == 1 and gemini_messages[0]['role'] == 'user':
                # Use generate_content for single-turn conversations
                response = await gemini_model.generate_content_async(
                    gemini_messages[0]['parts'][0]
                )
            else:
                # Use chat for multi-turn conversations
                chat = gemini_model.start_chat(history=gemini_messages[:-1])
                response = await chat.send_message_async(
                    gemini_messages[-1]['parts'][0]
                )

            # Extract content from response
            content = response.text if response.text else ""

            return ProviderResponse(
                content=content,
                model=model,
                provider="google",
                reasoning=None,  # Gemini doesn't expose reasoning separately
                error=None
            )

        except Exception as e:
            # Return error response instead of raising
            error_msg = f"Google API error: {str(e)}"
            print(error_msg)
            return ProviderResponse(
                content="",
                model=model,
                provider="google",
                reasoning=None,
                error=error_msg
            )

    def get_provider_name(self) -> str:
        """Get provider name.

        Returns:
            'google'
        """
        return "google"
