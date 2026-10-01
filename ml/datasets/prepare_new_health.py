"""Prepare the new image-level archive with explicit labels and group splits."""
from collections import Counter, defaultdict
from io import BytesIO
import hashlib
import json
from pathlib import Path
import random
import re
import zipfile
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'ml/datasets/prepared-v3'

def main():
    (OUT/'images').mkdir(parents=True,exist_ok=True)
    rows=[];seen={};conflicts=set();bad=[];duplicates=0
    with zipfile.ZipFile(ROOT/'ml/datasets/raw/new-onion-source.zip') as archive:
        for name in archive.namelist():
            if Path(name).suffix.lower() not in ('.jpg','.jpeg','.png','.webp'): continue
            label='LEAF_ONLY' if '/Leaves/' in name else 'UNHEALTHY_BULB' if '/Bulb/Unhealthy/' in name else 'HEALTHY_BULB' if '/Bulb/Healthy/' in name else None
            if label is None: raise ValueError('Unknown label: '+name)
            content=archive.read(name);sha=hashlib.sha256(content).hexdigest()
            if sha in seen:
                duplicates+=1
                if seen[sha]!=label: conflicts.add(sha)
                continue
            seen[sha]=label
            try:
                target=OUT/'images'/f'{sha}.jpg'
                if not target.exists():
                    with Image.open(BytesIO(content)) as raw:
                        raw.load();image=ImageOps.pad(ImageOps.exif_transpose(raw).convert('RGB'),(256,256),color=(127,127,127))
                        image.save(target,quality=92)
            except Exception as exc:
                bad.append({'source':name,'error':str(exc)});continue
            folder=name.rsplit('/',1)[0];numbers=re.findall(r'\d+',Path(name).stem)
            serial=int(numbers[-1]) if numbers else 0
            group=folder+'/sequence-'+str(serial//100)
            rows.append({'path':f'images/{sha}.jpg','source':name,'sha256':sha,'label':label,'group':group,'multiple_bulbs':'/Bulb/' in name and ('/Multiple/' in name or '/Mixed/' in name)})
            if len(rows)%1000==0: print('Prepared '+str(len(rows)),flush=True)
    rows=[r for r in rows if r['sha256'] not in conflicts]
    strata=defaultdict(set)
    for r in rows:
        folder=r['source'].rsplit('/',1)[0]
        # Mixed-ratio folders can contain only two proxy groups. Stratify all
        # healthy mixed photos together while keeping each group intact.
        stratum=folder.split('/Mixed/')[0]+'/Mixed' if '/Mixed/' in folder else folder
        strata[stratum].add(r['group'])
    mapping={}
    for folder,groups in sorted(strata.items()):
        groups=sorted(groups);random.Random(42).shuffle(groups)
        if len(groups)<3: raise ValueError('Insufficient independent proxy groups: '+folder)
        ntest=max(1,round(len(groups)*.15));nval=max(1,round(len(groups)*.15))
        for i,g in enumerate(groups): mapping[g]='test' if i<ntest else 'val' if i<ntest+nval else 'train'
    for r in rows: r['split']=mapping[r['group']]
    summary={'retained':len(rows),'duplicates_removed':duplicates,'conflicts_removed':len(conflicts),'corrupt':bad,'counts':dict(Counter(r['split']+'/'+r['label'] for r in rows)),
             'group_counts':dict(Counter(r['split'] for r in rows if r['multiple_bulbs'])),'split_policy':'Seed 42; 70/15/15 approximate folder-stratified consecutive-100 filename proxy groups. Exact source duplicates removed. No real lot IDs; lot independence and near-duplicate independence unproven. Fresh ImageNet initialization required; do not warm-start v2.'}
    (OUT/'manifest.json').write_text(json.dumps(rows,indent=2));(OUT/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)

if __name__=='__main__': main()
