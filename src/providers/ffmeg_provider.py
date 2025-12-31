"""
FFmpeg executor - local video processing (NO API)
"""
import logging
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class FFmpegProvider:
    """
    Executes FFmpeg commands locally
    No API calls - runs on your server
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.ffmpeg_path = self.config.get('FFMPEG_PATH', 'ffmpeg')
        self.ffprobe_path = self.config.get('FFPROBE_PATH', 'ffprobe')
    
    def extract_metadata(self, video_path: Path) -> Dict[str, Any]:
        """Execute ffprobe command to get video metadata"""
        try:
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return {'success': False, 'error': result.stderr}
            
            metadata = json.loads(result.stdout)
            
            # Parse basic info
            streams = metadata.get('streams', [])
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), {})
            audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), {})
            
            return {
                'success': True,
                'duration': float(metadata.get('format', {}).get('duration', 0)),
                'width': video_stream.get('width', 0),
                'height': video_stream.get('height', 0),
                'video_codec': video_stream.get('codec_name'),
                'audio_codec': audio_stream.get('codec_name'),
                'raw_metadata': metadata
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def extract_audio(self, video_path: Path, output_path: Path) -> Dict[str, Any]:
        """Execute ffmpeg command to extract audio"""
        try:
            cmd = [
                self.ffmpeg_path,
                '-i', str(video_path),
                '-vn', '-acodec', 'mp3',
                str(output_path),
                '-y'  # Overwrite output
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return {'success': False, 'error': result.stderr}
            
            return {
                'success': True,
                'output_path': str(output_path)
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def extract_thumbnail(self, video_path: Path, timestamp: float, output_path: Path) -> Dict[str, Any]:
        """Execute ffmpeg command to extract thumbnail frame"""
        try:
            cmd = [
                self.ffmpeg_path,
                '-ss', str(timestamp),
                '-i', str(video_path),
                '-vframes', '1',
                '-q:v', '2',
                str(output_path),
                '-y'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return {'success': False, 'error': result.stderr}
            
            return {
                'success': True,
                'output_path': str(output_path)
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}