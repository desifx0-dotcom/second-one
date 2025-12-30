"""
Title, description, and chapter generation service
Uses multiple AI models for creative content generation
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
import re

from src.core.base import BaseService, ProcessingResult
from src.core.exceptions import ProcessingError, ExternalServiceError
from src.core.constants import SUPPORTED_LANGUAGES, AI_MODELS

# Import providers
from src.providers.openai_provider import OpenAIProvider
from src.providers.google_provider import GoogleProvider
from src.providers.anthropic_provider import AnthropicProvider

logger = logging.getLogger(__name__)

class TitleService(BaseService):
    """
    Service for generating titles, descriptions, tags, summaries, and chapters
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Initialize AI providers
        self.providers = {
            'openai': OpenAIProvider(config),
            'google': GoogleProvider(config),
            'anthropic': AnthropicProvider(config)
        }
        
        # Generation templates by language
        self.generation_templates = self._load_templates()
        
        # Statistics
        self.stats = {
            'total_generations': 0,
            'titles_generated': 0,
            'descriptions_generated': 0,
            'tags_generated': 0,
            'summaries_generated': 0,
            'chapters_generated': 0,
            'by_language': {},
            'by_provider': {}
        }
    
    def initialize(self) -> bool:
        """Initialize title service and AI providers"""
        try:
            logger.info("Initializing TitleService...")
            
            # Initialize providers
            for name, provider in self.providers.items():
                if not provider.initialize():
                    logger.warning(f"Provider {name} failed to initialize")
            
            logger.info("TitleService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"TitleService initialization failed: {str(e)}")
            return False
    
    async def generate_titles(
        self,
        transcription: Union[str, Dict[str, Any]],
        language: str = 'en',
        video_metadata: Optional[Dict[str, Any]] = None,
        count: int = 5,
        style: str = 'engaging'
    ) -> ProcessingResult:
        """
        Generate multiple title options from transcription
        
        Args:
            transcription: Transcription text or data
            language: Language code
            video_metadata: Video metadata (duration, resolution, etc.)
            count: Number of titles to generate
            style: Title style (engaging, clickbait, professional, descriptive)
            
        Returns:
            ProcessingResult: Titles generation result
        """
        start_time = datetime.now()
        
        try:
            # Extract text from transcription
            text = self._extract_text_from_transcription(transcription)
            if not text:
                return ProcessingResult(
                    success=False,
                    error="No text available from transcription"
                )
            
            # Validate language
            if language not in SUPPORTED_LANGUAGES:
                language = 'en'  # Default to English
            
            # Get generation template
            template = self.generation_templates.get(language, {}).get('titles', {})
            if not template:
                template = self.generation_templates['en']['titles']
            
            # Prepare prompt
            prompt = self._build_title_prompt(
                text=text,
                language=language,
                style=style,
                count=count,
                template=template,
                metadata=video_metadata
            )
            
            # Select provider
            provider = self._select_provider(language, 'title_generation')
            
            # Generate titles
            generation_result = await provider.generate_text(
                prompt=prompt,
                max_tokens=300,
                temperature=0.7
            )
            
            if not generation_result.success:
                return ProcessingResult(
                    success=False,
                    error=f"Title generation failed: {generation_result.error}"
                )
            
            # Parse generated titles
            generated_text = generation_result.data.get('text', '')
            titles = self._parse_generated_titles(generated_text, count)
            
            # Generate descriptions for each title
            descriptions = []
            if titles:
                descriptions = await self._generate_descriptions(
                    text=text,
                    titles=titles,
                    language=language,
                    metadata=video_metadata
                )
            
            # Generate tags
            tags = await self._generate_tags(text, language)
            
            # Generate summary
            summary = await self._generate_summary(text, language)
            
            # Prepare result
            duration = (datetime.now() - start_time).total_seconds()
            result_data = {
                'titles': titles,
                'descriptions': descriptions,
                'tags': tags,
                'summary': summary,
                'language': language,
                'style': style,
                'provider': provider.__class__.__name__,
                'duration': duration
            }
            
            # Update statistics
            self._update_statistics(
                'titles',
                language,
                provider.__class__.__name__,
                True,
                duration,
                len(titles)
            )
            
            logger.info(f"Generated {len(titles)} titles in {duration:.2f}s")
            
            return ProcessingResult(
                success=True,
                data=result_data,
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self._update_statistics('titles', 'unknown', 'unknown', False, duration)
            
            logger.error(f"Title generation failed: {str(e)}", exc_info=True)
            
            return ProcessingResult(
                success=False,
                error=f"Title generation failed: {str(e)}",
                duration=duration
            )
    
    async def generate_descriptions(
        self,
        transcription: Union[str, Dict[str, Any]],
        titles: List[str],
        language: str = 'en',
        video_metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Generate descriptions for given titles
        
        Args:
            transcription: Transcription text
            titles: List of titles
            language: Language code
            video_metadata: Video metadata
            
        Returns:
            ProcessingResult: Descriptions generation result
        """
        start_time = datetime.now()
        
        try:
            # Extract text
            text = self._extract_text_from_transcription(transcription)
            if not text:
                return ProcessingResult(
                    success=False,
                    error="No text available from transcription"
                )
            
            # Generate descriptions
            descriptions = await self._generate_descriptions(
                text=text,
                titles=titles,
                language=language,
                metadata=video_metadata
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Update statistics
            self._update_statistics(
                'descriptions',
                language,
                'openai',  # Default provider
                True,
                duration,
                len(descriptions)
            )
            
            return ProcessingResult(
                success=True,
                data={'descriptions': descriptions},
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self._update_statistics('descriptions', 'unknown', 'unknown', False, duration)
            
            logger.error(f"Description generation failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Description generation failed: {str(e)}",
                duration=duration
            )
    
    async def generate_tags(
        self,
        transcription: Union[str, Dict[str, Any]],
        language: str = 'en',
        count: int = 10
    ) -> ProcessingResult:
        """
        Generate tags/keywords from transcription
        
        Args:
            transcription: Transcription text
            language: Language code
            count: Number of tags to generate
            
        Returns:
            ProcessingResult: Tags generation result
        """
        start_time = datetime.now()
        
        try:
            # Extract text
            text = self._extract_text_from_transcription(transcription)
            if not text:
                return ProcessingResult(
                    success=False,
                    error="No text available from transcription"
                )
            
            # Generate tags
            tags = await self._generate_tags(text, language, count)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Update statistics
            self._update_statistics(
                'tags',
                language,
                'openai',
                True,
                duration,
                len(tags)
            )
            
            return ProcessingResult(
                success=True,
                data={'tags': tags},
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self._update_statistics('tags', 'unknown', 'unknown', False, duration)
            
            logger.error(f"Tag generation failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Tag generation failed: {str(e)}",
                duration=duration
            )
    
    async def generate_summary(
        self,
        transcription: Union[str, Dict[str, Any]],
        language: str = 'en',
        max_length: int = 200
    ) -> ProcessingResult:
        """
        Generate summary from transcription
        
        Args:
            transcription: Transcription text
            language: Language code
            max_length: Maximum summary length
            
        Returns:
            ProcessingResult: Summary generation result
        """
        start_time = datetime.now()
        
        try:
            # Extract text
            text = self._extract_text_from_transcription(transcription)
            if not text:
                return ProcessingResult(
                    success=False,
                    error="No text available from transcription"
                )
            
            # Generate summary
            summary = await self._generate_summary(text, language, max_length)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Update statistics
            self._update_statistics(
                'summaries',
                language,
                'openai',
                True,
                duration,
                1
            )
            
            return ProcessingResult(
                success=True,
                data={'summary': summary},
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self._update_statistics('summaries', 'unknown', 'unknown', False, duration)
            
            logger.error(f"Summary generation failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Summary generation failed: {str(e)}",
                duration=duration
            )
    
    async def generate_chapters(
        self,
        transcription: Union[str, Dict[str, Any]],
        duration: float,
        language: str = 'en',
        max_chapters: int = 10
    ) -> ProcessingResult:
        """
        Generate video chapters from transcription
        
        Args:
            transcription: Transcription text with timestamps
            duration: Video duration in seconds
            language: Language code
            max_chapters: Maximum number of chapters
            
        Returns:
            ProcessingResult: Chapters generation result
        """
        start_time = datetime.now()
        
        try:
            # Check if transcription has timestamps
            if isinstance(transcription, dict) and 'words' in transcription:
                words = transcription['words']
            elif isinstance(transcription, str):
                # Simple text without timestamps
                return ProcessingResult(
                    success=False,
                    error="Transcription must include timestamps for chapter generation"
                )
            else:
                return ProcessingResult(
                    success=False,
                    error="Invalid transcription format"
                )
            
            # Group words into potential chapters
            chapters = self._detect_chapters_from_transcription(words, duration, max_chapters)
            
            # Generate chapter titles
            chapter_titles = await self._generate_chapter_titles(chapters, language)
            
            # Combine chapters with titles
            final_chapters = []
            for i, (chapter_start, chapter_end) in enumerate(chapters):
                title = chapter_titles[i] if i < len(chapter_titles) else f"Chapter {i+1}"
                final_chapters.append({
                    'start': chapter_start,
                    'end': chapter_end,
                    'title': title,
                    'duration': chapter_end - chapter_start
                })
            
            duration_sec = (datetime.now() - start_time).total_seconds()
            
            # Update statistics
            self._update_statistics(
                'chapters',
                language,
                'openai',
                True,
                duration_sec,
                len(final_chapters)
            )
            
            return ProcessingResult(
                success=True,
                data={'chapters': final_chapters},
                duration=duration_sec
            )
            
        except Exception as e:
            duration_sec = (datetime.now() - start_time).total_seconds()
            self._update_statistics('chapters', 'unknown', 'unknown', False, duration_sec)
            
            logger.error(f"Chapter generation failed: {str(e)}", exc_info=True)
            return ProcessingResult(
                success=False,
                error=f"Chapter generation failed: {str(e)}",
                duration=duration_sec
            )
    
    # ========== PRIVATE METHODS ==========
    
    def _load_templates(self) -> Dict[str, Any]:
        """Load generation templates for different languages"""
        # Base templates in English
        base_templates = {
            'en': {
                'titles': {
                    'engaging': "Generate {count} engaging YouTube video titles based on this content:\n\n{content}\n\nRequirements:\n1. Catchy and clickable\n2. 50-70 characters max\n3. Include keywords\n4. Add emojis where appropriate\n\nTitles:",
                    'professional': "Generate {count} professional video titles based on this content:\n\n{content}\n\nRequirements:\n1. Clear and descriptive\n2. 40-60 characters\n3. Include main topic\n4. No emojis\n\nTitles:",
                    'clickbait': "Generate {count} clickbait-style video titles based on this content:\n\n{content}\n\nRequirements:\n1. Create curiosity gap\n2. Use power words\n3. 45-65 characters\n4. Add 1-2 emojis\n\nTitles:",
                    'descriptive': "Generate {count} descriptive video titles based on this content:\n\n{content}\n\nRequirements:\n1. Accurately describe content\n2. 55-75 characters\n3. Include key details\n4. No emojis\n\nTitles:"
                },
                'descriptions': "Write a YouTube video description for this title: '{title}'\n\nBased on this content:\n{content}\n\nInclude:\n1. Engaging opening\n2. Key points/timestamps\n3. Call to action\n4. Relevant hashtags\n\nDescription:",
                'tags': "Extract {count} relevant keywords/tags from this content:\n\n{content}\n\nTags (comma-separated):",
                'summary': "Summarize this content in {max_length} words or less:\n\n{content}\n\nSummary:"
            }
        }
        
        # Add templates for other major languages
        # In production, these would be more comprehensive
        templates = base_templates.copy()
        
        # Spanish templates
        templates['es'] = {
            'titles': {
                'engaging': "Genera {count} títulos atractivos para videos de YouTube basados en este contenido:\n\n{content}\n\nRequisitos:\n1. Llamativos y clickeables\n2. 50-70 caracteres máximo\n3. Incluir palabras clave\n4. Agregar emojis donde sea apropiado\n\nTítulos:",
                'professional': "Genera {count} títulos profesionales para videos basados en este contenido:\n\n{content}\n\nRequisitos:\n1. Claros y descriptivos\n2. 40-60 caracteres\n3. Incluir tema principal\n4. Sin emojis\n\nTítulos:"
            }
        }
        
        # French templates
        templates['fr'] = {
            'titles': {
                'engaging': "Générez {count} titres accrocheurs pour des vidéos YouTube basés sur ce contenu:\n\n{content}\n\nExigences:\n1. Attrayants et cliquables\n2. 50-70 caractères maximum\n3. Inclure des mots-clés\n4. Ajouter des émojis si approprié\n\nTitres:"
            }
        }
        
        return templates
    
    def _extract_text_from_transcription(self, transcription: Union[str, Dict[str, Any]]) -> str:
        """Extract plain text from transcription data"""
        if isinstance(transcription, str):
            return transcription
        
        if isinstance(transcription, dict):
            if 'text' in transcription:
                return transcription['text']
            elif 'words' in transcription:
                return ' '.join([word.get('word', '') for word in transcription['words']])
        
        return ""
    
    def _build_title_prompt(
        self,
        text: str,
        language: str,
        style: str,
        count: int,
        template: Dict[str, str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build prompt for title generation"""
        # Get template for the specified style
        style_template = template.get(style, template.get('engaging', ''))
        
        # Truncate text if too long
        max_text_length = 2000
        if len(text) > max_text_length:
            text = text[:max_text_length] + "..."
        
        # Prepare metadata string
        meta_info = ""
        if metadata:
            meta_parts = []
            if 'duration' in metadata:
                minutes = int(metadata['duration'] // 60)
                meta_parts.append(f"{minutes} min")
            if 'resolution' in metadata:
                meta_parts.append(f"{metadata['resolution']}")
            if 'original_filename' in metadata:
                # Extract keywords from filename
                filename = metadata['original_filename']
                # Remove extension and split by common separators
                name = filename.rsplit('.', 1)[0] if '.' in filename else filename
                keywords = re.split(r'[_\-\s]+', name)
                meta_parts.append(f"Keywords: {', '.join(keywords[:3])}")
            
            if meta_parts:
                meta_info = f"\n\nVideo Info: {', '.join(meta_parts)}"
        
        # Build final prompt
        prompt = style_template.format(
            count=count,
            content=text + meta_info
        )
        
        return prompt
    
    def _parse_generated_titles(self, generated_text: str, expected_count: int) -> List[str]:
        """Parse generated text to extract titles"""
        titles = []
        
        # Split by newlines and remove empty lines
        lines = [line.strip() for line in generated_text.split('\n') if line.strip()]
        
        for line in lines:
            # Remove numbering (1., 2., etc.)
            line = re.sub(r'^\d+[\.\)]\s*', '', line)
            
            # Remove quotes if present
            line = line.strip('"\'').strip()
            
            if line and len(line) >= 10:  # Reasonable minimum length
                titles.append(line)
            
            if len(titles) >= expected_count:
                break
        
        # If not enough titles found, split by other delimiters
        if len(titles) < expected_count:
            # Try splitting by other common separators
            alt_lines = re.split(r'[;\|•]', generated_text)
            for alt_line in alt_lines:
                alt_line = alt_line.strip()
                if alt_line and alt_line not in titles and len(alt_line) >= 10:
                    titles.append(alt_line)
                
                if len(titles) >= expected_count:
                    break
        
        return titles[:expected_count]
    
    async def _generate_descriptions(
        self,
        text: str,
        titles: List[str],
        language: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Generate descriptions for titles"""
        descriptions = []
        
        # Truncate text for description generation
        max_text_length = 1000
        if len(text) > max_text_length:
            text = text[:max_text_length] + "..."
        
        # Get description template
        template = self.generation_templates.get(language, {}).get('descriptions')
        if not template:
            template = self.generation_templates['en']['descriptions']
        
        # Generate description for each title
        for title in titles[:3]:  # Limit to first 3 titles
            try:
                prompt = template.format(title=title, content=text)
                
                provider = self.providers.get('openai')
                if not provider:
                    continue
                
                result = await provider.generate_text(
                    prompt=prompt,
                    max_tokens=500,
                    temperature=0.6
                )
                
                if result.success:
                    description = result.data.get('text', '').strip()
                    descriptions.append(description)
                
                # Add small delay between requests
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"Failed to generate description for '{title}': {str(e)}")
                continue
        
        return descriptions
    
    async def _generate_tags(
        self,
        text: str,
        language: str,
        count: int = 10
    ) -> List[str]:
        """Generate tags from text"""
        # Truncate text
        max_text_length = 1500
        if len(text) > max_text_length:
            text = text[:max_text_length] + "..."
        
        # Get tags template
        template = self.generation_templates.get(language, {}).get('tags')
        if not template:
            template = self.generation_templates['en']['tags']
        
        prompt = template.format(count=count, content=text)
        
        try:
            provider = self.providers.get('openai')
            if not provider:
                return []
            
            result = await provider.generate_text(
                prompt=prompt,
                max_tokens=100,
                temperature=0.3
            )
            
            if not result.success:
                return []
            
            generated_text = result.data.get('text', '').strip()
            
            # Parse tags
            tags = []
            for tag in generated_text.split(','):
                tag = tag.strip().lower()
                if tag and len(tag) >= 2:  # Minimum tag length
                    tags.append(tag)
            
            return tags[:count]
            
        except Exception as e:
            logger.warning(f"Tag generation failed: {str(e)}")
            return []
    
    async def _generate_summary(
        self,
        text: str,
        language: str,
        max_length: int = 200
    ) -> str:
        """Generate summary from text"""
        # Truncate text
        max_text_length = 3000
        if len(text) > max_text_length:
            text = text[:max_text_length] + "..."
        
        # Get summary template
        template = self.generation_templates.get(language, {}).get('summary')
        if not template:
            template = self.generation_templates['en']['summary']
        
        prompt = template.format(max_length=max_length, content=text)
        
        try:
            provider = self.providers.get('openai')
            if not provider:
                return ""
            
            result = await provider.generate_text(
                prompt=prompt,
                max_tokens=300,
                temperature=0.5
            )
            
            if not result.success:
                return ""
            
            return result.data.get('text', '').strip()
            
        except Exception as e:
            logger.warning(f"Summary generation failed: {str(e)}")
            return ""
    
    def _detect_chapters_from_transcription(
        self,
        words: List[Dict[str, Any]],
        duration: float,
        max_chapters: int
    ) -> List[Tuple[float, float]]:
        """Detect natural chapter breaks from transcription"""
        chapters = []
        
        if not words or len(words) < 10:
            return chapters
        
        # Calculate target chapter duration
        target_chapter_duration = duration / max_chapters
        
        # Simple algorithm: break at natural pauses and topic changes
        current_start = words[0].get('start', 0)
        current_end = current_start
        word_count = 0
        
        for i, word in enumerate(words):
            word_end = word.get('end', current_end)
            word_count += 1
            
            # Check for natural break points
            is_break_point = False
            
            # Break at significant time gaps
            if i > 0:
                prev_word = words[i-1]
                time_gap = word.get('start', 0) - prev_word.get('end', 0)
                if time_gap > 2.0:  # 2 second pause
                    is_break_point = True
            
            # Break after reasonable duration
            chapter_duration = word_end - current_start
            if chapter_duration >= target_chapter_duration * 0.8:  # 80% of target
                # Also check word count
                if word_count >= 50:  # Minimum words per chapter
                    is_break_point = True
            
            if is_break_point:
                chapters.append((current_start, word_end))
                current_start = word_end
                current_end = word_end
                word_count = 0
            
            current_end = word_end
        
        # Add final chapter
        if current_start < duration:
            chapters.append((current_start, duration))
        
        return chapters
    
    async def _generate_chapter_titles(
        self,
        chapters: List[Tuple[float, float]],
        language: str
    ) -> List[str]:
        """Generate titles for chapters"""
        # Simple implementation - in production, you'd analyze the content of each chapter
        titles = []
        
        for i, (start, end) in enumerate(chapters):
            duration_min = (end - start) / 60
            titles.append(f"Part {i+1} ({duration_min:.1f} min)")
        
        return titles
    
    def _select_provider(self, language: str, task_type: str) -> Any:
        """Select appropriate AI provider"""
        # For now, default to OpenAI
        return self.providers.get('openai', list(self.providers.values())[0])
    
    def _update_statistics(
        self,
        task_type: str,
        language: str,
        provider: str,
        success: bool,
        duration: float,
        count: int = 1
    ):
        """Update service statistics"""
        # Update language stats
        if language not in self.stats['by_language']:
            self.stats['by_language'][language] = {
                'count': 0,
                'successful': 0,
                'total_duration': 0.0
            }
        
        lang_stats = self.stats['by_language'][language]
        lang_stats['count'] += count
        if success:
            lang_stats['successful'] += count
        lang_stats['total_duration'] += duration
        
        # Update provider stats
        if provider not in self.stats['by_provider']:
            self.stats['by_provider'][provider] = {
                'count': 0,
                'successful': 0
            }
        
        prov_stats = self.stats['by_provider'][provider]
        prov_stats['count'] += count
        if success:
            prov_stats['successful'] += count
        
        # Update overall stats
        self.stats['total_generations'] += count
        if task_type == 'titles':
            self.stats['titles_generated'] += count
        elif task_type == 'descriptions':
            self.stats['descriptions_generated'] += count
        elif task_type == 'tags':
            self.stats['tags_generated'] += count
        elif task_type == 'summaries':
            self.stats['summaries_generated'] += count
        elif task_type == 'chapters':
            self.stats['chapters_generated'] += count
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get title service statistics"""
        return {
            **self.stats,
            'available_providers': list(self.providers.keys()),
            'supported_templates': list(self.generation_templates.keys())
        }