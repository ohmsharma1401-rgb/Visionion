from pathlib import Path
from collections import defaultdict
from PIL import Image, ImageOps, ImageDraw
from io import BytesIO
import zipfile

archive=Path('ml/datasets/raw/onion-source.zip')
groups=defaultdict(list)
with zipfile.ZipFile(archive) as z:
    for name in z.namelist():
        if '/2. Bulb/' in name and name.lower().endswith('.jpg'):
            groups[name.rsplit('/',1)[0]].append(name)
    sheet=Image.new('RGB',(1000,len(groups)*145),'white');draw=ImageDraw.Draw(sheet)
    for row,(folder,entries) in enumerate(sorted(groups.items())):
        draw.text((8,row*145+3),folder.split('/2. Bulb/')[1],fill='black')
        for col,index in enumerate([0,len(entries)//4,len(entries)//2,3*len(entries)//4,len(entries)-1]):
            image=Image.open(BytesIO(z.read(entries[index]))).convert('RGB')
            image.thumbnail((192,115));sheet.paste(image,(col*200,row*145+23))
    Path('output').mkdir(exist_ok=True)
    sheet.save('output/dataset-contact-sheet.jpg')
