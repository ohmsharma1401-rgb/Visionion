"""Generate explicitly synthetic camera-gate fixtures, not training data."""
from pathlib import Path
from PIL import Image, ImageDraw
import random

out=Path('samples');out.mkdir(exist_ok=True)
for seed in range(3):
    rng=random.Random(seed)
    image=Image.new('RGB',(800,600),(105+seed*4,110,82))
    draw=ImageDraw.Draw(image)
    for y in range(0,600,5): draw.line((0,y,800,y),fill=(95,100,75))
    for row in range(4):
        for col in range(5):
            x=55+col*145+rng.randrange(-8,8);y=65+row*125+rng.randrange(-8,8)
            draw.ellipse((x,y,x+95,y+92),fill=(170+rng.randrange(30),120,125),outline=(75,42,54),width=3)
            for offset in (15,28,40): draw.arc((x+offset,y,x+95-offset,y+92),80,280,fill=(110,65,82),width=2)
            draw.polygon([(x+42,y+3),(x+50,y-14),(x+58,y+3)],fill=(160,140,72))
    draw.rectangle((0,0,800,30),fill=(35,65,48));draw.text((10,8),'SYNTHETIC DEMO IMAGE - NOT REAL ONIONS',fill='white')
    image.save(out/f'synthetic-sample-{seed+1}.jpg',quality=95)
