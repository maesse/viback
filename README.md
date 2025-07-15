# Video Backend API

A Python backend for managing, searching, and streaming video files with advanced metadata extraction, AI-powered tagging, and semantic search capabilities.

## Features

- **File Scanning**: Recursively scans specified folders for video files.
- **Metadata Extraction**: Extracts technical metadata like duration, codec, and resolution using FFmpeg.
- **AI-Powered Tagging**:
  - **Visual Tagging**: Generates descriptive tags from video thumbnails using a Vision Language Model (VLM).
  - **Filename Analysis**: Extracts structured metadata (actors, series, etc.) from filenames using an LLM.
- **Torrent Metadata**: Scans and extracts information from `.torrent` files.
- **Thumbnail & Preview Generation**: Automatically creates image thumbnails and short video previews.
- **Semantic Search**:
  - **Vector Embeddings**: Creates vector embeddings for all collected text metadata for powerful semantic search.
  - **Advanced Querying**: Supports complex search queries with filters for text, tags, and paths (e.g., `beach tag:water path:"folder/"`).
  - **Similarity Search**: Finds visually and textually similar videos.
- **REST API**: Provides endpoints for searching, streaming, and managing video metadata.
- **Task Queue**: Manages heavy processing tasks like scanning and AI analysis in the background.
- **Database**: Uses SQLite for persistent storage of all video metadata.

## Setup

1.  Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

2.  Install FFmpeg (required for video processing):

    - Windows: Download from https://ffmpeg.org/
    - macOS: `brew install ffmpeg`
    - Linux: `sudo apt install ffmpeg`

3.  Configure media folders:
    Edit `data/config.ini` to specify your media folders:

    ```ini
    [DEFAULT]
    media_folders = /path/to/videos,/another/path
    ```

## Running the API

```bash
python main.py
```

The API will be available at http://localhost:8088

## API Endpoints

- `GET /` - Basic info.
- `GET /videos` - List all videos.
- `GET /videos/search` - Perform a search query.
- `GET /videos/{id}` - Get detailed metadata for a single video.
- `GET /videos/{id}/similar` - Find videos similar to the given video.
- `GET /videos/{id}/stream.mp4` - Stream a video file.
- `POST /scan` - Trigger a background task to scan media folders.

## Usage

1.  First, trigger a scan of your media folders. This will start a series of background tasks to process your files (metadata, thumbnails, AI tags, etc.).

    ```bash
    curl -X POST http://localhost:8088/scan
    ```

2.  Search for videos using natural language
