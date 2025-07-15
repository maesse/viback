import os
import ffmpeg
from models import Video, Thumbnail
from sqlalchemy.orm import Session
from config import get_config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_thumbnails(db: Session, video: Video):
    """Generate thumbnails"""

    # Load configuration
    config = get_config()

    thumbnail_dir = config['THUMBNAILS']['thumbnail_dir']
    os.makedirs(thumbnail_dir, exist_ok=True)

    # Generate static thumbnails
    count = int(config['THUMBNAILS']['thumbnail_count'])
    width = config['THUMBNAILS']['thumbnail_width']
    height = config['THUMBNAILS']['thumbnail_height']
    intervals = [video.duration * (i+1)/(count+1) for i in range(count)]
    try:
        for i, timestamp in enumerate(intervals):
            thumbnail_path = os.path.join(thumbnail_dir, f"{video.id}_{i}.jpg")
            
            # Static thumbnail
            (
                ffmpeg.input(video.path, ss=timestamp)
                .filter('scale', width, height, force_original_aspect_ratio='decrease')
                .output(thumbnail_path, vframes=1)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            # Add to database
            thumbnail = Thumbnail(
                video_id=video.id,
                path=thumbnail_path,
                timestamp=timestamp,
            )
            db.add(thumbnail)
        db.commit()

    except ffmpeg.Error as e:
        logger.error(f"Thumbnail generation failed: {e.stderr.decode()}")