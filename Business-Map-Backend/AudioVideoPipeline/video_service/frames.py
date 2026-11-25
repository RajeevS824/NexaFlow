###############################################################
# VIDEO SERVICE — FRAMES
# Video frame extraction using OpenCV
###############################################################

import logging
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)


def extract_frames(video_path: str, frames_dir: str) -> dict:
    """
    Extract one frame per second from a video file into JPEG images.

    Args:
        video_path:  Path to the input video file.
        frames_dir:  Directory where extracted frames will be saved.

    Returns:
        {
            "fps":          float,
            "total_frames": int,
            "duration_sec": float,
            "saved_count":  int,
            "frames_dir":   str,
        }

    Raises:
        FileNotFoundError: if video_path does not exist.
        RuntimeError:      if OpenCV cannot open the video.
    """
    video = Path(video_path)
    out_dir = Path(frames_dir)

    if not video.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps

    logger.info(
        f"Video opened | fps={fps:.2f} | total_frames={total_frames} "
        f"| duration={duration_sec:.1f}s"
    )

    frame_interval = int(fps)   # one frame per second
    count          = 0
    saved_count    = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if count % frame_interval == 0:
            out_path = out_dir / f"frame_{saved_count:04d}.jpg"
            cv2.imwrite(str(out_path), frame)
            saved_count += 1
        count += 1

    cap.release()

    logger.info(f"Frame extraction done — {saved_count} frames saved to {out_dir}")

    return {
        "fps":          fps,
        "total_frames": total_frames,
        "duration_sec": duration_sec,
        "saved_count":  saved_count,
        "frames_dir":   str(out_dir),
    }


def list_frame_files(frames_dir: str) -> list:
    """Return sorted list of .jpg frame Paths from frames_dir."""
    return sorted(Path(frames_dir).glob("*.jpg"))
