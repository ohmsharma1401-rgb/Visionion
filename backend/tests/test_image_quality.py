from io import BytesIO
import numpy as np
from PIL import Image
from backend.vision import validate_image

LIMITS={'max_pixels':24000000,'min_dimension':128,'min_laplacian_variance':35,
        'min_brightness':40,'max_brightness':225,'max_glare_fraction':0.25}

def assess(pixels):
    stream=BytesIO();Image.fromarray(pixels).save(stream,format='PNG')
    return validate_image(stream.getvalue(),'image/png',LIMITS)[1]

def fixture():
    pixels=np.full((256,256,3),255,dtype=np.uint8)
    pixels[40:216,40:216]=np.random.default_rng(7).integers(70,180,(176,176,3),dtype=np.uint8)
    return pixels

def test_white_background_is_not_glare():
    result=assess(fixture())
    assert result['usable'] and result['glare_fraction']==0
    assert result['bright_background_fraction']>0.5

def test_internal_clipped_highlight_still_blocks():
    pixels=fixture();pixels[70:186,70:186]=255
    result=assess(pixels)
    assert not result['usable'] and result['glare_fraction']>0.25
    assert 'Excessive glare: avoid direct light.' in result['reasons']

def test_blank_overexposed_frame_still_blocks():
    result=assess(np.full((256,256,3),255,dtype=np.uint8))
    assert not result['usable']
    assert 'Excessive brightness: reduce exposure.' in result['reasons']
