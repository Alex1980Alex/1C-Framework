"""
MCP server for scene detection and frame extraction from video files.

Uses PySceneDetect v0.7 API with ContentDetector to identify scene boundaries
(abrupt changes in frame content) and extract representative frames from each
scene segment. Кадр сохраняется на КАЖДУЮ сцену (сегмент между склейками) — не по
таймкоду и не по I-frame'ам; точнее ffmpeg-фильтра select=gt(scene,X).

Source: PySceneDetect v0.7 API (https://www.scenedetect.com/)
"""

import os
from mcp.server.fastmcp import FastMCP

# Scene detection API - Source: PySceneDetect v0.7
from scenedetect import detect, open_video, ContentDetector

# Import save_images with fallback for different PySceneDetect versions
try:
    from scenedetect.output import save_images
except ImportError:
    from scenedetect.scene_manager import save_images


mcp = FastMCP("scene-detect")


@mcp.tool()
def extract_scene_frames(
    video_path: str,
    threshold: float = 27.0,
    output_dir: str = "",
    num_images: int = 1,
) -> dict:
    """
    Extract representative frames at scene boundaries from a video file.

    PySceneDetect uses ContentDetector to identify scene transitions (abrupt
    changes in frame content). For each detected scene, extracts num_images
    frames and saves them to the output directory.

    Args:
        video_path: Path to the input video file (required).
        threshold: ContentDetector sensitivity threshold (default: 27.0).
                   Lower values detect more scene cuts (typically 20-35 range).
                   Higher values require larger content changes.
        output_dir: Output directory for extracted frames. If empty, uses
                    <video_directory>/scene_frames.
        num_images: Number of frames to extract per scene (default: 1).

    Returns:
        Dictionary with keys:
            - ok: True if extraction succeeded, False otherwise.
            - error: Error message if ok is False.
            - count: Number of scenes detected (0 if no scene cuts found).
            - scenes: List of scene metadata dicts with keys:
                n, start, end, start_sec, end_sec.
            - images: List of absolute paths to extracted frame files.
            - output_dir: Absolute path to output directory.
    """
    # Validate input file
    if not os.path.isfile(video_path):
        return {"ok": False, "error": f"Video file not found: {video_path}"}

    # Determine output directory
    if not output_dir:
        video_dir = os.path.dirname(os.path.abspath(video_path))
        output_dir = os.path.join(video_dir, "scene_frames")

    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Source: PySceneDetect v0.7 - detect scene boundaries using ContentDetector
        scenes = detect(video_path, ContentDetector(threshold=float(threshold)))

        # Build scene metadata list
        scene_rows = []
        for i, (start, end) in enumerate(scenes):
            scene_rows.append({
                "n": i + 1,
                "start": str(start),
                "end": str(end),
                "start_sec": round(start.get_seconds(), 3),
                "end_sec": round(end.get_seconds(), 3),
            })

        # Extract and save images
        images = []
        if scene_rows:
            video = open_video(video_path)
            # Source: PySceneDetect v0.7 - save_images() extracts representative frames
            saved = save_images(
                scenes,
                video,
                num_images=int(num_images),
                output_dir=output_dir,
            )

            # Normalize save_images output (dict or list depending on version)
            if isinstance(saved, dict):
                # Dict format: {scene_num: [filenames, ...]}
                for filenames in saved.values():
                    for filename in filenames:
                        if os.path.isabs(filename):
                            images.append(filename)
                        else:
                            images.append(os.path.join(output_dir, filename))
            else:
                # List format: [filename, ...]
                for filename in saved:
                    if os.path.isabs(filename):
                        images.append(filename)
                    else:
                        images.append(os.path.join(output_dir, filename))

        return {
            "ok": True,
            "count": len(scene_rows),
            "scenes": scene_rows,
            "images": images,
            "output_dir": output_dir,
        }

    except Exception as e:
        return {"ok": False, "error": f"Scene detection failed: {str(e)}"}


if __name__ == "__main__":
    mcp.run()
