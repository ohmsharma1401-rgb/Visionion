import numpy as np
import pytest
from PIL import Image

from backend.calibration import detect_reference, marker_image, size_category
from backend.grading.validators import calibration_scale
from backend.tests.test_api import client, analyze, auth


def test_known_reference_converts_pixels_to_mm():
    scale = calibration_scale(50, [[10, 10], [210, 10]], 400, 300)
    assert scale['mm_per_pixel'] == .25
    assert 220 * scale['mm_per_pixel'] == 55


def test_demo_size_bands_have_open_upper_bound():
    assert [size_category(value) for value in (44.99, 45, 55, 65)] == [
        'Small', 'Medium', 'Large', 'Extra Large'
    ]
    assert size_category(None) is None


def test_camera_requires_a_visible_reference(client, monkeypatch):
    monkeypatch.setattr('backend.main.detect_reference', lambda image: None)
    response = analyze(client, auth(client), require_reference='true')
    assert response.status_code == 422
    assert 'Reference marker not detected' in response.text


def test_measurement_is_null_without_calibration(client):
    record = analyze(client, auth(client), demo_scenario='single').json()
    finding = record['detections'][0]
    assert finding['diameter_mm'] is None
    assert finding['measurement']['width_mm'] is None
    assert finding['size_category'] is None


def test_printable_marker_is_detected():
    marker = marker_image(400).convert('RGB')
    image = Image.new('RGB', (640, 600), 'white')
    image.paste(marker, (100, 100))
    result = detect_reference(image)
    assert result is not None
    assert result['method'] == 'reference_marker'
    assert result['reference_width_mm'] == 50
    assert 395 <= result['reference_pixel_width'] <= 405


def test_perspective_distortion_is_rejected():
    cv2 = pytest.importorskip('cv2')
    marker = np.asarray(marker_image(400))
    source = np.float32([[0,0],[399,0],[399,399],[0,399]])
    target = np.float32([[90,90],[440,130],[560,500],[30,480]])
    warped = cv2.warpPerspective(marker, cv2.getPerspectiveTransform(source,target),
                                 (640,600), borderValue=255)
    with pytest.raises(ValueError, match='parallel'):
        detect_reference(Image.fromarray(warped).convert('RGB'))


def test_fallback_rejects_stretched_marker(monkeypatch):
    monkeypatch.setattr('backend.calibration._aruco', lambda: (_ for _ in ()).throw(ImportError()))
    marker = marker_image(400).resize((400,260))
    photo = Image.new('RGB',(640,500),'white')
    photo.paste(marker,(100,100))
    assert detect_reference(photo) is None
