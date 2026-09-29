import math

def polygon_area(points: list[list[float]]) -> float:
    if len(points) < 3:
        return 0.0
    return abs(sum(points[i][0] * points[(i+1)%len(points)][1] - points[(i+1)%len(points)][0] * points[i][1] for i in range(len(points)))) / 2

def calibration_scale(reference_mm: float | None, points: list[list[float]] | None, width: int, height: int) -> dict:
    if reference_mm is None and points is None:
        return {'available': False, 'mm_per_pixel': None, 'reference_mm': None, 'points': None, 'method': 'unavailable', 'message': 'Physical size cannot be reliably estimated without a reference scale.'}
    if reference_mm is None or not isinstance(points,list) or len(points) != 2:
        raise ValueError('Provide a known reference length and two endpoints on that reference.')
    if not math.isfinite(reference_mm) or not 0 < reference_mm <= 1000:
        raise ValueError('Reference length must be between 0 and 1000 mm.')
    for point in points:
        if not isinstance(point,list) or len(point) != 2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in point) or not 0 <= point[0] <= width or not 0 <= point[1] <= height:
            raise ValueError('Calibration endpoints must lie within the image.')
    pixels = math.dist(points[0], points[1])
    if pixels < 10:
        raise ValueError('Reference endpoints must be at least 10 pixels apart.')
    return {'available': True, 'mm_per_pixel': reference_mm / pixels, 'reference_mm': reference_mm, 'points': points, 'reference_pixels': pixels, 'method': 'user_reference_line', 'message': 'Area-equivalent diameter; reference and onions must lie in the same plane. Perspective and occlusion cause error.'}

def diameter_from_polygon(points: list[list[float]], mm_per_pixel: float | None) -> float | None:
    if mm_per_pixel is None:
        return None
    if not math.isfinite(mm_per_pixel) or mm_per_pixel <= 0:
        raise ValueError('Invalid calibration scale')
    area = polygon_area(points)
    return round(2 * math.sqrt(area / math.pi) * mm_per_pixel, 2) if area > 0 else None
