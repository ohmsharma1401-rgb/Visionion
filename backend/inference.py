"""Explicit demo, real health classifier, and optional onion-trained YOLO segmentation."""
import json
import hashlib
import math
import os
from pathlib import Path
from functools import lru_cache
from PIL import Image, ImageOps
from backend.grading.validators import polygon_area

ROOT=Path(__file__).resolve().parents[1]
ALL_MODEL_PATH=ROOT/'ml/models/bulb-health-all-v2.pt'
ALL_METADATA_PATH=ROOT/'ml/models/bulb-health-all-v2.json'
NEW_MODEL_PATH=ROOT/'ml/models/bulb-health-v3.pt'
NEW_METADATA_PATH=ROOT/'ml/models/bulb-health-v3.json'
MODEL_PATH=NEW_MODEL_PATH if NEW_MODEL_PATH.exists() and NEW_METADATA_PATH.exists() else ALL_MODEL_PATH if ALL_MODEL_PATH.exists() and ALL_METADATA_PATH.exists() else ROOT/'ml/models/bulb-health-v1.pt'
METADATA_PATH=NEW_METADATA_PATH if MODEL_PATH==NEW_MODEL_PATH else ALL_METADATA_PATH if MODEL_PATH==ALL_MODEL_PATH else ROOT/'ml/models/bulb-health-v1.json'
LIMITATIONS=['AI detects visible characteristics only. Internal rot, pesticide residue, moisture, firmness, smell, microbial infection and hidden defects cannot be reliably determined from these images.', 'Physical size needs a reference in the same plane; overlapping or partially hidden onions cannot be measured reliably.']

def model_info():
    trained=MODEL_PATH.exists() and METADATA_PATH.exists()
    metadata=json.loads(METADATA_PATH.read_text()) if trained else None
    return {'demo_enabled':os.getenv('DEMO_MODE','true').lower()=='true','health_model_available':trained,'health_model':metadata,'segmentation_available':bool(os.getenv('ONION_SEG_WEIGHTS')),
            'supported_real_labels':['HEALTHY_BULB','UNHEALTHY_BULB','LEAF_ONLY'] if trained else [],
            'limitations':LIMITATIONS+['The supplied dataset contains image-level health labels, no per-onion masks or defect subtype labels. Whole-image screening classifies the photo as a whole; it does not locate or count separate bulbs. User-drawn regions remain optional for individual bulb classification.']}

@lru_cache(maxsize=1)
def health_model():
    import torch
    from torchvision import models,transforms
    if not MODEL_PATH.exists() or not METADATA_PATH.exists(): raise RuntimeError('Bulb-health model has not finished training.')
    if hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()!=json.loads(METADATA_PATH.read_text())['sha256']:
        raise RuntimeError('Model weights do not match the evaluated checkpoint hash.')
    checkpoint=torch.load(MODEL_PATH,map_location='cpu',weights_only=True)
    model=models.mobilenet_v3_small(weights=None)
    model.classifier[3]=torch.nn.Linear(model.classifier[3].in_features,len(checkpoint['labels']))
    model.load_state_dict(checkpoint['state_dict']);model.eval()
    torch.set_num_threads(4)
    transform=transforms.Compose([transforms.Resize((160,160)),transforms.ToTensor(),transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
    return model,transform,checkpoint['labels']

def health_predict(image:Image.Image):
    import torch
    model,transform,labels=health_model()
    prepared=ImageOps.pad(image.convert('RGB'),(256,256),color=(127,127,127))
    with torch.inference_mode(): probs=model(transform(prepared).unsqueeze(0)).softmax(1)[0].tolist()
    index=max(range(len(probs)),key=probs.__getitem__)
    return labels[index],probs[index],dict(zip(labels,probs))

def validate_regions(regions,width,height):
    if not isinstance(regions,list) or not 1<=len(regions)<=100: raise ValueError('Supply 1–100 onion polygons.')
    for polygon in regions:
        if not isinstance(polygon,list) or not 3<=len(polygon)<=200: raise ValueError('Each onion outline requires 3–200 points.')
        for point in polygon:
            if not isinstance(point,list) or len(point)!=2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in point) or not 0<=point[0]<=width or not 0<=point[1]<=height:
                raise ValueError('Region points must be finite and inside the image.')
        if polygon_area(polygon)<25: raise ValueError('Onion region is too small.')
    return regions

def detection(identifier,polygon,label,confidence,defects=None,source='demo'):
    xs=[p[0] for p in polygon];ys=[p[1] for p in polygon]
    return {'id':identifier,'class':label,'confidence':confidence,'bbox':[min(xs),min(ys),max(xs),max(ys)],'mask':polygon,'centroid':[sum(xs)/len(xs),sum(ys)/len(ys)],'diameter_mm':None,'defects':defects or [],'region_source':source,'visibility_issues':[]}

def infer(image,mode,scenario='multiple',regions=None):
    width,height=image.size
    if mode=='demo':
        if not model_info()['demo_enabled']: raise RuntimeError('Demo inference is disabled.')
        if scenario=='calibrated_sample':
            polygons=validate_regions(regions,width,height)
            return [detection(i+1,polygon,'GOOD',.93,source='demo_sample_outline') for i,polygon in enumerate(polygons)],'mock-calibrated-sample-v1'
        if scenario=='no_onion': return [],'mock-instance-v2'
        labels=['GOOD'] if scenario=='single' else ['GOOD','GOOD','DAMAGED','ROTTEN','SPROUTED','REVIEW_REQUIRED']
        output=[]
        for i,label in enumerate(labels):
            cx,cy=(width*.5,height*.5) if len(labels)==1 else (width*(.2+.3*(i%3)),height*(.29+.42*(i//3)))
            rx,ry=(width*.22,height*.28) if len(labels)==1 else (width*.11,height*.15)
            poly=[[round(cx+rx*math.cos(t*math.pi/16),2),round(cy+ry*math.sin(t*math.pi/16),2)] for t in range(32)]
            kind={'DAMAGED':'MECHANICAL_INJURY','ROTTEN':'ROTTING','SPROUTED':'SPROUTED'}.get(label)
            output.append(detection(i+1,poly,label,.42 if label=='REVIEW_REQUIRED' or scenario=='uncertain' else .93,[{'type':kind,'confidence':.91}] if kind else []))
        return output,'mock-instance-v2'
    if mode=='health':
        supplied=regions is not None
        polygons=validate_regions(regions,width,height) if supplied else [[[0,0],[width,0],[width,height],[0,height]]]
        output=[]
        threshold=json.loads(METADATA_PATH.read_text())['confidence_threshold'] if METADATA_PATH.exists() else .8
        for i,polygon in enumerate(polygons):
            d=detection(i+1,polygon,'REVIEW_REQUIRED',0,source='user_outline' if supplied else 'whole_image_health_screen')
            box=d['bbox'];crop=image.crop(tuple(map(int,box)))
            label,confidence,probabilities=health_predict(crop)
            d.update(health_label=label,confidence=confidence,health_probabilities=probabilities)
            if label=='LEAF_ONLY':
                d['classification_warnings']=['The model classified this photo as leaf-only and cannot assess bulb health. This may be a misclassification; it does not prove that onions are absent. Try a close-up of one intact bulb.']
            d['class']='GOOD' if label=='HEALTHY_BULB' and confidence>=threshold else 'REVIEW_REQUIRED'
            d['eligibility_blocked']='This model predicts broad bulb health only. Specific defect checks needed for Grade A were not trained; manual review is required.'
            if label=='UNHEALTHY_BULB': d['defects']=[{'type':'UNSPECIFIED_VISIBLE_UNHEALTHY','confidence':confidence}]
            if confidence<threshold: d.setdefault('classification_warnings',[]).append(f'Health confidence is below the validation-selected {threshold:.2f} review threshold.')
            if not supplied: d['mask']=None
            output.append(d)
        return output,json.loads(METADATA_PATH.read_text())['model_version']
    if mode=='segmentation':
        weights=os.getenv('ONION_SEG_WEIGHTS')
        if not weights: raise RuntimeError('No onion-trained segmentation weights configured. The supplied ZIP has no masks for supervised segmentation training.')
        from ultralytics import YOLO
        result=YOLO(weights).predict(image,verbose=False,conf=.1,max_det=100)[0]
        if result.masks is None: return [],Path(weights).stem
        mapping={'good':'GOOD','healthy':'GOOD','damaged':'DAMAGED','rotten':'ROTTEN','sprouted':'SPROUTED','undersized':'UNDERSIZED'}
        output=[]
        for i,box in enumerate(result.boxes):
            source=result.names[int(box.cls.item())].lower()
            if source not in mapping: raise RuntimeError(f'Unsupported segmentation label {source}. Configure a model with documented onion classes.')
            label=mapping[source];kind={'DAMAGED':'MECHANICAL_INJURY','ROTTEN':'ROTTING','SPROUTED':'SPROUTED'}.get(label)
            confidence=float(box.conf.item())
            output.append(detection(i+1,result.masks.xy[i].tolist(),label,confidence,[{'type':kind,'confidence':confidence}] if kind else [],'model_segmentation'))
        return output,Path(weights).stem
    raise ValueError('Unsupported inference mode')
