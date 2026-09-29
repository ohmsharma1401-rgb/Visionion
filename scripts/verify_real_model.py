"""Exercise actual trained weights through the live API using held-out source images."""
import json
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[1]
rows=json.loads((root/'ml/datasets/prepared/manifest.json').read_text())
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=120) as client:
    token=client.post('/api/auth/login',json={'username':'inspector','password':(root/'data/local-demo-password.txt').read_text().strip()}).json()['access_token']
    headers={'Authorization':'Bearer '+token};results=[]
    for label in ['HEALTHY_BULB','UNHEALTHY_BULB','LEAF_ONLY']:
        row=next(r for r in rows if r['split']=='test' and r['label']==label)
        path=root/'ml/datasets/prepared'/row['path']
        response=client.post('/api/analyze',headers=headers,files={'image':(path.name,path.read_bytes(),'image/jpeg')},data={'mode':'health','single_onion_confirmed':'true'})
        results.append({'source_label':label,'status':response.status_code,'result':response.json()})
        if response.status_code==200:
            record=response.json();assert not record['demo'] and record['model_version']=='bulb-health-v1'
            assert record['grade_a_percentage'] is None and record['urs_percentage'] is None and record['quality_score'] is None
            assert all(d['diameter_mm'] is None for d in record['detections'])
            if label=='HEALTHY_BULB':
                report=client.post('/api/report/'+record['id'],headers=headers).json()
                (root/'output/pdf/trained-health-report.pdf').write_bytes(client.get(report['pdf_url'],headers=headers).content)
                (root/'output/real-test-image.jpg').write_bytes(path.read_bytes())
    (root/'output/real-model-api-check.json').write_text(json.dumps(results,indent=2))
    print(json.dumps([{'label':r['source_label'],'http_status':r['status'],'predictions':[d.get('health_label') for d in r['result'].get('detections',[])]} for r in results],indent=2))
