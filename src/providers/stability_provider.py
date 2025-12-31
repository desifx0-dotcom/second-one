"""
Stability AI API executor - ONLY makes image generation API calls
PRIMARY for thumbnails
"""
import logging
from typing import Dict, Any, Optional, List

try:
    import stability_sdk.client
    import stability_sdk.interfaces.gooseai.generation.generation_pb2 as generation
    HAS_STABILITY = True
except ImportError:
    HAS_STABILITY = False

logger = logging.getLogger(__name__)

class StabilityAIProvider:
    """
    Executes Stability AI API calls only
    Primary for AI thumbnail generation
    """
    
    def __init__(self, api_key: str = None, config: Dict[str, Any] = None):
        self.config = config or {}
        self.api_key = api_key or self.config.get('STABILITY_API_KEY')
        self.client = None
        
        if self.api_key and HAS_STABILITY:
            self._init_stability()
    
    def _init_stability(self):
        """Initialize Stability AI client"""
        try:
            self.client = stability_sdk.client.StabilityInference(
                key=self.api_key,
                engine='stable-diffusion-xl-1024-v1-0'
            )
            logger.info("Stability AI client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Stability AI: {str(e)}")
    
    def generate_image(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Execute Stability AI image generation API call"""
        if not self.client:
            return {'success': False, 'error': 'Stability AI not initialized'}
        
        try:
            responses = self.client.generate(prompt=prompt, **kwargs)
            
            images = []
            for resp in responses:
                for artifact in resp.artifacts:
                    if artifact.type == generation.ARTIFACT_IMAGE:
                        images.append({
                            'binary': artifact.binary,
                            'seed': artifact.seed,
                            'mime_type': 'image/png'
                        })
            
            return {
                'success': True,
                'images': images,
                'count': len(images)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }