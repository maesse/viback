import asyncio
import os
from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from typing import Callable, List
from sqlalchemy.orm import Session, defer, joinedload
from models import Task, TorrentFile, Video, VideoSchema, VideoTagSet
from database import SessionLocal, get_db
from config import get_config, get_media_folders
from range import range_requests_response
from tasks import process_queue
from query import ParsedQuery, parse_query_string, search_query
from vector_index import search_similar_from_video
from pyinstrument import Profiler
from pyinstrument.renderers.html import HTMLRenderer
from pyinstrument.renderers.speedscope import SpeedscopeRenderer

app = FastAPI(title="Video Backend API")


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for thumbnails
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def read_root():
    return {"message": "Video Backend API"}

@app.get("/videos", response_model=List[VideoSchema])
def list_videos(db: Session = Depends(get_db)):
    # profiler = Profiler()
    # profiler.start()
    
    videos = (
        db.query(Video)
        .filter(Video.duration > 1)
        .options(
            joinedload(Video.thumbnails),
            joinedload(Video.tag_sets)
        )
        .all()
    )
    # profiler.stop()

    # # we dump the profiling into a file
    # with open(f"profiler/profile2.speedscope.json", "w") as out:
    #     out.write(profiler.output(renderer=SpeedscopeRenderer()))
    return videos

@app.get("/videos/search", response_model=List[VideoSchema])
def search_videos(q: str = Query(..., description="Search query"), limit: int = 10, rerank: bool = True, db: Session = Depends(get_db)):
    profiler = Profiler()
    profiler.start()
        
    parsed_query: ParsedQuery = parse_query_string(q)
    terms = parsed_query["terms"]
    tags = parsed_query["filters"].get("tag")
    path = parsed_query["filters"].get("path")
    vision = parsed_query["filters"].get("vision")

    videos = search_query(db, terms=terms, tags=tags, path=path, vision=vision, limit=limit, rerank=rerank)

    profiler.stop()
    # we dump the profiling into a file
    with open(f"profiler/profile.speedscope.json", "w") as out:
        out.write(profiler.output(renderer=SpeedscopeRenderer()))

    return videos

@app.get("/videos/{video_id}/similar", response_model=List[VideoSchema])
def get_similar_videos_by_id(video_id: int, limit: int = 20, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="No video found for this video")
    result = search_similar_from_video(db, video, k = limit)
    return result

@app.get("/videos/{video_id}", response_model=VideoSchema)
def get_video_details(video_id: int, db: Session = Depends(get_db)):
    """Get detailed metadata for a video"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return video

@app.get("/videos/{video_id}/stream.mp4")
async def stream_video(
    video_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Stream video file with HTTP Range support"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video or not os.path.exists(video.path):
        raise HTTPException(status_code=404, detail="Video not found")

    return range_requests_response(
        request, file_path=video.path, content_type="video/mp4"
    )

@app.get("/videos/{video_id}/stream.avi")
async def stream_video(
    video_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Stream video file with HTTP Range support"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video or not os.path.exists(video.path):
        raise HTTPException(status_code=404, detail="Video not found")

    return range_requests_response(
        request, file_path=video.path, content_type="video/avi"
    )

@app.post("/scan")
def trigger_scan(db: Session = Depends(get_db)):
    """Trigger a new media scan"""
    media_folders = get_media_folders()
    # Create scan task
    task = Task(
        type='scan',
        status='pending',
        payload=str(media_folders)
    )
    db.add(task)
    db.commit()

    return {"status": "scan task created."}


@app.on_event("startup")
async def startup_event():
    db: Session = SessionLocal()
    videos = db.query(Video).filter(Video.torrent_file_id == None).all()
    for video in videos:
        torrentfile_search = video.searchpath.replace("\\", "/")  # Ensure search path is in correct format
        results = db.query(TorrentFile).filter(TorrentFile.path == torrentfile_search).all()
        if results:
            if len(results) > 1:
                print(f"Warning: Multiple torrent files found for video {video.id}: {results}")
            else:
                video.torrent_file = results[0]
                db.commit()
                print(f"Updated video {video.id} with torrent file {results[0].id}")
    
    videos = db.query(Video).filter(Video.torrent_tags == None).all()
    for video in videos:
        if video.torrent_file and video.torrent_file.torrent and video.torrent_file.torrent.taglist:
            video.torrent_tags = video.torrent_file.torrent.taglist
            db.commit()
            print(f"Updated video {video.id} with torrent tags {video.torrent_tags}")
    db.close()
    asyncio.create_task(process_queue())  # fire and forget background loop

if __name__ == "__main__":
    import uvicorn
    config = get_config()
    uvicorn.run(app, host=config['DEFAULT'].get('host', '0.0.0.0'), 
               port=int(config['DEFAULT'].get('port', '8088')))
