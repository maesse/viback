import os
import ffmpeg
from datetime import datetime
from database import SessionLocal
from models import Video, Thumbnail, Task
from config import get_config
import logging
from sqlalchemy.orm import Session
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_metadata(db: Session):
    """Extract metadata for videos without complete info"""
    # Get videos needing metadata
    videos = db.query(Video).filter(Video.duration == None).all()
    
    for video in videos:
        try:
            process_video_metadata(db, video)
        except Exception as e:
            logger.error(f"Failed to process {video.path}: {e}")
            continue

def process_video_metadata(db: Session, video: Video):
    """Extract metadata and generate thumbnails for a video"""
    if not os.path.exists(video.path):
        logger.warning(f"File not found: {video.path}")
        return
        
    try:
        # Get video metadata
        probe = ffmpeg.probe(video.path)
        video_stream = next(
            (stream for stream in probe['streams'] if stream['codec_type'] == 'video'),
            None
        )
        
        if video_stream:
            # Update video metadata
            video.duration = float(probe['format']['duration'])
            video.codec = video_stream['codec_name']
            video.width = int(video_stream['width'])
            video.height = int(video_stream['height'])
            video.size = os.path.getsize(video.path)
            
            db.commit()
            logger.info(f"Processed metadata for {video.path}")

            task = Task(
                type='preview',
                status='pending',
                payload=str(video.id),
                created_at=datetime.utcnow()
            )
            db.add(task)
            task = Task(
                type='thumbnail',
                status='pending',
                payload=str(video.id),
                created_at=datetime.utcnow()
            )
            db.add(task)
            db.commit()
            
    except Exception as e:
        logger.error(f"Error processing {video.path}: {e}")
        raise
