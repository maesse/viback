import ast
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from typing import List
from sqlalchemy.orm import Session
from models import Task, Video, VideoTagSet
from database import SessionLocal
from vector_index import load_faiss_index

executor = ThreadPoolExecutor(max_workers=1)

def generate_embedding(db: Session, arg: str):
    load_faiss_index(db)

def filename_metadata(db: Session, arg: str):
    import asyncio
    from textextractor import extract_tags_from_path
    videos = db.query(Video).filter(Video.filename_metadata == None).all()
    llm_semaphore = asyncio.Semaphore(3)

    async def process_video(video: Video):
        print(f"[worker] Generating filename metadata for video {video.filename}")
        async with llm_semaphore:
            tags = await asyncio.to_thread(extract_tags_from_path, video.searchpath)
        print(tags)
        # Update DB in the main thread
        video.filename_metadata = tags.model_dump()

    async def process_all():
        await asyncio.gather(*(process_video(video) for video in videos))
        db.commit()  # Commit once, in the main thread

    asyncio.run(process_all())

def preview(db: Session, arg: str):
    """Generate a preview for a video."""
    from preview import generate_preview
    video = db.get(Video, arg)
    if not video:
        raise ValueError(f"Video with ID {arg} not found")
    generate_preview(db, video)

def tag(db: Session, arg: str):
    """Generate tags for a video based on its thumbnail."""
    import asyncio
    from imgtagger import generate_tags as generate_tags_impl

    videos = db.query(Video).filter(Video.tag_sets == None, Video.thumbnails != None).all()
    llm_semaphore = asyncio.Semaphore(2)

    async def process_video(video: Video):
        if not video.thumbnails:
            print(f"[worker] No thumbnails for video {video.filename}, skipping.")
            return None
        thumbnail = video.thumbnails[0]
        print(f"[worker] Generating visual tags from screenshot {video.filename}")
        async with llm_semaphore:
            try:
                result = await asyncio.to_thread(generate_tags_impl, thumbnail.path)
            except FileNotFoundError as e:
                print(f"[worker] {e} -- skipping.")
                return None
            except Exception as e:
                print(f"[worker] Error processing {video.filename}: {e}")
                return None
        tag_set = VideoTagSet(
            video_id=video.id,
            tags=result['tags'],
            prompt=result['prompt'],
        )
        return tag_set
            
    async def process_all():
        result = await asyncio.gather(*(process_video(video) for video in videos))
        for tag_set in result:
            if tag_set is not None:
                db.add(tag_set)
        db.commit()  # Commit once, in the main thread

    asyncio.run(process_all())

    # for video in videos:
    #     thumbnail = video.thumbnails[0]
    #     result = generate_tags_impl(thumbnail.path)
    #     tag_set = VideoTagSet(
    #         video_id=video.id,
    #         tags=result['tags'],
    #         prompt=result['prompt'],
    #     )
    #     db.add(tag_set)
    #     db.commit()
    #     db.refresh(tag_set)

def thumbnail(db: Session, arg: str):
    """Generate thumbnails for a video."""
    from thumbnails import generate_thumbnails
    video = db.get(Video, arg)
    if not video:
        raise ValueError(f"Video with ID {arg} not found")
    if not video.duration:
        raise ValueError(f"Video with ID {arg} has no duration, cannot generate thumbnails")
    
    generate_thumbnails(db, video)

def metadata(db: Session, arg: str):
    """Extract metadata for all videos"""
    from metadata import extract_metadata
    extract_metadata(db)

def torrent_tags(db: Session, arg: str):
    """Scan torrent files in a directory and extract metadata"""
    from torrent_metadata import scan_torrent_files
    directory = arg.strip('"')  # Remove quotes if present
    if not directory:
        raise ValueError("Directory path is required")
    scan_torrent_files(db, directory)


def scan(db: Session, arg: str):
    """Scan media folders for video files and process them."""
    from scanner import scan_media_folders

    media_folders: List[str] = ast.literal_eval(arg)
    scan_media_folders(db, media_folders)

    task = Task(
        type='metadata',
        status='pending'
    )
    db.add(task)
    db.commit()
    
TASK_TYPE_FUNCTIONS = {
    "scan": scan,
    "metadata": metadata,
    "preview": preview,
    "thumbnail": thumbnail,
    "filename_metadata": filename_metadata,
    "embedding": generate_embedding,
    "tag": tag,
    "torrent_tags": torrent_tags,
}

def fetch_next_task(db: Session) -> Task | None: 
    task = db.query(Task).filter(Task.status == 'pending').order_by(Task.created_at).first()
    if task:
        task.status = 'processing'
        db.commit()
    return task

async def process_queue():
    db: Session = SessionLocal()
    load_faiss_index(db)
    db.close()

    while True:
        db: Session = SessionLocal()
        try:
            task = fetch_next_task(db)
            if task:
                print(f"[worker] Processing Task: {task.type} - args: {task.payload}")
                try:
                    func = TASK_TYPE_FUNCTIONS.get(task.type)
                    if func is None:
                        print(f"[worker] Unknown task type: {task.type}")
                        task.fail(db)
                    else:
                        await asyncio.to_thread(func, db, task.payload)
                        print(f"[worker] Task Done: {task.type} - args: {task.payload}")
                        task.complete(db)
                except Exception as e:
                    print(f"[worker] Task Error ({task.type} - args: {task.payload}): {e}")
                    task.fail(db)
            else:
                await asyncio.sleep(1)
        finally:
            db.close()