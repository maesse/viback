import os
from pathlib import Path
from sqlalchemy.orm import Session
from models import Video, Task, VideoTagSet
from config import get_supported_extensions
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def scan_media_folders(db: Session, media_folders: list[str]):
    """Scan media folders for video files"""
    extensions = get_supported_extensions()
    
    try:
        for folder in media_folders:
            folder_path = Path(folder)
            if not folder_path.exists():
                logger.warning(f"Folder not found: {folder}")
                continue
                
            for ext in extensions:
                for file_path in folder_path.rglob(f'*{ext}', case_sensitive=False):
                    process_video_file(db, file_path)
        
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise

def process_video_file(db: Session, file_path: Path):
    """Process a single video file and update database"""

    # Check if video already exists
    file_path = str(file_path.absolute())
    id = Video.id_for_path(file_path)
    video = db.get(Video, id)

    if video:
        # Check if something is missing
        # if not db.query(VideoTagSet).filter(VideoTagSet.video_id == id).first() and not db.query(Task).filter(Task.type == 'tag', Task.payload == id).first():
        #     task = Task(
        #         type='tag',
        #         status='pending',
        #         payload=id,
        #     )
        #     db.add(task)
        #     db.commit()
        #     logger.info(f"Missing tags, adding tag job to task queue: {file_path}")
        return
    else:
        # Add new video entry
        video = Video(
            path=file_path,
            filename=os.path.basename(file_path)
        )
        db.add(video)
        db.commit()
        logger.info(f"Added new video: {file_path}")