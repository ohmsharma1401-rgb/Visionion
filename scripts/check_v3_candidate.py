"""Check representative original ZIP photos through production inference."""
from io import BytesIO
import json
from pathlib import Path
import sys
import time
import zipfile
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.inference import infer,model_info
from backend.grading.visual_grade import grade_health
from backend.grading import load_spec
from backend.vision import validate_image

def main():
    info=model_info()['health_model'];assert info['model_version']=='bulb-health-v3'
    out=ROOT/'output/v3-training';rows=json.loads((out/'representative-sources.json').read_text());results=[]
    with zipfile.ZipFile(ROOT/'ml/datasets/raw/new-onion-source.zip') as archive:
        for i,row in enumerate(rows):
            content=archive.read(row['source']);image,quality=validate_image(content,'image/jpeg',load_spec().quality)
            image.save(out/f'sample-{i+1:02d}-original.jpg')
            started=time.perf_counter();detections,version=infer(image,'health')
            grade=grade_health(detections,info['confidence_threshold'])
            results.append({'source':row['source'],'source_label':row['label'],'multiple_bulbs':row['multiple_bulbs'],
                'quality':quality,'prediction':detections[0]['health_label'],'confidence':detections[0]['confidence'],
                'visual_grade':grade,'inference_seconds':round(time.perf_counter()-started,4),
                'model_version':version,'note':'Original test image diagnostic; includes predictions even if the API quality gate would reject it.'})
    (out/'runtime-check.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))

if __name__=='__main__': main()
