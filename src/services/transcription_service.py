"""
Transcription service using multiple AI providers
Supports 150+ languages with fallback providers
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

from src.core.base import BaseService, ProcessingResult
from src.core.exceptions import ProcessingError, ExternalServiceError
from src.core.constants import SUPPORTED_LANGUAGES, AI_MODELS

# Import providers
from src.providers.openai_provider import OpenAIProvider
from src.providers.google_provider import GoogleProvider
from src.providers.assemblyai_provider import AssemblyAIProvider

logger = logging.getLogger(__name__)

class TranscriptionService(BaseService):
    """
    Transcription service supporting multiple AI providers with fallback
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Initialize providers
        self.providers = {
            'openai': OpenAIProvider(config),
            'google': GoogleProvider(config),
            'assemblyai': AssemblyAIProvider(config)
        }
        
        # Provider priority based on language
        self.provider_priority = {
            'en': ['assemblyai', 'openai', 'google'],
            'zh': ['google', 'openai'],
            'ja': ['google', 'openai'],
            'ko': ['google', 'openai'],
            'default': ['openai', 'google']
        }
        
        # Statistics
        self.stats = {
            'total_transcriptions': 0,
            'successful': 0,
            'failed': 0,
            'by_language': {},
            'by_provider': {}
        }
    
    def initialize(self) -> bool:
        """Initialize transcription service and providers"""
        try:
            logger.info("Initializing TranscriptionService...")
            
            # Initialize all providers
            for name, provider in self.providers.items():
                if not provider.initialize():
                    logger.warning(f"Provider {name} failed to initialize")
                    # Continue with other providers
            
            logger.info("TranscriptionService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"TranscriptionService initialization failed: {str(e)}")
            return False
    
    async def transcribe_video(
        self,
        video_path: Union[str, Path],
        source_language: str = 'auto',
        target_language: Optional[str] = None,
        provider: Optional[str] = None
    ) -> ProcessingResult:
        """
        Transcribe video to text
        
        Args:
            video_path: Path to video file
            source_language: Source language code or 'auto'
            target_language: Target language for translation
            provider: Specific provider to use
            
        Returns:
            ProcessingResult: Transcription result
        """
        start_time = datetime.now()
        
        try:
            # Extract audio if needed
            audio_path = await self._extract_audio(video_path)
            if not audio_path:
                return ProcessingResult(
                    success=False,
                    error="Failed to extract audio from video"
                )
            
            # Detect language if auto
            if source_language == 'auto':
                source_language = await self._detect_language(audio_path)
                if not source_language:
                    source_language = 'en'  # Default to English
            
            # Validate language
            if source_language not in SUPPORTED_LANGUAGES:
                return ProcessingResult(
                    success=False,
                    error=f"Language '{source_language}' is not supported"
                )
            
            # Select provider
            selected_provider = provider or self._select_provider(source_language)
            if not selected_provider or selected_provider not in self.providers:
                return ProcessingResult(
                    success=False,
                    error="No suitable transcription provider available"
                )
            
            logger.info(f"Transcribing with {selected_provider} for language {source_language}")
            
            # Transcribe with selected provider
            provider_instance = self.providers[selected_provider]
            transcription_result = await provider_instance.transcribe(
                audio_path=audio_path,
                language=source_language
            )
            
            if not transcription_result.success:
                # Try fallback providers
                return await self._try_fallback_providers(
                    audio_path, source_language, selected_provider
                )
            
            # Translate if target language specified and different
            translation_result = None
            if target_language and target_language != source_language:
                translation_result = await self._translate_transcription(
                    transcription_result.data.get('text', ''),
                    source_language=source_language,
                    target_language=target_language
                )
            
            # Clean up temporary audio file
            await self._cleanup_temp_file(audio_path)
            
            # Prepare final result
            duration = (datetime.now() - start_time).total_seconds()
            result_data = {
                'transcription': transcription_result.data.get('transcription', {}),
                'text': transcription_result.data.get('text', ''),
                'words': transcription_result.data.get('words', []),
                'confidence': transcription_result.data.get('confidence', 0.0),
                'detected_language': source_language,
                'provider': selected_provider,
                'duration': duration,
                'word_count': len(transcription_result.data.get('text', '').split())
            }
            
            if translation_result and translation_result.success:
                result_data['translation'] = translation_result.data
                result_data['target_language'] = target_language
            
            # Update statistics
            self._update_statistics(
                source_language,
                selected_provider,
                True,
                duration,
                result_data['word_count']
            )
            
            logger.info(f"Transcription completed: {result_data['word_count']} words in {duration:.2f}s")
            
            return ProcessingResult(
                success=True,
                data=result_data,
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self._update_statistics('unknown', 'unknown', False, duration)
            
            logger.error(f"Transcription failed: {str(e)}", exc_info=True)
            
            return ProcessingResult(
                success=False,
                error=f"Transcription failed: {str(e)}",
                error_details={'exception_type': type(e).__name__},
                duration=duration
            )
    
    async def transcribe_batch(
        self,
        video_paths: List[Union[str, Path]],
        source_language: str = 'auto',
        max_concurrent: int = 3
    ) -> Dict[str, ProcessingResult]:
        """
        Transcribe multiple videos concurrently
        
        Args:
            video_paths: List of video paths
            source_language: Source language
            max_concurrent: Maximum concurrent transcriptions
            
        Returns:
            Dict[str, ProcessingResult]: Results by video path
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = {}
        
        async def transcribe_with_limit(video_path):
            async with semaphore:
                result = await self.transcribe_video(video_path, source_language)
                return str(video_path), result
        
        # Create tasks
        tasks = [transcribe_with_limit(path) for path in video_paths]
        
        # Run concurrently
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in completed:
            if isinstance(result, Exception):
                logger.error(f"Batch transcription task failed: {str(result)}")
                continue
            
            video_path, transcription_result = result
            results[video_path] = transcription_result
        
        return results
    
    async def get_transcription_formats(
        self,
        transcription_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Convert transcription to multiple formats
        
        Args:
            transcription_data: Transcription data
            
        Returns:
            Dict[str, str]: Transcription in different formats
        """
        formats = {}
        
        # SRT format
        formats['srt'] = self._convert_to_srt(transcription_data)
        
        # VTT format
        formats['vtt'] = self._convert_to_vtt(transcription_data)
        
        # Plain text
        formats['txt'] = transcription_data.get('text', '')
        
        # JSON format
        formats['json'] = json.dumps(transcription_data, indent=2)
        
        return formats
    
    # ========== PRIVATE METHODS ==========
    
    async def _extract_audio(self, video_path: Union[str, Path]) -> Optional[Path]:
        """Extract audio from video file"""
        try:
            import tempfile
            import subprocess
            
            # Create temporary audio file
            temp_dir = tempfile.mkdtemp()
            audio_path = Path(temp_dir) / 'audio.mp3'
            
            # Extract audio using ffmpeg
            cmd = [
                'ffmpeg', '-i', str(video_path),
                '-vn', '-acodec', 'libmp3lame',
                '-ab', '192k', '-ar', '44100',
                '-y', str(audio_path)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Audio extraction failed: {stderr.decode()}")
                return None
            
            if not audio_path.exists() or audio_path.stat().st_size == 0:
                logger.error("Extracted audio file is empty")
                return None
            
            return audio_path
            
        except Exception as e:
            logger.error(f"Audio extraction error: {str(e)}")
            return None
    
    async def _detect_language(self, audio_path: Path) -> Optional[str]:
        """Detect language from audio"""
        try:
            # Try with each provider that supports language detection
            for provider_name in ['google', 'openai']:
                if provider_name in self.providers:
                    provider = self.providers[provider_name]
                    if hasattr(provider, 'detect_language'):
                        result = await provider.detect_language(audio_path)
                        if result and result.success:
                            return result.data.get('language')
            
            return None
            
        except Exception as e:
            logger.error(f"Language detection failed: {str(e)}")
            return None
    
    def _select_provider(self, language: str) -> Optional[str]:
        """Select the best provider for the language"""
        # Get priority for this language
        priority = self.provider_priority.get(language, self.provider_priority['default'])
        
        # Return first available provider
        for provider in priority:
            if provider in self.providers and self.providers[provider].is_available():
                return provider
        
        return None
    
    async def _try_fallback_providers(
        self,
        audio_path: Path,
        language: str,
        failed_provider: str
    ) -> ProcessingResult:
        """Try fallback providers if primary fails"""
        # Get all providers except the failed one
        available_providers = [
            name for name, provider in self.providers.items()
            if name != failed_provider and provider.is_available()
        ]
        
        for provider_name in available_providers:
            try:
                logger.info(f"Trying fallback provider: {provider_name}")
                
                provider = self.providers[provider_name]
                result = await provider.transcribe(audio_path, language)
                
                if result.success:
                    logger.info(f"Fallback provider {provider_name} succeeded")
                    return result
                
            except Exception as e:
                logger.error(f"Fallback provider {provider_name} failed: {str(e)}")
                continue
        
        return ProcessingResult(
            success=False,
            error="All transcription providers failed"
        )
    
    async def _translate_transcription(
        self,
        text: str,
        source_language: str,
        target_language: str
    ) -> ProcessingResult:
        """Translate transcription text"""
        try:
            # Use Google Translate provider (best for translation)
            if 'google' in self.providers:
                provider = self.providers['google']
                if hasattr(provider, 'translate'):
                    return await provider.translate(
                        text=text,
                        source_language=source_language,
                        target_language=target_language
                    )
            
            return ProcessingResult(
                success=False,
                error="Translation service not available"
            )
            
        except Exception as e:
            logger.error(f"Translation failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Translation failed: {str(e)}"
            )
    
    async def _cleanup_temp_file(self, file_path: Path):
        """Clean up temporary file"""
        try:
            if file_path.exists():
                file_path.unlink()
                # Also remove parent directory if empty
                parent = file_path.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {str(e)}")
    
    def _convert_to_srt(self, transcription_data: Dict[str, Any]) -> str:
        """Convert transcription to SRT format"""
        try:
            words = transcription_data.get('words', [])
            if not words:
                return ""
            
            srt_lines = []
            segment_index = 1
            
            # Group words into segments (approximately 5-10 words per segment)
            words_per_segment = 8
            for i in range(0, len(words), words_per_segment):
                segment_words = words[i:i + words_per_segment]
                
                # Get segment times
                start_time = segment_words[0].get('start', 0)
                end_time = segment_words[-1].get('end', start_time + 5)
                
                # Format times for SRT (HH:MM:SS,mmm)
                start_str = self._format_srt_time(start_time)
                end_str = self._format_srt_time(end_time)
                
                # Get segment text
                segment_text = ' '.join(word.get('word', '') for word in segment_words)
                
                # Add to SRT
                srt_lines.append(str(segment_index))
                srt_lines.append(f"{start_str} --> {end_str}")
                srt_lines.append(segment_text)
                srt_lines.append("")  # Empty line between segments
                
                segment_index += 1
            
            return '\n'.join(srt_lines)
            
        except Exception as e:
            logger.error(f"SRT conversion failed: {str(e)}")
            return ""
    
    def _convert_to_vtt(self, transcription_data: Dict[str, Any]) -> str:
        """Convert transcription to WebVTT format"""
        try:
            srt_content = self._convert_to_srt(transcription_data)
            if not srt_content:
                return ""
            
            # Convert SRT to VTT
            vtt_lines = ["WEBVTT", ""]
            
            for line in srt_content.split('\n'):
                if '-->' in line:
                    # Convert SRT time format to VTT
                    line = line.replace(',', '.')
                vtt_lines.append(line)
            
            return '\n'.join(vtt_lines)
            
        except Exception as e:
            logger.error(f"VTT conversion failed: {str(e)}")
            return ""
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format seconds to SRT time format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds - int(seconds)) * 1000)
        seconds = int(seconds)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    
    def _update_statistics(
        self,
        language: str,
        provider: str,
        success: bool,
        duration: float,
        word_count: int = 0
    ):
        """Update transcription statistics"""
        # Update language stats
        if language not in self.stats['by_language']:
            self.stats['by_language'][language] = {
                'count': 0,
                'successful': 0,
                'total_words': 0,
                'total_duration': 0.0
            }
        
        lang_stats = self.stats['by_language'][language]
        lang_stats['count'] += 1
        if success:
            lang_stats['successful'] += 1
            lang_stats['total_words'] += word_count
        lang_stats['total_duration'] += duration
        
        # Update provider stats
        if provider not in self.stats['by_provider']:
            self.stats['by_provider'][provider] = {
                'count': 0,
                'successful': 0
            }
        
        prov_stats = self.stats['by_provider'][provider]
        prov_stats['count'] += 1
        if success:
            prov_stats['successful'] += 1
        
        # Update overall stats
        self.stats['total_transcriptions'] += 1
        if success:
            self.stats['successful'] += 1
        else:
            self.stats['failed'] += 1
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get transcription service statistics"""
        return {
            **self.stats,
            'available_providers': list(self.providers.keys()),
            'supported_languages': list(SUPPORTED_LANGUAGES.keys())
        }