"""
OpenAI API executor - ONLY makes OpenAI API calls
Primary: Whisper for captions
Fallback: GPT for other text (if Gemini fails)
"""
import logging
from typing import Dict, Any, Optional

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

logger = logging.getLogger(__name__)

class OpenAIProvider:
    """
    Executes OpenAI API calls only
    1. Whisper API for captions (PRIMARY)
    2. GPT API as fallback (if Gemini fails)
    """
    
    def __init__(self, api_key: str = None, config: Dict[str, Any] = None):
        self.config = config or {}
        self.api_key = api_key or self.config.get('OPENAI_API_KEY')
        self.client = None
        
        if self.api_key and HAS_OPENAI:
            self._init_openai()
    
    def _init_openai(self):
        """Initialize OpenAI client"""
        try:
            self.client = openai.OpenAI(api_key=self.api_key)
            logger.info("OpenAI client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI: {str(e)}")
    
    # ========== WHISPER API (PRIMARY FOR CAPTIONS) ==========
    
    def transcribe_audio(self, audio_file_path: str, **kwargs) -> Dict[str, Any]:
        """Execute Whisper API call for transcription"""
        if not self.client:
            return {'success': False, 'error': 'OpenAI not initialized'}
        
        try:
            with open(audio_file_path, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-1",
                    **kwargs
                )
            
            return {
                'success': True,
                'text': transcript.text,
                'language': getattr(transcript, 'language', 'en'),
                'duration': getattr(transcript, 'duration', 0)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    # ========== GPT API (FALLBACK) ==========
    
    def generate_chat_completion(self, messages: list, **kwargs) -> Dict[str, Any]:
        """Execute GPT API call - used as fallback"""
        if not self.client:
            return {'success': False, 'error': 'OpenAI not initialized'}
        
        try:
            response = self.client.chat.completions.create(
                messages=messages,
                **kwargs
            )
            
            return {
                'success': True,
                'text': response.choices[0].message.content,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }