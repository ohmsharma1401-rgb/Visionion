import importlib
import hashlib
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
def test_health_requires_confirmation(client): assert analyze(client,mode='health').status_code==422
def test_owner_protection(client):
    r=analyze(client).json()
    import backend.main as main
    import jwt
    stranger={'Authorization':'Bearer '+jwt.encode({'sub':'other'},main.SECRET,algorithm='HS256')}
    assert client.get('/api/inspection/'+r['id'],headers=stranger).status_code==404
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
