"""
Thumbnail generation service
Extracts frames and generates AI-powered thumbnails
"""

import asyncio
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import concurrent.futures

from src.core.base import BaseService, ProcessingResult
from src.core.exceptions import ProcessingError, ExternalServiceError
from src.core.constants import THUMBNAIL_STYLES

# Import providers
from src.providers.stability_provider import StabilityProvider
from src.providers.openai_provider import OpenAIProvider  # For DALL-E
from src.providers.google_provider import GoogleProvider  # For Imagen

logger = logging.getLogger(__name__)

class ThumbnailService(BaseService):
    """
    Service for extracting and generating video thumbnails
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Initialize AI providers
        self.providers = {
            'stability': StabilityProvider(config),
            'openai': OpenAIProvider(config),
            'google': GoogleProvider(config)
        }
        
        # Image processing pool
        self.image_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        
        # Statistics
        self.stats = {
            'total_thumbnails': 0,
            'extracted': 0,
            'ai_generated': 0,
            'by_style': {},
            'by_provider': {},
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def initialize(self) -> bool:
        """Initialize thumbnail service and providers"""
        try:
            logger.info("Initializing ThumbnailService...")
            
            # Initialize providers
            for name, provider in self.providers.items():
                if not provider.initialize():
                    logger.warning(f"Provider {name} failed to initialize")
            
            logger.info("ThumbnailService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"ThumbnailService initialization failed: {str(e)}")
            return False
    
    async def generate_thumbnails(
        self,
        video_path: Union[str, Path],
        titles: List[str] = None,
        style: str = 'cinematic',
        count: int = 5,
        width: int = 1280,
        height: int = 720,
        use_ai: bool = True
    ) -> ProcessingResult:
        """
        Generate thumbnails for video
        
        Args:
            video_path: Path to video file
            titles: List of titles for AI generation
            style: Thumbnail style
            count: Number of thumbnails to generate
            width: Thumbnail width
            height: Thumbnail height
            use_ai: Whether to use AI generation
            
        Returns:
            ProcessingResult: Thumbnails generation result
        """
        start_time = datetime.now()
        
        try:
            thumbnails = []
            thumbnail_urls = []
            
            # Step 1: Extract frames from video
            extracted_frames = await self._extract_video_frames(
                video_path, count=count, width=width, height=height
            )
            
            for frame_path in extracted_frames:
                # Step 2: Apply style to frame
                styled_path = await self._apply_thumbnail_style(
                    frame_path, style, width, height
                )
                
                if styled_path:
                    thumbnails.append(str(styled_path))
                    self.stats['extracted'] += 1
            
            # Step 3: Generate AI thumbnails if requested and titles available
            ai_thumbnails = []
            if use_ai and titles and len(titles) > 0:
                ai_thumbnails = await self._generate_ai_thumbnails(
                    titles=titles,
                    style=style,
                    count=min(3, count),  # Max 3 AI thumbnails
                    width=width,
                    height=height
                )
                
                for ai_path in ai_thumbnails:
                    thumbnails.append(str(ai_path))
                    self.stats['ai_generated'] += 1
            
            # Step 4: Upload to storage
            uploaded_urls = await self._upload_thumbnails(thumbnails)
            thumbnail_urls.extend(uploaded_urls)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Prepare result
            result_data = {
                'thumbnails': thumbnails,
                'urls': thumbnail_urls,
                'count': len(thumbnails),
                'extracted_count': len(extracted_frames),
                'ai_count': len(ai_thumbnails),
                'style': style,
                'dimensions': f"{width}x{height}",
                'duration': duration
            }
            
            # Update statistics
            self._update_statistics(style, 'mixed', True, duration, len(thumbnails))
            
            logger.info(f"Generated {len(thumbnails)} thumbnails in {duration:.2f}s")
            
            return ProcessingResult(
                success=True,
                data=result_data,
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self._update_statistics('unknown', 'unknown', False, duration)
            
            logger.error(f"Thumbnail generation failed: {str(e)}", exc_info=True)
            
            return ProcessingResult(
                success=False,
                error=f"Thumbnail generation failed: {str(e)}",
                duration=duration
            )
    
    async def extract_best_frame(
        self,
        video_path: Union[str, Path],
        width: int = 1280,
        height: int = 720
    ) -> ProcessingResult:
        """
        Extract the best frame from video for thumbnail
        
        Args:
            video_path: Path to video file
            width: Frame width
            height: Frame height
            
        Returns:
            ProcessingResult: Best frame extraction result
        """
        start_time = datetime.now()
        
        try:
            # Extract multiple candidate frames
            candidate_frames = await self._extract_video_frames(
                video_path, count=10, width=width, height=height
            )
            
            if not candidate_frames:
                return ProcessingResult(
                    success=False,
                    error="No frames could be extracted from video"
                )
            
            # Score each frame
            best_frame = None
            best_score = -1
            
            for frame_path in candidate_frames:
                score = await self._score_frame_quality(frame_path)
                if score > best_score:
                    best_score = score
                    best_frame = frame_path
            
            if not best_frame:
                return ProcessingResult(
                    success=False,
                    error="Could not determine best frame"
                )
            
            # Apply basic enhancements
            enhanced_path = await self._enhance_frame(best_frame, width, height)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            result_data = {
                'frame_path': str(enhanced_path) if enhanced_path else str(best_frame),
                'score': best_score,
                'dimensions': f"{width}x{height}",
                'duration': duration
            }
            
            logger.info(f"Extracted best frame with score {best_score:.2f}")
            
            return ProcessingResult(
                success=True,
                data=result_data,
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"Best frame extraction failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Frame extraction failed: {str(e)}",
                duration=duration
            )
    
    async def create_custom_thumbnail(
        self,
        base_image_path: Union[str, Path],
        title: str,
        subtitle: str = None,
        style: str = 'cinematic',
        width: int = 1280,
        height: int = 720
    ) -> ProcessingResult:
        """
        Create custom thumbnail with text overlay
        
        Args:
            base_image_path: Base image path
            title: Title text
            subtitle: Subtitle text
            style: Thumbnail style
            width: Thumbnail width
            height: Thumbnail height
            
        Returns:
            ProcessingResult: Custom thumbnail result
        """
        start_time = datetime.now()
        
        try:
            # Load and resize base image
            import cv2
            import numpy as np
            
            image = cv2.imread(str(base_image_path))
            if image is None:
                return ProcessingResult(
                    success=False,
                    error="Could not load base image"
                )
            
            # Resize to target dimensions
            image = cv2.resize(image, (width, height))
            
            # Apply style
            styled_image = await self._apply_style_to_image(image, style)
            
            # Add text overlay
            result_image = await self._add_text_overlay(
                styled_image, title, subtitle, style
            )
            
            # Save result
            output_path = Path(tempfile.mktemp(suffix='.jpg'))
            cv2.imwrite(str(output_path), result_image)
            
            # Upload to storage
            uploaded_url = await self._upload_thumbnail(output_path)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            result_data = {
                'thumbnail_path': str(output_path),
                'thumbnail_url': uploaded_url,
                'dimensions': f"{width}x{height}",
                'style': style,
                'duration': duration
            }
            
            self.stats['ai_generated'] += 1
            self._update_statistics(style, 'custom', True, duration, 1)
            
            logger.info(f"Created custom thumbnail in {duration:.2f}s")
            
            return ProcessingResult(
                success=True,
                data=result_data,
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self._update_statistics(style, 'custom', False, duration)
            
            logger.error(f"Custom thumbnail creation failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Custom thumbnail failed: {str(e)}",
                duration=duration
            )
    
    # ========== PRIVATE METHODS ==========
    
    async def _extract_video_frames(
        self,
        video_path: Union[str, Path],
        count: int = 5,
        width: int = 1280,
        height: int = 720
    ) -> List[Path]:
        """Extract frames from video at evenly spaced intervals"""
        frames = []
        
        try:
            import subprocess
            import tempfile
            
            # Get video duration using ffprobe
            duration_cmd = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)
            ]
            
            result = subprocess.run(
                duration_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning(f"Could not get video duration: {result.stderr}")
                return frames
            
            try:
                duration = float(result.stdout.strip())
            except ValueError:
                logger.warning(f"Invalid duration: {result.stdout}")
                return frames
            
            # Create temporary directory for frames
            temp_dir = Path(tempfile.mkdtemp())
            
            # Calculate frame extraction times
            if duration <= 0:
                return frames
            
            interval = duration / (count + 1)  # +1 to avoid very beginning/end
            
            # Extract frames
            for i in range(count):
                time_seconds = interval * (i + 1)
                
                output_path = temp_dir / f"frame_{i+1:03d}.jpg"
                
                cmd = [
                    'ffmpeg', '-ss', str(time_seconds),
                    '-i', str(video_path),
                    '-vframes', '1',
                    '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
                    '-q:v', '2',  # Quality (2 = high, 31 = low)
                    '-y',  # Overwrite output
                    str(output_path)
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0 and output_path.exists():
                    # Optimize image
                    await self._optimize_image(output_path)
                    frames.append(output_path)
                else:
                    logger.warning(f"Frame extraction failed at {time_seconds}s: {stderr.decode()}")
            
            return frames
            
        except Exception as e:
            logger.error(f"Frame extraction error: {str(e)}")
            return frames
    
    async def _apply_thumbnail_style(
        self,
        image_path: Path,
        style: str,
        width: int,
        height: int
    ) -> Optional[Path]:
        """Apply style to thumbnail image"""
        try:
            import cv2
            import numpy as np
            
            # Get style parameters
            style_params = THUMBNAIL_STYLES.get(style, THUMBNAIL_STYLES['cinematic'])
            
            # Load image
            image = cv2.imread(str(image_path))
            if image is None:
                return None
            
            # Resize if needed
            if image.shape[1] != width or image.shape[0] != height:
                image = cv2.resize(image, (width, height))
            
            # Apply brightness, contrast, saturation
            image = image.astype(np.float32)
            
            # Brightness
            image = image * style_params['brightness']
            image = np.clip(image, 0, 255)
            
            # Contrast
            mean = np.mean(image)
            image = (image - mean) * style_params['contrast'] + mean
            image = np.clip(image, 0, 255)
            
            # Convert to appropriate type
            image = image.astype(np.uint8)
            
            # Save result
            output_path = Path(tempfile.mktemp(suffix='.jpg'))
            cv2.imwrite(str(output_path), image)
            
            # Optimize
            await self._optimize_image(output_path)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Style application failed: {str(e)}")
            return None
    
    async def _generate_ai_thumbnails(
        self,
        titles: List[str],
        style: str,
        count: int,
        width: int,
        height: int
    ) -> List[Path]:
        """Generate AI-powered thumbnails based on titles"""
        ai_thumbnails = []
        
        try:
            # Use Stability AI for image generation
            provider = self.providers.get('stability')
            if not provider:
                logger.warning("Stability AI provider not available")
                return ai_thumbnails
            
            # Generate prompt from titles
            prompt = self._create_ai_prompt(titles, style)
            
            # Generate image
            result = await provider.generate_image(
                prompt=prompt,
                width=width,
                height=height,
                count=count
            )
            
            if result.success:
                images = result.data.get('images', [])
                for i, image_data in enumerate(images[:count]):
                    # Save image to temporary file
                    import tempfile
                    output_path = Path(tempfile.mktemp(suffix='.png'))
                    
                    if isinstance(image_data, bytes):
                        with open(output_path, 'wb') as f:
                            f.write(image_data)
                    elif isinstance(image_data, str):
                        # Assume base64 encoded
                        import base64
                        image_bytes = base64.b64decode(image_data)
                        with open(output_path, 'wb') as f:
                            f.write(image_bytes)
                    
                    # Convert to JPEG and optimize
                    jpeg_path = await self._convert_to_jpeg(output_path)
                    if jpeg_path:
                        ai_thumbnails.append(jpeg_path)
                    
                    # Clean up original
                    output_path.unlink(missing_ok=True)
            
            return ai_thumbnails
            
        except Exception as e:
            logger.error(f"AI thumbnail generation failed: {str(e)}")
            return ai_thumbnails
    
    async def _upload_thumbnails(self, thumbnail_paths: List[str]) -> List[str]:
        """Upload thumbnails to storage service"""
        urls = []
        
        try:
            from .storage_service import StorageService
            storage_service = StorageService(self.config)
            
            for path in thumbnail_paths:
                upload_result = storage_service.upload_thumbnail(Path(path))
                if upload_result.success:
                    urls.append(upload_result.data.get('url', ''))
            
            return urls
            
        except Exception as e:
            logger.error(f"Thumbnail upload failed: {str(e)}")
            return urls
    
    async def _upload_thumbnail(self, thumbnail_path: Path) -> Optional[str]:
        """Upload single thumbnail to storage"""
        try:
            from .storage_service import StorageService
            storage_service = StorageService(self.config)
            
            upload_result = storage_service.upload_thumbnail(thumbnail_path)
            if upload_result.success:
                return upload_result.data.get('url')
            
            return None
            
        except Exception as e:
            logger.error(f"Thumbnail upload failed: {str(e)}")
            return None
    
    async def _score_frame_quality(self, frame_path: Path) -> float:
        """Score frame quality for thumbnail selection"""
        try:
            import cv2
            import numpy as np
            
            image = cv2.imread(str(frame_path))
            if image is None:
                return 0.0
            
            scores = []
            
            # 1. Sharpness (Laplacian variance)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            sharpness = np.var(laplacian)
            scores.append(min(sharpness / 1000, 1.0))  # Normalize
            
            # 2. Brightness (avoid too dark or too bright)
            brightness = np.mean(gray)
            brightness_score = 1.0 - abs(brightness - 127.5) / 127.5
            scores.append(brightness_score)
            
            # 3. Contrast (standard deviation)
            contrast = np.std(gray)
            contrast_score = min(contrast / 64, 1.0)
            scores.append(contrast_score)
            
            # 4. Colorfulness
            # Split channels
            b, g, r = cv2.split(image.astype("float"))
            
            # Compute rg = R - G
            rg = np.absolute(r - g)
            
            # Compute yb = 0.5 * (R + G) - B
            yb = np.absolute(0.5 * (r + g) - b)
            
            # Compute mean and standard deviation
            rg_mean, rg_std = np.mean(rg), np.std(rg)
            yb_mean, yb_std = np.mean(yb), np.std(yb)
            
            # Compute colorfulness
            std_root = np.sqrt((rg_std ** 2) + (yb_std ** 2))
            mean_root = np.sqrt((rg_mean ** 2) + (yb_mean ** 2))
            colorfulness = std_root + (0.3 * mean_root)
            color_score = min(colorfulness / 100, 1.0)
            scores.append(color_score)
            
            # Weighted average
            weights = [0.3, 0.2, 0.25, 0.25]  # Sharpness most important
            final_score = sum(s * w for s, w in zip(scores, weights))
            
            return final_score
            
        except Exception as e:
            logger.warning(f"Frame scoring failed: {str(e)}")
            return 0.5  # Default score
    
    async def _enhance_frame(
        self,
        frame_path: Path,
        width: int,
        height: int
    ) -> Optional[Path]:
        """Apply enhancements to frame"""
        try:
            import cv2
            import numpy as np
            
            image = cv2.imread(str(frame_path))
            if image is None:
                return None
            
            # Resize
            image = cv2.resize(image, (width, height))
            
            # Basic enhancements
            # 1. Contrast Limited Adaptive Histogram Equalization (CLAHE)
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            enhanced_lab = cv2.merge((cl, a, b))
            image = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
            
            # 2. Slight sharpening
            kernel = np.array([[-1, -1, -1],
                               [-1,  9, -1],
                               [-1, -1, -1]])
            image = cv2.filter2D(image, -1, kernel)
            
            # Save enhanced image
            output_path = Path(tempfile.mktemp(suffix='.jpg'))
            cv2.imwrite(str(output_path), image)
            
            # Optimize
            await self._optimize_image(output_path)
            
            return output_path
            
        except Exception as e:
            logger.warning(f"Frame enhancement failed: {str(e)}")
            return None
    
    async def _apply_style_to_image(self, image, style: str):
        """Apply style to image array"""
        import cv2
        import numpy as np
        
        style_params = THUMBNAIL_STYLES.get(style, THUMBNAIL_STYLES['cinematic'])
        
        # Convert to float for processing
        img_float = image.astype(np.float32)
        
        # Brightness
        img_float = img_float * style_params['brightness']
        img_float = np.clip(img_float, 0, 255)
        
        # Contrast
        mean = np.mean(img_float)
        img_float = (img_float - mean) * style_params['contrast'] + mean
        img_float = np.clip(img_float, 0, 255)
        
        # Saturation (simplified - convert to HSV and adjust)
        hsv = cv2.cvtColor(img_float.astype(np.uint8), cv2.COLOR_BGR2HSV)
        hsv = hsv.astype(np.float32)
        hsv[:, :, 1] = hsv[:, :, 1] * style_params['saturation']
        hsv = np.clip(hsv, 0, 255)
        img_float = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        
        return img_float.astype(np.uint8)
    
    async def _add_text_overlay(self, image, title: str, subtitle: str = None, style: str = 'cinematic'):
        """Add text overlay to image"""
        import cv2
        import numpy as np
        
        height, width = image.shape[:2]
        
        # Create copy for text overlay
        result = image.copy()
        
        # Determine text color based on style
        if style in ['dark', 'cinematic']:
            text_color = (255, 255, 255)  # White
            shadow_color = (0, 0, 0)  # Black
        else:
            text_color = (0, 0, 0)  # Black
            shadow_color = (255, 255, 255)  # White
        
        # Calculate font scale based on title length
        title_words = title.split()
        avg_word_len = sum(len(word) for word in title_words) / len(title_words) if title_words else 0
        
        if avg_word_len > 8 or len(title_words) > 6:
            font_scale = 1.8
        elif avg_word_len > 5 or len(title_words) > 4:
            font_scale = 2.2
        else:
            font_scale = 2.8
        
        # Ensure font fits within width
        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = 3
        
        # Wrap text if too long
        max_width = width * 0.8
        wrapped_lines = []
        current_line = ""
        
        for word in title_words:
            test_line = f"{current_line} {word}".strip()
            (text_width, _), _ = cv2.getTextSize(test_line, font, font_scale, thickness)
            
            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    wrapped_lines.append(current_line)
                current_line = word
        
        if current_line:
            wrapped_lines.append(current_line)
        
        # Draw text with shadow for better readability
        line_height = int(70 * font_scale)
        start_y = height - (len(wrapped_lines) * line_height) - 100
        
        if subtitle:
            start_y -= 50
        
        for i, line in enumerate(wrapped_lines):
            y = start_y + (i * line_height)
            
            # Get text size
            (text_width, text_height), baseline = cv2.getTextSize(
                line, font, font_scale, thickness
            )
            
            # Center text
            x = (width - text_width) // 2
            
            # Draw shadow (slightly offset)
            cv2.putText(
                result, line,
                (x + 2, y + 2),
                font, font_scale,
                shadow_color, thickness + 2,
                cv2.LINE_AA
            )
            
            # Draw main text
            cv2.putText(
                result, line,
                (x, y),
                font, font_scale,
                text_color, thickness,
                cv2.LINE_AA
            )
        
        # Add subtitle if provided
        if subtitle:
            sub_font_scale = font_scale * 0.6
            sub_thickness = 2
            
            (sub_width, sub_height), _ = cv2.getTextSize(
                subtitle, font, sub_font_scale, sub_thickness
            )
            
            sub_x = (width - sub_width) // 2
            sub_y = start_y + (len(wrapped_lines) * line_height) + 30
            
            # Draw subtitle shadow
            cv2.putText(
                result, subtitle,
                (sub_x + 1, sub_y + 1),
                font, sub_font_scale,
                shadow_color, sub_thickness + 1,
                cv2.LINE_AA
            )
            
            # Draw subtitle
            cv2.putText(
                result, subtitle,
                (sub_x, sub_y),
                font, sub_font_scale,
                text_color, sub_thickness,
                cv2.LINE_AA
            )
        
        return result
    
    def _create_ai_prompt(self, titles: List[str], style: str) -> str:
        """Create prompt for AI image generation"""
        # Combine titles
        combined_title = " ".join(titles[:2])  # Use first 2 titles
        
        # Style-specific prompts
        style_prompts = {
            'cinematic': "cinematic, dramatic lighting, film still, professional photography, 8k",
            'minimal': "minimalist, clean design, simple, elegant, white space, modern",
            'vibrant': "vibrant colors, energetic, dynamic, colorful, eye-catching, pop art style",
            'dark': "dark mood, mysterious, dramatic shadows, noir style, low light",
            'bright': "bright, cheerful, sunny, happy, optimistic, high key lighting",
            'retro': "retro style, vintage, 80s aesthetic, grainy film, nostalgic"
        }
        
        style_desc = style_prompts.get(style, style_prompts['cinematic'])
        
        prompt = f"{combined_title}. {style_desc}. Professional YouTube thumbnail, trending on art station, detailed, high quality"
        
        return prompt
    
    async def _optimize_image(self, image_path: Path, quality: int = 85):
        """Optimize image file size"""
        try:
            from PIL import Image
            
            img = Image.open(image_path)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Save optimized
            img.save(image_path, 'JPEG', quality=quality, optimize=True)
            
        except Exception as e:
            logger.warning(f"Image optimization failed: {str(e)}")
    
    async def _convert_to_jpeg(self, image_path: Path) -> Optional[Path]:
        """Convert image to JPEG format"""
        try:
            from PIL import Image
            
            img = Image.open(image_path)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Save as JPEG
            jpeg_path = Path(tempfile.mktemp(suffix='.jpg'))
            img.save(jpeg_path, 'JPEG', quality=90, optimize=True)
            
            return jpeg_path
            
        except Exception as e:
            logger.warning(f"JPEG conversion failed: {str(e)}")
            return None
    
    def _update_statistics(
        self,
        style: str,
        provider: str,
        success: bool,
        duration: float,
        count: int = 1
    ):
        """Update service statistics"""
        # Update style stats
        if style not in self.stats['by_style']:
            self.stats['by_style'][style] = {
                'count': 0,
                'successful': 0,
                'total_duration': 0.0
            }
        
        style_stats = self.stats['by_style'][style]
        style_stats['count'] += count
        if success:
            style_stats['successful'] += count
        style_stats['total_duration'] += duration
        
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
        self.stats['total_thumbnails'] += count
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get thumbnail service statistics"""
        return {
            **self.stats,
            'available_providers': list(self.providers.keys()),
            'supported_styles': list(THUMBNAIL_STYLES.keys())
        }