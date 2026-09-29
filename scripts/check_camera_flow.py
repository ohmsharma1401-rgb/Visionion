"""Exercise the calibrated sample through the running local API."""
from pathlib import Path
import json
import math

import httpx

ROOT=Path(__file__).resolve().parents[1]
base='http://127.0.0.1:8000'
password=(ROOT/'data/local-demo-password.txt').read_text().strip()
with httpx.Client(timeout=120) as client:
    health=client.get(base+'/api/health')
    health.raise_for_status()
    marker=client.get(base+'/api/calibration/marker.pdf')
    marker.raise_for_status()
    assert marker.content.startswith(b'%PDF')
    token=client.post(base+'/api/auth/login',json={'username':'inspector','password':password})
    token.raise_for_status()
    headers={'Authorization':'Bearer '+token.json()['access_token']}
    polygon=[[600+142*math.cos(i*2*math.pi/36),320+137*math.sin(i*2*math.pi/36)] for i in range(36)]
    image=(ROOT/'web/public/demo-calibrated-sample.jpg').read_bytes()
    response=client.post(base+'/api/analyze',headers=headers,
        files={'image':('synthetic-calibrated-sample.jpg',image,'image/jpeg')},
        data={'mode':'demo','demo_scenario':'calibrated_sample','regions':json.dumps([polygon]),'require_reference':'true','variety':'Red onion'})
    if response.status_code!=200:
        raise AssertionError(f'Analysis failed with {response.status_code}: {response.text[:500]}')
    record=response.json()
    assert record['calibration']['method']=='reference_marker'
    assert record['detections'][0]['measurement']['diameter_mm'] is not None
    assert record['detections'][0]['size_category'] is not None
    pdf=client.post(base+f"/api/report/{record['id']}",headers=headers)
    pdf.raise_for_status()
    artifact=client.get(base+pdf.json()['pdf_url'],headers=headers)
    artifact.raise_for_status()
    assert artifact.content.startswith(b'%PDF')
    print(json.dumps({'inspection_id':record['id'],'quality_class':record['detections'][0]['class'],
        'calibration':record['calibration']['method'],'diameter_mm':record['detections'][0]['diameter_mm'],
        'size_category':record['detections'][0]['size_category'],'pdf_bytes':len(artifact.content)},indent=2))
