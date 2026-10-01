import importlib
import hashlib
import json
from io import BytesIO
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path / "test.db"}')
    monkeypatch.setenv('ALLOW_SQLITE_FOR_TESTS','1')
    monkeypatch.setenv('DATA_DIR',str(tmp_path/'images'))
    monkeypatch.setenv('DEMO_PASSWORD','test-password');monkeypatch.setenv('DEMO_MODE','true')
    import backend.main as main
    importlib.reload(main)
    return TestClient(main.app)
def auth(client):
    r=client.post('/api/auth/login',json={'username':'inspector','password':'test-password'});assert r.status_code==200
    return {'Authorization':'Bearer '+r.json()['access_token']}
def sample(color=None,size=(256,256)):
    image=Image.new('RGB',size,color) if color is not None else Image.fromarray(np.random.default_rng(42).integers(45,235,(size[1],size[0],3),dtype=np.uint8))
    buf=BytesIO();image.save(buf,format='JPEG');return buf.getvalue()
def analyze(client,headers=None,content=None,**data):
    return client.post('/api/analyze',headers=headers or auth(client),files={'image':('ignored-name.jpg',sample() if content is None else content,'image/jpeg')},data={'mode':'demo',**data})
def test_complete_demo_pipeline(client):
    headers=auth(client);r=analyze(client,headers,calibration_reference_mm='50',calibration_points='[[10,10],[110,10]]');assert r.status_code==200,r.text
    record=r.json();assert record['demo'] and record['total_onions']==6 and record['urs_percentage'] is None
    assert record['detections'][0]['mask'] and record['detections'][0]['diameter_mm']>0
    identifier=record['id'];assert client.get(record['annotated_url'],headers=headers).status_code==200
    metadata=client.post('/api/report/'+identifier,headers=headers).json();pdf=client.get(metadata['pdf_url'],headers=headers)
    assert hashlib.sha256(pdf.content).hexdigest()==metadata['pdf_sha256']
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    for required in ('DEMO ANALYSIS','Per-onion findings','URS','REVIEW_REQUIRED','SHA-256'): assert required in text
    assert client.get('/api/reports/verify/'+record['report_hash']).json()['valid']
    assert client.get('/api/audit/verify',headers=headers).json()['valid']
    original=client.get(record['image_url'],headers=headers).content
    assert analyze(client,headers,inspection_id=identifier).status_code==409
    assert client.get(record['image_url'],headers=headers).content==original
    Path('output/pdf').mkdir(parents=True,exist_ok=True);Path('output/pdf/analysis-v2-demo.pdf').write_bytes(pdf.content)
@pytest.mark.parametrize('content',[b'',b'not an image'])
def test_empty_and_invalid(client,content): assert analyze(client,content=content).status_code==422
@pytest.mark.parametrize('color',[0,255])
def test_dark_and_glare(client,color): assert analyze(client,content=sample(color)).status_code==422
def test_resolution_limit(client): assert analyze(client,content=sample(size=(32,32))).status_code==422
def test_file_size_limit(client): assert analyze(client,content=b'x'*(8*1024*1024+1)).status_code==413
def test_no_onion(client): assert analyze(client,demo_scenario='no_onion').status_code==422
def test_uncertain(client):
    r=analyze(client,demo_scenario='uncertain').json();assert r['review_count']==6 and r['grade_a_percentage'] is None
def test_no_scale_no_diameter(client):
    r=analyze(client,demo_scenario='single').json();assert r['detections'][0]['diameter_mm'] is None and r['grade_a_percentage'] is None
def test_batch_details_are_saved_and_reported(client):
    details={'batch_id':'LOT-42','farm':'Nashik Test Farm','operator':'Inspector','origin':'Nashik','expected_kg':120,'notes':'Dry storage'}
    response=analyze(client,batch_details=json.dumps(details));assert response.status_code==200,response.text
    record=response.json();assert record['batch_details']==details
    saved=client.get('/api/inspection/'+record['id'],headers=auth(client)).json();assert saved['batch_details']==details
    headers=auth(client);client.post('/api/report/'+record['id'],headers=headers)
    pdf=client.get('/api/report/'+record['id']+'/pdf',headers=headers)
    text='\n'.join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
    assert 'LOT-42' in text and 'Nashik Test Farm' in text
    assert analyze(client,batch_details=json.dumps({'farm':'x'*121})).status_code==422
def test_bad_calibration(client):
    assert analyze(client,calibration_reference_mm='50').status_code==422
    assert analyze(client,calibration_points='bad-json').status_code==422
    assert analyze(client,calibration_reference_mm='50',calibration_points='{"a":1,"b":2}').status_code==422
def test_auth_and_mime(client):
    assert client.get('/api/inspections').status_code in (401,403)
    r=client.post('/api/analyze',headers=auth(client),files={'image':('x.jpg',sample(),'text/plain')},data={'mode':'demo'});assert r.status_code==422
def test_batch_partial_failure_and_duplicate(client):
    r=client.post('/api/analyze/batch',headers=auth(client),files=[('images',('a.jpg',sample(),'image/jpeg')),('images',('b.jpg',sample(),'image/jpeg')),('images',('c.jpg',b'bad','image/jpeg'))],data={'mode':'demo'})
    assert [x['success'] for x in r.json()['results']]==[True,False,False]
@pytest.mark.parametrize('health_label,confidence,expected_grade',[
    ('HEALTHY_BULB',.98,'A'),('UNHEALTHY_BULB',.98,'Poor'),
    ('LEAF_ONLY',.98,'Review required'),('HEALTHY_BULB',.5,'Review required'),
    ('UNHEALTHY_BULB',.5,'Review required')])
def test_whole_photo_returns_health_result_including_leaf_prediction(client,monkeypatch,health_label,confidence,expected_grade):
    import backend.inference as inference
    probabilities={label: confidence if label==health_label else (1-confidence)/2 for label in ['HEALTHY_BULB','UNHEALTHY_BULB','LEAF_ONLY']}
    monkeypatch.setattr(inference,'health_predict',lambda image:(health_label,confidence,probabilities))
    response=analyze(client,mode='health')
    assert response.status_code==200,response.text
    record=response.json()
    assert record['analysis_scope']=='whole_image'
    assert record['detections'][0]['health_label']==health_label
    assert record['grade_a_percentage'] is None
    assert record['detections'][0]['mask'] is None
    if health_label=='LEAF_ONLY':
        assert record['review_required']
        assert record['detections'][0]['class']=='REVIEW_REQUIRED'
        assert record['detections'][0]['classification_warnings']
    saved=client.get('/api/inspection/'+record['id'],headers=auth(client))
    assert saved.status_code==200
    assert saved.json()['detections'][0]['health_probabilities']==probabilities
    assert saved.json()['visual_grade']['label']==expected_grade
    assert saved.json()['detections'][0]['visual_grade']['label']==expected_grade
    headers=auth(client)
    assert client.post('/api/report/'+record['id'],headers=headers).status_code==200
    pdf=client.get('/api/report/'+record['id']+'/pdf',headers=headers)
    text='\n'.join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
    assert 'AI visual grade: '+expected_grade in text
    assert record['urs_percentage'] is None
    assert record['detections'][0]['grade_a_candidate'] is None
    if record['model_version']=='bulb-health-all-v2':
        assert '16,271 usable images' in text
        assert 'no validated accuracy figure is claimed' in ' '.join(text.split())
        assert 'not official procurement grades' in ' '.join(text.split())
    assert client.get('/api/reports/verify/'+record['report_hash']).json()['valid']
def test_owner_protection(client):
    r=analyze(client).json()
    import backend.main as main
    import jwt
    stranger={'Authorization':'Bearer '+jwt.encode({'sub':'other'},main.SECRET,algorithm='HS256')}
    assert client.get('/api/inspection/'+r['id'],headers=stranger).status_code==401
def test_rate_limit(client,monkeypatch):
    headers=auth(client);monkeypatch.setenv('RATE_LIMIT_PER_MINUTE','1');assert analyze(client,headers).status_code==429

def test_pdf_tamper_is_detected(client):
    headers=auth(client);record=analyze(client,headers).json()
    assert client.post('/api/report/'+record['id'],headers=headers).status_code==200
    import backend.main as main
    (main.DATA/f"{record['id']}-report.pdf").write_bytes(b'modified')
    verified=client.get('/api/reports/verify/'+record['report_hash']).json()
    assert verified['record_valid'] and not verified['pdf_valid'] and not verified['valid']
    assert client.get('/api/report/'+record['id']+'/pdf',headers=headers).status_code==409

def test_demo_sessions_are_isolated_and_expire(client,monkeypatch):
    import jwt
    import backend.main as main
    from datetime import datetime,timedelta,timezone
    monkeypatch.setenv('DEMO_LOGIN_ENABLED','true')
    first=client.post('/api/auth/demo').json()['access_token']
    second=client.post('/api/auth/demo').json()['access_token']
    a={'Authorization':'Bearer '+first};b={'Authorization':'Bearer '+second}
    assert first!=second
    assert client.get('/api/auth/me',headers=a).json()['demo'] is True
    response=analyze(client,a)
    assert response.status_code==200,response.text
    record=response.json();identifier=record['id']
    assert len(client.get('/api/inspections',headers=a).json())==1
    assert client.get('/api/inspections',headers=b).json()==[]
    for headers in (b,auth(client)):
        assert client.get('/api/inspection/'+identifier,headers=headers).status_code==404
        assert client.get(record['image_url'],headers=headers).status_code==404
        assert client.post('/api/report/'+identifier,headers=headers).status_code==404
    assert client.post('/api/report/'+identifier,headers=a).status_code==200
    assert client.get('/api/report/'+identifier+'/pdf',headers=a).status_code==200
    assert client.get('/api/report/'+identifier+'/pdf',headers=b).status_code==404
    claims=jwt.decode(first,main.SECRET,algorithms=['HS256'])
    claims['exp']=datetime.now(timezone.utc)-timedelta(seconds=1)
    expired=jwt.encode(claims,main.SECRET,algorithm='HS256')
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+expired}).status_code==401
    claims['exp']=datetime.now(timezone.utc)+timedelta(hours=1);claims.pop('demo')
    invalid=jwt.encode(claims,main.SECRET,algorithm='HS256')
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+invalid}).status_code==401
    monkeypatch.setenv('DEMO_LOGIN_ENABLED','false')
    assert client.post('/api/auth/demo').status_code==403
    assert client.get('/api/auth/me',headers=a).status_code==401
