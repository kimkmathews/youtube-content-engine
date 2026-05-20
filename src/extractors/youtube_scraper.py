import re
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
from src.core.schema import VideoMetadata

class YouTubeScraper:
    def __init__(self):
        self.url_pattern = re.compile(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')

    def extract_video_id(self, url: str) -> str:
        match = self.url_pattern.search(url)
        if not match:
            raise ValueError(f"Invalid YouTube URL: {url}")
        return match.group(6)

    def get_metadata(self, url: str) -> VideoMetadata:
        try:
            ydl_opts = {'quiet': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
            video_id = self.extract_video_id(url)
            return VideoMetadata(
                video_id=video_id,
                title=info.get('title', 'Unknown Title'),
                channel_name=info.get('uploader', 'Unknown Channel'),
                description=info.get('description', ''),
                length_seconds=info.get('duration', 0)
            )
        except Exception as e:
            raise RuntimeError(f"Failed to extract metadata: {str(e)}")

    def get_transcript(self, video_id: str) -> str:
        try:
            transcript_list = YouTubeTranscriptApi().fetch(video_id)
            full_text = " ".join([entry.text for entry in transcript_list])
            # Basic cleanup of newlines and extra spaces
            full_text = re.sub(r'\s+', ' ', full_text).strip()
            return full_text
        except Exception as e:
            raise RuntimeError(f"Failed to extract transcript: {str(e)}")
