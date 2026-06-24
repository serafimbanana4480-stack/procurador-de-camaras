"""
Stream capture — abre streams RTSP, captura screenshots, extrai info.

OpenCV (cv2.VideoCapture) é a implementação primária. Para streams
H.265/hevc, OpenCV pode falhar; aí tenta-se ffmpeg como fallback.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

import cv2

from procurador.core.models import Camera, CameraStatus, StreamInfo
from procurador.utils.helpers import safe_run

logger = logging.getLogger(__name__)


# =====================================================================
# OpenCV
# =====================================================================


def _decode_fourcc(fourcc_int: int) -> str:
    """Descodificar int FOURCC para string codec.

    Devolve string vazia se o fourcc for 0 (codec desconhecido).
    """
    try:
        chars = []
        for i in range(4):
            b = (fourcc_int >> 8 * i) & 0xFF
            if b == 0:
                continue
            # Só aceitar bytes ASCII imprimíveis
            if 32 <= b < 127:
                chars.append(chr(b))
        return "".join(chars) if chars else ""
    except Exception:
        return "Unknown"


def _capture_with_opencv(rtsp_url: str, timeout: float = 5.0) -> dict | None:
    """Tenta abrir stream com OpenCV.

    Returns:
        Dict com {frame, width, height, fps, codec} ou None.
    """
    cap: cv2.VideoCapture | None = None
    try:
        # OpenCV tem timeouts próprios; configuramos via env var
        # OPENCV_FFMPEG_CAPTURE_OPTIONS: timeout em microssegundos, max_delay em segundos
        import os

        timeout_us = int(timeout * 1_000_000)
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            f"rtsp_transport;tcp|timeout;{timeout_us}|max_delay;{int(timeout * 1_000_000)}"
        )

        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        # Aplicar timeout via CAP_PROP também
        try:
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout * 1000))
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(timeout * 1000))
        except Exception:
            pass
        if not cap.isOpened():
            return None

        # Esperar primeiro frame com timeout
        start = time.monotonic()
        deadline = start + timeout
        frame: cv2.Mat | None = None
        while time.monotonic() < deadline:
            ret, f = cap.read()
            if ret and f is not None:
                frame = f
                break
            time.sleep(0.1)

        if frame is None:
            return None

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        codec_int = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = _decode_fourcc(codec_int)

        # Bitrate
        bitrate_kbps: float | None = None
        try:
            br = cap.get(cv2.CAP_PROP_BITRATE)
            if br > 0:
                bitrate_kbps = br / 1000.0
        except Exception:
            pass

        return {
            "frame": frame,
            "width": width,
            "height": height,
            "fps": fps,
            "codec": codec,
            "bitrate_kbps": bitrate_kbps,
        }
    except Exception as e:
        logger.debug(f"opencv capture err: {e}")
        return None
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass


# =====================================================================
# ffmpeg fallback
# =====================================================================


def _capture_with_ffmpeg(rtsp_url: str, output_path: str, timeout: float = 8.0) -> bool:
    """Fallback: usa ffmpeg CLI para capturar 1 frame."""
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        logger.debug("ffmpeg não encontrado no PATH")
        return False

    cmd = [
        ffmpeg_path,
        "-y",
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
        "-vframes",
        "1",
        "-ss",
        "1",  # Skip 1 segundo
        "-timeout",
        str(int(timeout)),
        output_path,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout + 2,
        )
        return result.returncode == 0 and Path(output_path).exists()
    except subprocess.TimeoutExpired:
        logger.debug("ffmpeg timeout")
        return False
    except Exception as e:
        logger.debug(f"ffmpeg err: {e}")
        return False


# =====================================================================
# Main capture
# =====================================================================


def capture_stream(
    camera: Camera,
    screenshot_dir: str = "data/screenshots",
    timeout: float = 5.0,
    try_ffmpeg_fallback: bool = True,
) -> Camera:
    """Captura screenshot de uma câmara LIVE.

    Args:
        camera: Camera (deve ter rtsp_url e status LIVE).
        screenshot_dir: Diretório para guardar screenshots.
        timeout: Timeout total.
        try_ffmpeg_fallback: Se True, tenta ffmpeg se OpenCV falhar.

    Returns:
        Camera atualizada com stream info e screenshot_path.
    """
    if not camera.rtsp_url:
        logger.debug(f"capture_stream: {camera.ip} sem rtsp_url")
        return camera
    if camera.status != CameraStatus.LIVE:
        logger.debug(f"capture_stream: {camera.ip} não está LIVE ({camera.status})")
        return camera

    screenshot_dir_p = Path(screenshot_dir)
    screenshot_dir_p.mkdir(parents=True, exist_ok=True)

    # 1. Tentar OpenCV
    # Reduzir timeout para captura rápida - se não funcionar em 5s, skip
    opencv_timeout = min(timeout, 5.0)
    result = safe_run(_capture_with_opencv, camera.rtsp_url, opencv_timeout, log_errors=False)

    if result and result.get("frame") is not None:
        frame = result["frame"]
        filename = f"{camera.ip.replace('.', '_')}_{int(time.time())}.jpg"
        filepath = screenshot_dir_p / filename
        try:
            cv2.imwrite(str(filepath), frame)
        except Exception as e:
            logger.debug(f"imwrite err: {e}")
            return camera

        camera.stream = StreamInfo(
            codec=result.get("codec"),
            width=result.get("width", 0),
            height=result.get("height", 0),
            fps=result.get("fps", 0.0),
            bitrate_kbps=result.get("bitrate_kbps"),
            url=camera.rtsp_url,
        )
        camera.screenshot_path = str(filepath)
        logger.info(
            f"📸 Screenshot {camera.ip}: {result['width']}x{result['height']} "
            f"{result['codec']} → {filename}"
        )
        return camera

    # 2. Fallback ffmpeg
    if try_ffmpeg_fallback:
        filename = f"{camera.ip.replace('.', '_')}_{int(time.time())}.jpg"
        filepath = screenshot_dir_p / filename
        if _capture_with_ffmpeg(camera.rtsp_url, str(filepath), timeout=timeout):
            camera.screenshot_path = str(filepath)
            logger.info(f"📸 Screenshot (ffmpeg) {camera.ip} → {filename}")
        else:
            logger.debug(f"ffmpeg fallback falhou para {camera.ip}")

    return camera


def capture_batch(
    cameras: list[Camera],
    screenshot_dir: str = "data/screenshots",
    max_workers: int = 4,
    timeout: float = 5.0,
) -> list[Camera]:
    """Captura screenshots de várias câmaras LIVE em paralelo."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    live = [c for c in cameras if c.status == CameraStatus.LIVE and c.rtsp_url]
    if not live:
        logger.info("Nenhuma câmara LIVE para capturar")
        return cameras

    logger.info(f"📸 Capturando {len(live)} streams...")

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(capture_stream, cam, screenshot_dir, timeout): cam.ip for cam in live}
        for fut in as_completed(futures):
            ip = futures[fut]
            try:
                fut.result()
            except Exception as e:
                logger.error(f"Capture {ip} falhou: {e}")

    return cameras
