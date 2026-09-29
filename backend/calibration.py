"""Detect a printable ArUco reference; reject unreliable perspective."""
from __future__ import annotations

import json
import math
from io import BytesIO
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def size_config() -> dict:
    config = json.loads((ROOT / 'config' / 'size_bands.json').read_text())
    bands = config['bands']
    if config['official'] or config['reference_width_mm'] <= 0 or not bands:
        raise ValueError('Invalid demonstration size configuration.')
    for index, band in enumerate(bands):
        if band['min_mm'] < 0 or (band['max_mm'] is not None and band['max_mm'] <= band['min_mm']):
            raise ValueError('Invalid size band boundaries.')
        if index and band['min_mm'] != bands[index-1]['max_mm']:
            raise ValueError('Size bands must be continuous.')
    return config


def size_category(diameter_mm: float | None) -> str | None:
    if diameter_mm is None:
        return None
    for band in size_config()['bands']:
        if band['min_mm'] <= diameter_mm and (band['max_mm'] is None or diameter_mm < band['max_mm']):
            return band['name']
    return None


def _aruco():
    import cv2
    if not hasattr(cv2, 'aruco'):
        raise RuntimeError('OpenCV ArUco support is unavailable.')
    return cv2


def _marker_pattern() -> np.ndarray:
    # OpenCV DICT_4X4_50 marker 0, first orientation bytes B5 32.
    bits = np.unpackbits(np.array([181, 50], dtype=np.uint8)).reshape(4, 4)
    pattern = np.zeros((6, 6), dtype=np.uint8)
    pattern[1:5, 1:5] = bits
    return pattern


def marker_image(pixels: int = 800) -> Image.Image:
    try:
        cv2 = _aruco()
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        marker = cv2.aruco.generateImageMarker(dictionary, 0, pixels)
        return Image.fromarray(marker)
    except (ImportError,RuntimeError):
        pattern = _marker_pattern()
        output = Image.fromarray(np.where(pattern == 1, 255, 0).astype(np.uint8))
        return output.resize((pixels, pixels), Image.Resampling.NEAREST)


def marker_pdf() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    output = BytesIO()
    sheet = canvas.Canvas(output, pagesize=A4)
    width = float(size_config()['reference_width_mm'])
    x, y = 28*mm, A4[1]-85*mm
    sheet.setFont('Helvetica-Bold', 16)
    sheet.drawString(x, A4[1]-30*mm, 'OnionGrade calibration marker')
    sheet.setFont('Helvetica', 10)
    sheet.drawString(x, A4[1]-40*mm, 'Print at 100% / actual size. Do not fit to page.')
    sheet.drawImage(ImageReader(marker_image()), x, y, width=width*mm, height=width*mm)
    sheet.drawString(x, y-9*mm, f'ArUco 4x4 ID 0 - black square width {width:g} mm')
    sheet.drawString(x, y-16*mm, 'Verify the printed width with a ruler before use.')
    sheet.drawString(x, y-23*mm, 'Place flat beside the onion in the same plane.')
    sheet.save()
    return output.getvalue()


def detect_reference(image: Image.Image) -> dict | None:
    try: cv2 = _aruco()
    except (ImportError,RuntimeError): return _detect_reference_fallback(image)
    gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    corners, ids, _ = cv2.aruco.ArucoDetector(dictionary).detectMarkers(gray)
    if ids is None:
        return None
    matches = [i for i, marker_id in enumerate(ids.flatten()) if marker_id == 0]
    if len(matches) != 1:
        raise ValueError('Expected one visible 50 mm marker. Remove duplicates or retake the photo.')
    points = corners[matches[0]][0].astype(float)
    sides = [float(np.linalg.norm(points[(i+1)%4]-points[i])) for i in range(4)]
    if min(sides) < 40:
        raise ValueError('Reference marker is too small. Move the camera closer.')
    if any(x <= 3 or x >= image.width-3 or y <= 3 or y >= image.height-3 for x,y in points):
        raise ValueError('Keep the whole reference marker inside the frame.')
    angles = []
    for i in range(4):
        a = points[(i-1)%4]-points[i]
        b = points[(i+1)%4]-points[i]
        cosine = float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)))
        angles.append(math.degrees(math.acos(max(-1,min(1,cosine)))))
    if max(sides)/min(sides) > 1.18 or max(abs(a-90) for a in angles) > 12:
        raise ValueError('Measurement unreliable. Keep the camera parallel to the surface.')
    pixel_width = float(sum(sides[0::2])/2)
    pixel_height = float(sum(sides[1::2])/2)
    physical = float(size_config()['reference_width_mm'])
    return {
        'available': True,
        'mm_per_pixel': physical / ((pixel_width+pixel_height)/2),
        'reference_mm': physical,
        'reference_width_mm': physical,
        'reference_height_mm': physical,
        'reference_pixel_width': round(pixel_width,2),
        'reference_pixel_height': round(pixel_height,2),
        'reference_pixels': round((pixel_width+pixel_height)/2,2),
        'points': points.tolist(),
        'method': 'reference_marker',
        'message': 'Estimated using the printed 50 mm marker. Marker and onion must be in the same plane; this is not a validated caliper measurement.',
    }


def _detect_reference_fallback(image: Image.Image) -> dict | None:
    """Strict square-marker reader for local machines without OpenCV.

    Handles a nearly axis-aligned marker only. Rejects uncertain patterns;
    OpenCV ArUco handles rotated and skewed markers in deployment.
    """
    factor = min(1, 1000 / max(image.size))
    reduced = image.convert('L')
    if factor < 1:
        reduced = reduced.resize((round(image.width*factor), round(image.height*factor)))
    gray = np.asarray(reduced, dtype=np.uint8)
    h, w = gray.shape
    dark = gray < 105
    expected = _marker_pattern()
    patterns = [np.rot90(expected, turns) for turns in range(4)]
    found = []
    visited = set()
    for y in range(2, h-42, 3):
        transitions = np.diff(np.pad(dark[y].astype(np.int8), (1, 1)))
        starts = np.flatnonzero(transitions == 1)
        ends = np.flatnonzero(transitions == -1)
        for x1, x2 in zip(starts, ends):
            side = int(x2-x1)
            if side < 40 or side > min(w,h)*.75 or x1 < 3 or x2 >= w-3:
                continue
            key = (x1//3, x2//3, y//3)
            if key in visited:
                continue
            visited.add(key)
            for ratio in (1.0, .92, 1.08):
                height = side*ratio
                if y+height >= h-3:
                    continue
                cols = np.clip(np.round(x1+(np.arange(6)+.5)*side/6).astype(int),0,w-1)
                rows = np.clip(np.round(y+(np.arange(6)+.5)*height/6).astype(int),0,h-1)
                sampled = gray[np.ix_(rows, cols)]
                bits = (sampled > 128).astype(np.uint8)
                errors = min(int(np.count_nonzero(bits != pattern)) for pattern in patterns)
                if errors <= 1 and float(sampled.max()-sampled.min()) > 100:
                    found.append((errors,x1,y,x2,y+height))
                    break
    if not found:
        return None
    found.sort()
    _,x1,y1,x2,y2 = found[0]
    side_px = float(((x2-x1)+(y2-y1))/2/factor)
    physical = float(size_config()['reference_width_mm'])
    return {
        'available': True, 'mm_per_pixel': physical/side_px,
        'reference_mm': physical, 'reference_width_mm': physical,
        'reference_height_mm': physical,
        'reference_pixel_width': float(round((x2-x1)/factor,2)),
        'reference_pixel_height': float(round((y2-y1)/factor,2)),
        'reference_pixels': round(side_px,2),
        'points': [[float(round(x1/factor,2)),float(round(y1/factor,2))],
                   [float(round(x2/factor,2)),float(round(y1/factor,2))],
                   [float(round(x2/factor,2)),float(round(y2/factor,2))],
                   [float(round(x1/factor,2)),float(round(y2/factor,2))]],
        'method': 'reference_marker',
        'message': 'Estimated using the printed 50 mm marker. Local fallback requires a nearly square, upright marker; both objects must be in the same plane.',
    }
