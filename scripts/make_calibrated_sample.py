"""Create an explicitly synthetic sample for demonstrating marker calibration."""
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.calibration import marker_image

width, height = 960, 640
rng = np.random.default_rng(42)
background = np.zeros((height,width,3),dtype=np.uint8)
noise = rng.normal(0,5,(height,width)).clip(-15,15)
for channel,base in enumerate((176,182,165)):
    background[:,:,channel] = np.clip(base+noise,0,255)
image = Image.fromarray(background,'RGB')
onion = Image.new('RGBA',(width,height),(0,0,0,0))
draw = ImageDraw.Draw(onion)
draw.ellipse((458,183,742,457),fill=(148,60,45,255),outline=(95,37,31,255),width=4)
for inset in (16,34,55,78):
    draw.arc((458+inset,183+inset,742-inset,457-inset),35,310,fill=(190,94,68,110),width=3)
draw.line([(596,188),(601,154),(606,182)],fill=(87,68,40,255),width=7)
image = Image.alpha_composite(image.convert('RGBA'),onion.filter(ImageFilter.GaussianBlur(.8))).convert('RGB')
marker = marker_image(230).convert('RGB')
image.paste(marker,(65,85))
draw = ImageDraw.Draw(image)
draw.text((65,329),'SYNTHETIC SAMPLE / NOT A CALIPER MEASUREMENT',fill=(33,49,35))
destination = ROOT/'web/public/demo-calibrated-sample.jpg'
image.save(destination,quality=93)
print(destination)
