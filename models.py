import hashlib
import os
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, Mapped
from sqlalchemy import LargeBinary
from datetime import datetime
from sqlalchemy import JSON
from sqlalchemy.orm import Session

from config import get_media_folders

from typing import List, Optional, TYPE_CHECKING
from pydantic import BaseModel

if TYPE_CHECKING:
    from models import Thumbnail, Video, VideoTagSet

class ThumbnailSchema(BaseModel):
    path: str
    timestamp: Optional[float] = None

    class Config:
        orm_mode = True

class VideoSchema(BaseModel):
    id: int
    path: str
    searchpath: str
    filename: str
    size: int
    duration: float
    codec: str
    width: int
    height: int
    filename_metadata: Optional[dict] = None
    preview_path: Optional[str] = None
    thumbnail_paths: list[str] = []
    tags: list[str] = []
    torrent_tags: Optional[list[str]] = []

    class Config:
        orm_mode = True

Base = declarative_base()

def normalize_path(path: str) -> str:
        return os.path.normpath(os.path.abspath(path))

def hash_path_to_int(path: str) -> int:
    # Use SHA-256 and take the first 8 bytes to convert to int
    return int(hashlib.sha256(path.encode()).hexdigest()[:8], 16)

class VideoTagSet(Base):
    __tablename__ = 'video_tag_sets'

    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey('videos.id'), nullable=False)
    tags = Column(JSON)  # List of tags
    prompt = Column(String)  # The prompt used for generation
    created_at = Column(DateTime, default=datetime.utcnow)
    video: Mapped["Video"] = relationship("Video", back_populates="tag_sets")

class Video(Base):
    __tablename__ = 'videos'
    
    id = Column(Integer, primary_key=True)
    path = Column(String, unique=True, nullable=False)
    searchpath = Column(String)
    filename = Column(String)
    size = Column(Integer)  # in bytes
    duration = Column(Float)  # in seconds
    codec = Column(String)
    width = Column(Integer)
    height = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    preview_path = Column(String)  # Path to the generated preview video
    filename_metadata = Column(JSON)  # Metadata extracted from filename
    thumbnails: Mapped[List["Thumbnail"]] = relationship("Thumbnail", back_populates="video")
    tag_sets: Mapped[List["VideoTagSet"]] = relationship("VideoTagSet", back_populates="video")
    torrent_file_id = Column(Integer, ForeignKey('torrent_files.id'))
    torrent_file: Mapped[Optional["TorrentFile"]] = relationship("TorrentFile", uselist=False)
    torrent_tags = Column(JSON, nullable=True)  # List of tags from the torrent file

    @property
    def thumbnail_paths(self):
        # Return a list of thumbnail paths, excluding any that are None or empty
        return [t.path for t in self.thumbnails if t.path]

    @property
    def tags(self):
        # Flatten all tags from all tag_sets into a single list
        all_tags = []
        for tag_set in self.tag_sets:
            if tag_set.tags:
                all_tags.extend(tag_set.tags)
        return list(set(all_tags))  # Remove duplicates if needed

    # @property
    # def torrent_tags(self):
    #     if self.torrent_file and self.torrent_file.torrent.taglist:
    #         return self.torrent_file.torrent.taglist
    #     return []

    @staticmethod
    def id_for_path(path: str) -> int:
        """Generate a unique ID for a given path."""
        normalized_path = normalize_path(path)
        return hash_path_to_int(normalized_path)
    
    @staticmethod
    def generate_search_path(fullpath: str) -> str | None:
        folders = [normalize_path(os.path.abspath(folder)) for folder in get_media_folders()]
        search_path = None
        for prefix in folders:
            if fullpath.startswith(prefix):
                search_path = fullpath[len(prefix):].lstrip()
                break
        if search_path.startswith('\\'):
            search_path = search_path[1:]
        return search_path

    def __init__(self, **kwargs):
        path = kwargs.get("path")
        if not path:
            raise ValueError("path is required for Video")
        
        normalized_path = normalize_path(path)
        self.id = hash_path_to_int(normalized_path)
        self.path = normalized_path
        self.searchpath = Video.generate_search_path(normalized_path)
        for key, value in kwargs.items():
            if key != "path":  # already handled
                setattr(self, key, value)

class Thumbnail(Base):
    __tablename__ = 'thumbnails'
    
    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey('videos.id'))
    path = Column(String)  # Static thumbnail path
    timestamp = Column(Float)  # in seconds
    
    video: Mapped["Video"] = relationship("Video", back_populates="thumbnails")

class Torrent(Base):
    __tablename__ = 'torrents'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    taglist = Column(JSON, nullable=True)  # List of tags
    files: Mapped[List["TorrentFile"]] = relationship("TorrentFile", back_populates="torrent")
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, name: str, description: str, taglist: List[str], files: List["TorrentFile"]):
        self.name = name
        self.description = description
        self.taglist = taglist
        self.files = files

class TorrentFile(Base):
    __tablename__ = 'torrent_files'
    
    id = Column(Integer, primary_key=True)
    torrent_id = Column(Integer, ForeignKey('torrents.id'), nullable=False)
    path = Column(String, nullable=False)  # Path to the file in the torrent
    size = Column(Integer, nullable=False)  # Size of the file in bytes
    created_at = Column(DateTime, default=datetime.utcnow)

    torrent: Mapped["Torrent"] = relationship("Torrent", back_populates="files")

class Task(Base):
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True)
    type = Column(String)  # 'scan', 'metadata', 'thumbnail'
    status = Column(String)  # 'pending', 'processing', 'completed', 'failed'
    payload = Column(String)  # JSON data
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    def complete(self, db: Session):
        """Mark the task as completed."""
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        db.commit()

    def fail(self, db: Session):
        """Mark the task as failed."""
        self.status = 'failed'
        db.commit()