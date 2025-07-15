# Video Backend API

A Python backend for managing and streaming video files with metadata extraction and thumbnail generation.

## Features

- Scan folders for video files
- Extract video metadata (duration, codec, resolution)
- Generate thumbnails automatically
- REST API for accessing video information
- Video streaming capability
- SQLite database storage

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Install FFmpeg (required for video processing):

- Windows: Download from https://ffmpeg.org/
- macOS: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`

3. Configure media folders:
   Edit `config.ini` to specify your media folders:

```ini
[DEFAULT]
media_folders = /path/to/videos,/another/path
```

## Running the API

```bash
python main.py
```

The API will be available at http://localhost:8000

## API Endpoints

- `GET /` - Basic info
- `GET /videos` - List all videos
- `GET /videos/{id}` - Get video details
- `GET /videos/{id}/stream` - Stream video
- `POST /scan` - Trigger new scan

## Usage

1. First scan your media folders:

```bash
curl -X POST http://localhost:8000/scan
```

2. List all videos:

```bash
curl http://localhost:8000/videos
```

3. Stream a video:
   Open in browser: http://localhost:8000/videos/1/stream
