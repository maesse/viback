import os
import ffmpeg
import logging
import json
from sqlalchemy.orm import Session

from config import get_config
from models import Video

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_preview(db: Session, video: Video):
    # Load configuration
    config = get_config()
    num_clips = int(config['PREVIEWS']['preview_clips'])
    duration = float(config['PREVIEWS']['preview_duration'])
    fps = int(config['PREVIEWS']['preview_fps'])
    crf = int(config['PREVIEWS']['preview_crf'])
    width = int(config['PREVIEWS']['preview_width'])
    height = int(config['PREVIEWS']['preview_height'])

    # Ensure the output directory exists
    preview_dir = config['PREVIEWS']['preview_dir']
    os.makedirs(preview_dir, exist_ok=True)

    # Generate output file path
    base_name = video.id
    output_file = os.path.join(preview_dir, f"{base_name}_preview.mp4")

    if video.duration < 10:
        try:
            (
            ffmpeg
                .input(video.path, hwaccel='cuda', hwaccel_output_format='cuda')
                .filter('scale_cuda', w=width, h=height, force_original_aspect_ratio='decrease')
                .output(output_file, vcodec='h264_nvenc', cq=crf, b='0', an=None, r=fps, preset='p1')
                .overwrite_output()
                .run()
            )
            video.preview_path = output_file  # Save the preview path in the video model
            db.commit()
        except ffmpeg.Error as e:
            logger.error(f"Thumbnail generation failed: {e.stderr.decode()}")
            raise
    else:
        spacing = video.duration / (num_clips + 1)

        try:
            inputs = []

            for i in range(num_clips):
                start = spacing * (i + 1)
                stream = ffmpeg.input(video.path, ss=start, t=duration)
                # gpu_frame = stream.video.filter('hwupload_cuda')
                scaled = stream.video.filter('scale', w=width, h=height, force_original_aspect_ratio='decrease')
                inputs.append(scaled)

            filter_inputs = [s.video for s in inputs]
            joined = ffmpeg.concat(*inputs, n={num_clips}, v=1, a=0).node
            (
                ffmpeg
                .output(joined[0],
                        output_file, 
                        # map='[outv]',
                        vcodec='h264_nvenc',
                        cq=crf,
                        b='0',
                        an=None,
                        r=fps,
                        preset='p1')
                
                .overwrite_output()
                # .global_args('-filter_complex', filter_complex)
                .run()
            )

            video.preview_path = output_file  # Save the preview path in the video model
            db.commit()
        except ffmpeg.Error as e:
            logger.error(f"Thumbnail generation failed: {e.stderr.decode()}")
            raise