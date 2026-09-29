"""Ingest the supplied archive without trusting archive paths or inventing defect labels."""
from pathlib import Path
from io import BytesIO
from collections import Counter, defaultdict
import hashlib
import json
import random
import re
import zipfile
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'ml/datasets/prepared'

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    images=OUT/'images';images.mkdir(exist_ok=True)
    rows=[];seen={};duplicates=0;conflicts=[];bad=[]
    with zipfile.ZipFile(ROOT/'ml/datasets/raw/onion-source.zip') as archive:
        for index,name in enumerate(archive.namelist()):
            if not name.lower().endswith('.jpg'): continue
            content=archive.read(name)
            label='LEAF_ONLY' if '/1. Leaves/' in name else 'UNHEALTHY_BULB' if '/2. Unhealthy/' in name else 'HEALTHY_BULB'
            sha=hashlib.sha256(content).hexdigest()
            if sha in seen:
                duplicates+=1
                if seen[sha]!=label: conflicts.append(sha)
                continue
            seen[sha]=label
            try:
                with Image.open(BytesIO(content)) as raw:
                    image=ImageOps.exif_transpose(raw).convert('RGB')
                    image=ImageOps.pad(image,(256,256),color=(127,127,127))
                    image.save(images/f'{sha}.jpg',quality=92)
            except Exception as exc:
                bad.append({'source':name,'error':str(exc)});continue
            serial=int(re.search(r'(\d+)\.jpg$',name,re.I).group(1))
            folder=name.rsplit('/',1)[0]
            # There are no lot/session IDs. Keep 100 consecutive filenames together.
            # This reduces nearby-frame leakage but does NOT prove lot independence.
            group=f'{folder}/sequence-{(serial-1)//100:04d}'
            multi='/2. Bulb/' in name and '/2. Multiple/' in name
            rows.append({'path':f'images/{sha}.jpg','source':name,'sha256':sha,'label':label,'group':group,'multiple_bulbs':multi})
            if index%1000==0: print(f'Prepared {len(rows)} images',flush=True)
    conflicting=set(conflicts)
    rows=[r for r in rows if r['sha256'] not in conflicting]
    by_class=defaultdict(set)
    for r in rows:
        if not r['multiple_bulbs']: by_class[r['label']].add(r['group'])
    mapping={}
    for label,groups in sorted(by_class.items()):
        groups=sorted(groups);random.Random(42).shuffle(groups)
        train=int(len(groups)*.70);val=int(len(groups)*.15)
        for i,group in enumerate(groups): mapping[group]='train' if i<train else 'val' if i<train+val else 'test'
    for r in rows: r['split']='multiple_stress' if r['multiple_bulbs'] else mapping[r['group']]
    (OUT/'manifest.json').write_text(json.dumps(rows,indent=2))
    summary={'archive_images':len(seen)+duplicates,'retained':len(rows),'duplicates_removed':duplicates,'conflicting_hashes_removed':len(conflicting),'corrupt':bad,'counts':dict(Counter(f"{r['split']}/{r['label']}" for r in rows)),
             'split_policy':'70/15/15 by folder + consecutive 100-file proxy group; seed 42. Exact SHA-256 duplicates removed. Lot/session identifiers unavailable, so cross-lot generalization is NOT established. Multiple-bulb images are stress-test only, never instance labels.',
             'supported_labels':['HEALTHY_BULB','UNHEALTHY_BULB','LEAF_ONLY'],'unsupported':['damage subtype','rot subtype','sprouting subtype','instance masks','bounding boxes','physical size']}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__': prepare()
