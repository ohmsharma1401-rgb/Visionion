"""Real adapter for a separately trained segmentation model. Not used by demo API."""
import math
from ultralytics import YOLO

def infer(weights, image, mm_per_px=None):
    result=YOLO(weights).predict(image,verbose=False)[0]
    detections=[]
    for i,box in enumerate(result.boxes):
        mask=result.masks.data[i].cpu().numpy() if result.masks is not None else None
        # Area-equivalent diameter is approximate and unreliable for occluded onions.
        area=float(mask.sum()) if mask is not None else None
        scale=result.orig_shape[1]/mask.shape[1] if mask is not None else 1
        diameter=2*math.sqrt(area/math.pi)*scale*mm_per_px if area and mm_per_px else None
        detections.append({'class_name':result.names[int(box.cls.item())],'confidence':float(box.conf.item()),'bbox':box.xyxy[0].cpu().tolist(),'diameter_mm':diameter,'mask':mask.tolist() if mask is not None else None})
    return detections
