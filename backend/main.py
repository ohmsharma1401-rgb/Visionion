from collections import defaultdict,deque
from datetime import datetime,timedelta,timezone
from io import BytesIO
from pathlib import Path
import hashlib
import json
import os
import secrets
import threading
import time
import uuid
import jwt
from fastapi import FastAPI,Depends,HTTPException,UploadFile,File,Form,Request
from fastapi.responses import Response,JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from pydantic import BaseModel,Field
from sqlalchemy import select
from backend.database import initialize,Inspection,Audit,ReportArtifact,User
from backend import auth as accounts
from backend.grading import analyze_onions,load_spec,load_urs
from backend.grading.validators import calibration_scale,diameter_from_polygon
from backend.calibration import detect_reference,marker_pdf,size_category,size_config
from backend.inference import infer,model_info,LIMITATIONS
from backend.vision import validate_image,check_visibility,annotated_image
from backend.schemas import AnalysisResponse
from backend.reports import render_pdf

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.getenv('DATA_DIR',str(ROOT/'data')));DATA.mkdir(parents=True,exist_ok=True)
Session=initialize();SPEC=load_spec();URS=load_urs()
SECRET=os.getenv('JWT_SECRET') or secrets.token_hex(32);PASSWORD=os.getenv('DEMO_PASSWORD')
security=HTTPBearer();write_lock=threading.RLock();inference_lock=threading.Lock()
app=FastAPI(title='OnionGrade AI',version='0.2.0',description='Per-onion visual analysis with explicit model capabilities and unresolved grading.')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
requests_by_ip=defaultdict(deque)

@app.middleware('http')
async def limits(request:Request,call_next):
    if request.method=='POST':
        size=request.headers.get('content-length')
        if size and (not size.isdigit() or int(size)>85*1024*1024): return JSONResponse({'detail':'Request too large.'},status_code=413)
        now=time.monotonic();ip=request.client.host if request.client else 'unknown';queue=requests_by_ip[ip]
        while queue and now-queue[0]>60: queue.popleft()
        if len(queue)>=int(os.getenv('RATE_LIMIT_PER_MINUTE','30')): return JSONResponse({'detail':'Too many requests. Retry in one minute.'},status_code=429,headers={'Retry-After':'60'})
        queue.append(now)
        if len(requests_by_ip)>10000:
            for key in list(requests_by_ip):
                if not requests_by_ip[key] or now-requests_by_ip[key][-1]>60: del requests_by_ip[key]
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Cache-Control']='no-store'
    return response

def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()
def actor(credentials:HTTPAuthorizationCredentials=Depends(security)):
    try: subject=jwt.decode(credentials.credentials,SECRET,algorithms=['HS256'])['sub']
    except (jwt.PyJWTError,KeyError): raise HTTPException(401,'Session expired or invalid.')
    if subject=='inspector' and os.getenv('ALLOW_SQLITE_FOR_TESTS')=='1': return subject
    with Session() as db:
        user=db.get(User,subject)
        if not user or not user.verified_at: raise HTTPException(401,'Session expired or invalid.')
    return subject

class BatchDetails(BaseModel):
    batch_id:str=Field(default='',max_length=80)
    farm:str=Field(default='',max_length=120)
    operator:str=Field(default='',max_length=120)
    origin:str=Field(default='',max_length=120)
    expected_kg:float|None=Field(default=None,ge=0,le=10000000)
    notes:str=Field(default='',max_length=1000)

@app.post('/api/auth/login')
def login(body:accounts.Login):
    if body.username=='inspector' and not body.email and os.getenv('ALLOW_SQLITE_FOR_TESTS')=='1' and PASSWORD and secrets.compare_digest(body.password,PASSWORD):
        subject='inspector'
    else:
        if not body.email: raise HTTPException(401,'Invalid email or password.')
        email=accounts.normalized_email(body.email)
        with Session() as db:
            user=db.scalar(select(User).where(User.email==email))
            if not user or not accounts.valid_password(body.password,user.password_hash): raise HTTPException(401,'Invalid email or password.')
            if not user.verified_at: raise HTTPException(403,'Verify your email before signing in.')
            subject=user.id
    return {'access_token':jwt.encode({'sub':subject,'exp':datetime.now(timezone.utc)+timedelta(hours=8)},SECRET,algorithm='HS256'),'token_type':'bearer'}

@app.post('/api/auth/register')
def register(body:accounts.Register): return accounts.register(Session,body,SECRET)

@app.post('/api/auth/verify-otp')
def verify_otp(body:accounts.Verify): return accounts.verify(Session,body,SECRET)

@app.post('/api/auth/resend-otp')
def resend_otp(body:accounts.Resend): return accounts.resend(Session,body,SECRET)

@app.get('/api/auth/me')
def me(owner:str=Depends(actor)):
    with Session() as db:
        user=db.get(User,owner)
        if not user or not user.verified_at: raise HTTPException(401,'Account unavailable.')
        return {'id':user.id,'email':user.email,'name':user.name}

@app.get('/api/health')
def health(): return {'status':'ok','version':'0.2.0','trained_health_model':model_info()['health_model_available']}
@app.get('/api/model/info')
def info(): return model_info()
@app.get('/api/grading-spec')
def spec(): return {'grading':SPEC.model_dump(),'urs':URS.model_dump()}

@app.get('/api/calibration/config')
def calibration_config(): return size_config()

@app.get('/api/calibration/marker.pdf')
def calibration_marker():
    try: payload=marker_pdf()
    except (RuntimeError,ImportError) as exc: raise HTTPException(503,str(exc)) from exc
    return Response(payload,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="oniongrade-50mm-marker.pdf"'})

def read_record(identifier,owner):
    with Session() as db:
        item=db.get(Inspection,identifier)
        if not item or item.owner!=owner: raise HTTPException(404,'Inspection not found.')
        return json.loads(item.payload)

def save_record(record,owner):
    record=dict(record);record['report_hash']=digest(record)
    with write_lock,Session.begin() as db:
        if db.get(Inspection,record['id']): raise HTTPException(409,'Inspection ID already exists; analysis records are immutable.')
        db.add(Inspection(id=record['id'],owner=owner,payload=canonical(record),report_hash=record['report_hash']))
        previous=db.scalar(select(Audit).order_by(Audit.id.desc()).limit(1));prev=previous.hash if previous else '0'*64
        payload=canonical({'actor':owner,'action':'image.analyzed','entity':record['id'],'report_hash':record['report_hash'],'model':record['model_version'],'spec':record['grading_spec'],'at':record['created_at']})
        db.add(Audit(payload=payload,prev_hash=prev,hash=hashlib.sha256((prev+payload).encode()).hexdigest()))
    return record

def process(content,mime,owner,mode,scenario,variety,reference_mm,points,regions,identifier=None,require_reference=False,batch_details=None):
    try:
        image,quality=validate_image(content,mime,SPEC.quality)
        if points is not None or reference_mm is not None:
            calibration=calibration_scale(reference_mm,points,image.width,image.height)
        else:
            try: calibration=detect_reference(image)
            except (RuntimeError,ImportError) as exc:
                if require_reference: raise HTTPException(503,'Reference detection is unavailable on this server.') from exc
                calibration=None
            if calibration is None:
                if require_reference: raise ValueError('Reference marker not detected. Put the printed marker beside the onion, or upload an image and mark a known reference manually.')
                calibration=calibration_scale(None,None,image.width,image.height)
    except ValueError as exc: raise HTTPException(422,{'message':'Image quality is insufficient for reliable analysis.','reasons':[str(exc)]})
    if not quality['usable']: raise HTTPException(422,{'message':'Image quality is insufficient for reliable analysis.','reasons':quality['reasons'],'image_quality':quality})
    try:
        with inference_lock: detections,model_version=infer(image,mode,scenario,regions)
    except ValueError as exc: raise HTTPException(422,str(exc))
    except (RuntimeError,ImportError) as exc: raise HTTPException(503,str(exc))
    if not detections: raise HTTPException(422,{'message':'Image quality is insufficient for reliable analysis.','reasons':['No onion detected, or the health model identified a leaf-only image.'],'demo':mode=='demo'})
    crowded=check_visibility(detections,image.width,image.height,SPEC.quality)
    if crowded: raise HTTPException(422,{'message':'Image quality is insufficient for reliable analysis.','reasons':['Too many overlapping onions or regions. Separate the bulbs and retake.']})
    for d in detections:
        mask=d['mask'] if not d['visibility_issues'] else None
        scale=calibration['mm_per_pixel'] if mask else None
        d['diameter_mm']=diameter_from_polygon(mask,scale) if mask else None
        if mask:
            xs=[p[0] for p in mask];ys=[p[1] for p in mask]
            width_px=max(xs)-min(xs);height_px=max(ys)-min(ys)
            diameter_px=d['diameter_mm']/scale if scale and d['diameter_mm'] is not None else None
            d['measurement']={'width_px':round(width_px,2),'height_px':round(height_px,2),'diameter_px':round(diameter_px,2) if diameter_px else None,
                              'width_mm':round(width_px*scale,2) if scale else None,'height_mm':round(height_px*scale,2) if scale else None,
                              'diameter_mm':d['diameter_mm'],'calibration_source':calibration['method'] if scale else None,
                              'reference_width_mm':calibration.get('reference_width_mm',calibration.get('reference_mm')) if scale else None,
                              'confidence':d['confidence'] if d['region_source']=='model_segmentation' else None}
        else:
            d['measurement']=None
        d['size_category']=size_category(d['diameter_mm'])
    result=analyze_onions(detections,SPEC,URS)
    identifier=identifier or str(uuid.uuid4())
    record={'id':identifier,'schema_version':2,'success':True,'created_at':datetime.now(timezone.utc).isoformat(),'inspector':owner,'variety':variety,'batch_details':batch_details or {},'mode':mode,'demo':mode=='demo','model_version':model_version,'grading_spec':SPEC.spec_version,'spec_snapshot':SPEC.model_dump(),'urs_snapshot':URS.model_dump(),'size_config_snapshot':size_config(),'image_quality':quality,'calibration':calibration,'width':image.width,'height':image.height,
            'image_url':f'/api/inspection/{identifier}/image','annotated_url':f'/api/inspection/{identifier}/annotated','summary':{k:v for k,v in result.items() if k!='detections'},**result,
            'limitations':LIMITATIONS+(['DEMO ANALYSIS: boundaries, classes and confidence are fixed mock predictions unrelated to uploaded image contents. Calibrated mock geometry is still not a real measurement.'] if mode=='demo' else ['The health model was trained on broad image-level labels. It cannot identify rot/damage/sprouting subtypes or certify Grade A. User outlines are not learned segmentation.'] if mode=='health' else [])}
    # Persist only re-encoded JPEGs; ignore uploaded filenames and strip EXIF metadata.
    record['model_sha256']=model_info()['health_model']['sha256'] if mode=='health' else None
    with write_lock:
        with Session() as db:
            if db.get(Inspection,identifier): raise HTTPException(409,'Inspection ID already exists; original evidence cannot be overwritten.')
        image.save(DATA/f'{identifier}-original.jpg',quality=92)
        annotated_image(image,result['detections'],calibration,mode=='demo').save(DATA/f'{identifier}-annotated.jpg',quality=92)
        return save_record(record,owner)

def parse_json(value,name):
    if not value: return None
    try: return json.loads(value)
    except (ValueError,TypeError): raise HTTPException(422,f'{name} must be valid JSON.')

@app.post('/api/analyze',response_model=AnalysisResponse)
def analyze(image:UploadFile=File(...),mode:str=Form('health',pattern='^(health|demo|segmentation)$'),demo_scenario:str=Form('multiple',pattern='^(single|multiple|uncertain|no_onion|calibrated_sample)$'),calibration_reference_mm:float|None=Form(None,gt=0,le=1000),calibration_points:str|None=Form(None),regions:str|None=Form(None),variety:str=Form('Unspecified',max_length=100),batch_details:str|None=Form(None),inspection_id:uuid.UUID|None=Form(None),single_onion_confirmed:bool=Form(False),require_reference:bool=Form(False),owner=Depends(actor)):
    if mode=='health' and not regions and not single_onion_confirmed: raise HTTPException(422,'Confirm this is a single bulb or provide an outline for each onion.')
    if inspection_id:
        with Session() as db:
            if db.get(Inspection,str(inspection_id)): raise HTTPException(409,'Inspection ID already exists; original evidence cannot be overwritten.')
    content=image.file.read(8*1024*1024+1)
    if len(content)>8*1024*1024: raise HTTPException(413,'Maximum image size is 8 MB.')
    raw_batch=parse_json(batch_details,'batch_details')
    try: validated_batch=BatchDetails.model_validate(raw_batch).model_dump() if raw_batch is not None else None
    except ValueError as exc: raise HTTPException(422,'Invalid batch details.') from exc
    return process(content,image.content_type,owner,mode,demo_scenario,variety,calibration_reference_mm,parse_json(calibration_points,'calibration_points'),parse_json(regions,'regions'),str(inspection_id) if inspection_id else None,require_reference,validated_batch)

@app.post('/api/analyze/batch')
def batch(images:list[UploadFile]=File(...),mode:str=Form('health',pattern='^(health|demo|segmentation)$'),single_onion_confirmed:bool=Form(False),owner=Depends(actor)):
    if not 1<=len(images)<=10: raise HTTPException(422,'Batch size must be 1–10 images.')
    if mode=='health' and not single_onion_confirmed: raise HTTPException(422,'Confirm every batch image contains a single bulb.')
    results=[];hashes=set()
    for index,image in enumerate(images):
        content=image.file.read(8*1024*1024+1);sha=hashlib.sha256(content).hexdigest()
        if sha in hashes: results.append({'index':index,'success':False,'error':'Duplicate image in batch.'});continue
        hashes.add(sha)
        try:
            if len(content)>8*1024*1024: raise HTTPException(413,'Maximum image size is 8 MB.')
            results.append({'index':index,'success':True,'inspection':process(content,image.content_type,owner,mode,'multiple','Unspecified',None,None,None)})
        except HTTPException as exc: results.append({'index':index,'success':False,'error':exc.detail})
    return {'results':results,'policy':'Independent images. No cross-image counting or de-duplication of the same onion in different views.'}

@app.get('/api/inspections')
def history(owner=Depends(actor)):
    with Session() as db:
        records=[json.loads(x.payload) for x in db.scalars(select(Inspection).where(Inspection.owner==owner).order_by(Inspection.created_at.desc()))]
    return [r for r in records if r.get('schema_version')==2]

@app.get('/api/inspection/{identifier}',response_model=AnalysisResponse)
def inspection(identifier:uuid.UUID,owner=Depends(actor)): return read_record(str(identifier),owner)

@app.get('/api/inspection/{identifier}/{asset}')
def asset(identifier:uuid.UUID,asset:str,owner=Depends(actor)):
    read_record(str(identifier),owner)
    if asset not in ('image','annotated'): raise HTTPException(404,'Asset not found.')
    path=DATA/f'{identifier}-{"original" if asset=="image" else "annotated"}.jpg'
    if not path.exists(): raise HTTPException(404,'Image is missing.')
    return Response(path.read_bytes(),media_type='image/jpeg')

def report_artifact(identifier,owner):
    record=read_record(identifier,owner);path=DATA/f'{identifier}-report.pdf'
    with write_lock:
        with Session() as db:
            artifact=db.get(ReportArtifact,identifier)
            expected=artifact.pdf_sha256 if artifact else None
        if expected and path.exists():
            if not secrets.compare_digest(expected,hashlib.sha256(path.read_bytes()).hexdigest()): raise HTTPException(409,'PDF integrity check failed. Stored artifact has changed.')
        elif expected:
            raise HTTPException(409,'Stored report artifact is missing.')
        else:
            url=os.getenv('PUBLIC_BASE_URL','http://127.0.0.1:8000').rstrip('/')+'/api/reports/verify/'+record['report_hash']
            payload=render_pdf(record,url,DATA)
            temporary=DATA/f'{identifier}-report.tmp';temporary.write_bytes(payload);temporary.replace(path)
            with Session.begin() as db:
                db.add(ReportArtifact(inspection_id=identifier,pdf_sha256=hashlib.sha256(payload).hexdigest()))
    return path,hashlib.sha256(path.read_bytes()).hexdigest(),record

@app.post('/api/report/{identifier}')
def create_report(identifier:uuid.UUID,owner=Depends(actor)):
    path,sha,record=report_artifact(str(identifier),owner)
    return {'report_id':str(identifier),'pdf_url':f'/api/report/{identifier}/pdf','pdf_sha256':sha,'record_sha256':record['report_hash'],'hash_policy':'Embedded hash covers canonical analysis JSON. PDF byte hash is returned separately to avoid a self-referential hash.'}

@app.get('/api/report/{identifier}/pdf')
def download_report(identifier:uuid.UUID,owner=Depends(actor)):
    path,sha,_=report_artifact(str(identifier),owner)
    return Response(path.read_bytes(),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="oniongrade-{identifier}.pdf"','X-PDF-SHA256':sha})

@app.get('/api/reports/verify/{token}')
def verify(token:str):
    with Session() as db:
        item=db.scalar(select(Inspection).where(Inspection.report_hash==token))
        if not item: raise HTTPException(404,'Report not found.')
        record=json.loads(item.payload);stored=record.pop('report_hash');path=DATA/f'{item.id}-report.pdf'
        artifact=db.get(ReportArtifact,item.id)
        actual=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        pdf_valid=bool(actual and secrets.compare_digest(actual,artifact.pdf_sha256)) if artifact else None
        return {'valid':secrets.compare_digest(stored,digest(record)) and pdf_valid is not False,'record_valid':secrets.compare_digest(stored,digest(record)),'pdf_valid':pdf_valid,'report_id':item.id,'mode':record['mode'],'grading_spec':record.get('grading_spec',record.get('spec_version')),'pdf_sha256':artifact.pdf_sha256 if artifact else None}

@app.get('/api/audit/verify')
def audit(owner=Depends(actor)):
    previous='0'*64
    with Session() as db:
        rows=list(db.scalars(select(Audit).order_by(Audit.id)))
        for row in rows:
            if row.prev_hash!=previous or row.hash!=hashlib.sha256((previous+row.payload).encode()).hexdigest(): return {'valid':False}
            previous=row.hash
    return {'valid':True,'entries':len(rows)}

from fastapi.staticfiles import StaticFiles
DIST_DIR = ROOT / 'web' / 'dist'
if DIST_DIR.exists():
    app.mount('/', StaticFiles(directory=str(DIST_DIR), html=True), name='web')
