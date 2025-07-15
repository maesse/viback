import os
from pathlib import Path
from configparser import ConfigParser

# Default configuration
config = ConfigParser()
config['DEFAULT'] = {
    'database_url': 'sqlite:///data/videos.db',
    'media_folders': 'C:/Users/YourUser/Videos,C:/Users/YourUser/Downloads',  # Comma-separated paths
    'thumbnail_dir': 'static/thumbnails',
    'thumbnail_count': '3',  # Number of thumbnails per video
    'thumbnail_width': '320',
    'supported_extensions': '.mp4,.m4v,.wmv,.mkv,.avi,.flv,.mov,.webm'
}

config['IMAGE_TAGGER'] = {
    'prompt': "You are an AI that generates descriptive tags for video frames"
}

config['THUMBNAILS'] = {
    'thumbnail_dir': 'static/thumbnails',
    'thumbnail_count': '3',
    'thumbnail_width': '480',
    'thumbnail_height': '480'
}

config['PREVIEWS'] = {
    'preview_dir': 'static/previews',
    'preview_width': '480',
    'preview_height': '480',
    'preview_duration': '2',
    'preview_clips': '5',
    'preview_crf': '25',
    'preview_fps': '24'
}

# Create config file if it doesn't exist
config_path = Path('data/config.ini')
if not config_path.exists():
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        config.write(f)

def get_config():
    """Load and return the configuration"""
    # Read the persisted config file to get user changes
    user_config = ConfigParser()
    user_config.read(config_path)
    return user_config

def get_media_folders():
    """Get list of media folders to scan"""
    cfg = get_config()
    return [f.strip() for f in cfg['DEFAULT']['media_folders'].split(',')]

def get_supported_extensions():
    """Get list of supported file extensions"""
    cfg = get_config()
    return [e.strip() for e in cfg['DEFAULT']['supported_extensions'].split(',')]
