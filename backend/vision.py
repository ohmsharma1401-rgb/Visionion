import hashlib
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError, ImageDraw
import numpy as np

ALLOWED_MIME={'image/jpeg':'JPEG','image/png':'PNG','image/webp':'WEBP'}
COLORS={'GOOD':'#4b9661','DAMAGED':'#da933d','ROTTEN':'#c85555','SPROUTED':'#9877bf','UNDERSIZED':'#4e98b4','REVIEW_REQUIRED':'#d3a839'}

def validate_image(content:bytes,mime:str,limits:dict):
    if mime not in ALLOWED_MIME: raise ValueError('Allowed image types: JPEG, PNG and WebP.')
    if not content: raise ValueError('The image is empty.')
    if len(content)>8*1024*1024: raise ValueError('Maximum image size is 8 MB.')
    try:
        with Image.open(BytesIO(content)) as raw:
            if raw.format!=ALLOWED_MIME[mime]: raise ValueError('Image contents do not match the supplied MIME type.')
            if raw.width*raw.height>limits['max_pixels']: raise ValueError('Image exceeds the 24-megapixel limit.')
            if min(raw.size)<limits['min_dimension']: raise ValueError(f"Image resolution must be at least {int(limits['min_dimension'])} pixels on each side.")
            raw.load();image=ImageOps.exif_transpose(raw).convert('RGB')
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError) as exc:
        raise ValueError('Unsupported or corrupt image.') from exc
    gray=np.asarray(image.convert('L'),dtype=np.float32)
    lap=gray[:-2,1:-1]+gray[2:,1:-1]+gray[1:-1,:-2]+gray[1:-1,2:]-4*gray[1:-1,1:-1]
    blur=float(lap.var());brightness=float(gray.mean());glare=float((gray>245).mean());reasons=[]
    if blur<limits['min_laplacian_variance']: reasons.append('Too blurry: hold the camera steady and refocus.')
    if brightness<limits['min_brightness']: reasons.append('Too dark: use diffuse daylight.')
    if brightness>limits['max_brightness']: reasons.append('Excessive brightness: reduce exposure.')
    if glare>limits['max_glare_fraction']: reasons.append('Excessive glare: avoid direct light.')
    return image,{'usable':not reasons,'blur_score':round(blur,2),'brightness':round(brightness,2),'glare_fraction':round(glare,4),'width':image.width,'height':image.height,'reasons':reasons,'sha256':hashlib.sha256(content).hexdigest()}

def check_visibility(detections,width,height,limits):
    for d in detections:
        if d['region_source']=='user_confirmed_single_image': continue
        x1,y1,x2,y2=d['bbox']
        if x1<=1 or y1<=1 or x2>=width-1 or y2>=height-1: d['visibility_issues'].append('Onion partially outside frame or touching the image edge.')
    overlapping=set()
    for i,a in enumerate(detections):
        for j,b in enumerate(detections[:i]):
            x1,y1,x2,y2=a['bbox'];u1,v1,u2,v2=b['bbox']
            intersection=max(0,min(x2,u2)-max(x1,u1))*max(0,min(y2,v2)-max(y1,v1))
            union=(x2-x1)*(y2-y1)+(u2-u1)*(v2-v1)-intersection
            if union>0 and intersection/union>limits['max_overlap_iou']: overlapping.update([i,j])
    for index in overlapping: detections[index]['visibility_issues'].append('Overlapping regions may hide the onion boundary.')
    return bool(detections and len(overlapping)/len(detections)>limits['max_occluded_fraction'])

def annotated_image(image,detections,calibration,demo=False):
    out=image.copy();draw=ImageDraw.Draw(out)
    for d in detections:
        color=COLORS[d['class']];box=d['bbox']
        if d.get('mask'): draw.line([tuple(p) for p in d['mask']]+[tuple(d['mask'][0])],fill=color,width=max(2,image.width//300))
        else: draw.rectangle(box,outline=color,width=3)
        label=f"#{d['id']} {d.get('health_label',d['class'])} {d['confidence']:.0%}"
        if d.get('diameter_mm') is not None:
            label+=f" {d['diameter_mm']:.1f}mm {d.get('size_category') or ''}"
        x,y=box[:2];draw.rectangle((x,max(0,y-17),min(image.width,x+len(label)*6+8),max(0,y-17)+17),fill=color)
        draw.text((x+3,max(0,y-15)),label,fill='white')
    if calibration['available']:
        points=[tuple(p) for p in calibration['points']]
        draw.line(points+[points[0]] if len(points)==4 else points,fill='#00bce0',width=3)
    if demo: draw.rectangle((0,0,image.width,22),fill='#704d1b');draw.text((8,5),'DEMO ANALYSIS - MOCK BOUNDARIES / FINDINGS',fill='white')
    return out
