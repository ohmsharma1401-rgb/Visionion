"""Fine-tune the evaluated health classifier on every usable ZIP image.

This produces a deployment checkpoint, not a new held-out evaluation. All
manifest splits, including multi-bulb image-level labels, become training data.
"""
import argparse
import hashlib
import json
import random
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import models

from train_health import LABELS, OnionImages

ROOT=Path(__file__).resolve().parents[2]
PREVIOUS=ROOT/'ml/models/bulb-health-v1.pt'
PREVIOUS_META=ROOT/'ml/models/bulb-health-v1.json'
DESTINATION=ROOT/'ml/models/bulb-health-all-v2.pt'
METADATA=ROOT/'ml/models/bulb-health-all-v2.json'
HISTORY=ROOT/'ml/models/all-images-training-history.json'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--epochs',type=int,default=6)
    parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args()
    if not 1<=args.epochs<=50: raise ValueError('epochs must be between 1 and 50')
    random.seed(43);np.random.seed(43);torch.manual_seed(43);torch.set_num_threads(4)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    if device=='cuda':torch.cuda.manual_seed_all(43)
    if not PREVIOUS.is_file() or not PREVIOUS_META.is_file():
        raise RuntimeError('The evaluated v1 checkpoint is required before all-image fine-tuning.')
    parent=json.loads(PREVIOUS_META.read_text())
    if hashlib.sha256(PREVIOUS.read_bytes()).hexdigest()!=parent['sha256']:
        raise RuntimeError('Evaluated parent checkpoint hash does not match metadata.')
    rows=json.loads((ROOT/'ml/datasets/prepared/manifest.json').read_text())
    if len(rows)!=16271 or len({r['sha256'] for r in rows})!=len(rows):
        raise RuntimeError('Prepared manifest does not match the inspected 16,271 unique usable images.')
    for row in rows:
        if not (ROOT/'ml/datasets/prepared'/row['path']).is_file():
            raise RuntimeError(f"Prepared image missing: {row['path']}")
    counts=Counter(r['label'] for r in rows)
    splits=Counter(r['split'] for r in rows)
    loader=DataLoader(OnionImages(rows,training=True),batch_size=64,shuffle=True,
                      num_workers=args.workers,pin_memory=device=='cuda')
    checkpoint=torch.load(PREVIOUS,map_location='cpu',weights_only=True)
    model=models.mobilenet_v3_small(weights=None)
    model.classifier[3]=nn.Linear(model.classifier[3].in_features,len(LABELS))
    model.load_state_dict(checkpoint['state_dict']);model.to(device)
    weights=torch.tensor([len(rows)/(len(LABELS)*counts[label]) for label in LABELS],
                         dtype=torch.float32,device=device)
    loss_fn=nn.CrossEntropyLoss(weight=weights)
    optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,weight_decay=1e-4)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=args.epochs)
    history=[];started=time.time()
    print(json.dumps({'device':device,'images':len(rows),'classes':counts,'source_splits':splits,
                      'epochs':args.epochs,'independent_holdout':False}),flush=True)
    for epoch in range(1,args.epochs+1):
        model.train();total=0;seen=0
        for images,labels in loader:
            images,labels=images.to(device),labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss=loss_fn(model(images),labels)
            loss.backward();optimizer.step()
            total+=float(loss.item())*len(labels);seen+=len(labels)
        scheduler.step()
        item={'epoch':epoch,'train_loss':round(total/seen,6),
              'elapsed_seconds':round(time.time()-started,1)}
        history.append(item);HISTORY.write_text(json.dumps(history,indent=2))
        print(json.dumps(item),flush=True)
        torch.save({'state_dict':{k:v.detach().cpu() for k,v in model.state_dict().items()},
                    'labels':LABELS,'architecture':'mobilenet_v3_small',
                    'input_size':160,'epoch':epoch,'training_images':len(rows)},
                   DESTINATION.with_suffix('.partial.pt'))
    DESTINATION.with_suffix('.partial.pt').replace(DESTINATION)
    metadata={
        'model_version':'bulb-health-all-v2',
        'architecture':'mobilenet_v3_small',
        'parent_model_version':parent['model_version'],
        'parent_sha256':parent['sha256'],
        'training_images':len(rows),
        'class_counts':dict(counts),
        'source_splits_used':dict(splits),
        'epochs':args.epochs,
        'device':device,
        'elapsed_seconds':round(time.time()-started,1),
        'confidence_threshold':parent['confidence_threshold'],
        'threshold_provenance':'Inherited from v1 validation; not recalibrated after all-image training.',
        'evaluation_status':'No independent holdout remains for this all-image checkpoint. The v1 held-out metrics do not measure v2 performance.',
        'limitations':parent['limitations']+[
            'Multi-bulb images were used with image-level health labels; this does not train per-onion detection or segmentation.',
            'A new independent lot-level test is required to estimate deployment accuracy.'
        ],
        'sha256':hashlib.sha256(DESTINATION.read_bytes()).hexdigest(),
    }
    METADATA.write_text(json.dumps(metadata,indent=2))
    print('FINAL '+json.dumps(metadata),flush=True)


if __name__=='__main__':main()
