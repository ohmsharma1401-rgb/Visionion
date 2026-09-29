"""Train actual source-supported bulb health labels; never labels generic illness as rot."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import time
import numpy as np
from PIL import Image
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms

ROOT=Path(__file__).resolve().parents[2]
LABELS=['HEALTHY_BULB','UNHEALTHY_BULB','LEAF_ONLY']

class OnionImages(Dataset):
    def __init__(self,rows,training=False):
        self.rows=rows
        self.transform=transforms.Compose(([transforms.RandomResizedCrop(160,scale=(.7,1.0)),transforms.RandomHorizontalFlip(),transforms.RandomRotation(12),transforms.ColorJitter(.12,.12,.08,.02)] if training else [transforms.Resize((160,160))])+[transforms.ToTensor(),transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
    def __len__(self): return len(self.rows)
    def __getitem__(self,i):
        r=self.rows[i]
        with Image.open(ROOT/'ml/datasets/prepared'/r['path']) as im: image=self.transform(im.convert('RGB'))
        return image,LABELS.index(r['label'])

def metrics(matrix):
    matrix=np.asarray(matrix,dtype=float);per={}
    for i,label in enumerate(LABELS):
        tp=matrix[i,i];precision=tp/max(matrix[:,i].sum(),1);recall=tp/max(matrix[i,:].sum(),1)
        per[label]={'precision':round(float(precision),4),'recall':round(float(recall),4),'f1':round(float(2*precision*recall/max(precision+recall,1e-12)),4),'support':int(matrix[i,:].sum())}
    return {'accuracy':round(float(np.trace(matrix)/max(matrix.sum(),1)),4),'macro_f1':round(float(np.mean([v['f1'] for v in per.values()])),4),'per_class':per,'confusion_matrix':matrix.astype(int).tolist(),'labels':LABELS}

def evaluate(model,loader,device):
    model.eval();matrix=np.zeros((3,3),dtype=np.int64);probs=[];truth=[]
    with torch.inference_mode():
        for x,y in loader:
            output=model(x.to(device)).softmax(1).cpu()
            for t,p in zip(y.tolist(),output.argmax(1).tolist()): matrix[t,p]+=1
            probs.extend(output.tolist());truth.extend(y.tolist())
    return metrics(matrix),probs,truth

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--epochs',type=int,default=12);parser.add_argument('--workers',type=int,default=2);args=parser.parse_args()
    random.seed(42);np.random.seed(42);torch.manual_seed(42);torch.set_num_threads(4)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    if device=='cuda': torch.cuda.manual_seed_all(42)
    out=ROOT/'ml/models';out.mkdir(exist_ok=True)
    torch.hub.set_dir(str(ROOT/'ml/cache'))
    rows=json.loads((ROOT/'ml/datasets/prepared/manifest.json').read_text())
    loaders={s:DataLoader(OnionImages([r for r in rows if r['split']==s],s=='train'),batch_size=64,shuffle=s=='train',num_workers=args.workers,pin_memory=device=='cuda') for s in ('train','val','test','multiple_stress')}
    model=models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)
    model.classifier[3]=nn.Linear(model.classifier[3].in_features,len(LABELS));model.to(device)
    counts=np.bincount([LABELS.index(r['label']) for r in rows if r['split']=='train'],minlength=3)
    criterion=nn.CrossEntropyLoss(weight=torch.tensor(counts.sum()/(3*counts),dtype=torch.float32,device=device))
    optimizer=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=1e-4)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=args.epochs)
    best=-1;stale=0;history=[];started=time.time()
    print(json.dumps({'device':device,'gpu':torch.cuda.get_device_name() if device=='cuda' else None,'counts':counts.tolist(),'epochs':args.epochs}),flush=True)
    for epoch in range(args.epochs):
        model.train();loss_sum=0;n=0
        for x,y in loaders['train']:
            x,y=x.to(device),y.to(device);optimizer.zero_grad(set_to_none=True);loss=criterion(model(x),y);loss.backward();optimizer.step();loss_sum+=loss.item()*len(y);n+=len(y)
        scheduler.step();val,_,_=evaluate(model,loaders['val'],device)
        entry={'epoch':epoch+1,'train_loss':round(loss_sum/n,5),'validation':val,'elapsed_seconds':round(time.time()-started,1)};history.append(entry)
        (out/'training-history.json').write_text(json.dumps(history,indent=2));print(json.dumps(entry),flush=True)
        if val['macro_f1']>best:
            best=val['macro_f1'];stale=0
            torch.save({'state_dict':{k:v.cpu() for k,v in model.state_dict().items()},'labels':LABELS,'architecture':'mobilenet_v3_small','input_size':160,'epoch':epoch+1},out/'bulb-health-v1.pt')
        else: stale+=1
        if stale>=4: break
    checkpoint=torch.load(out/'bulb-health-v1.pt',map_location=device,weights_only=True);model.load_state_dict(checkpoint['state_dict'])
    val,val_probs,val_truth=evaluate(model,loaders['val'],device)
    # Select abstention threshold using validation only; preserve test independence.
    chosen=.80
    for threshold in (.65,.70,.75,.80,.85,.90,.95):
        chosen_rows=[(p,t) for p,t in zip(val_probs,val_truth) if max(p)>=threshold]
        if chosen_rows and sum(int(np.argmax(p))==t for p,t in chosen_rows)/len(chosen_rows)>=.95:
            chosen=threshold;break
    report={'model_version':'bulb-health-v1','architecture':'mobilenet_v3_small','pretrained_backbone':'ImageNet1K','best_epoch':checkpoint['epoch'],'device':device,'elapsed_seconds':round(time.time()-started,1),'confidence_threshold':chosen,'validation':val}
    for split in ('test','multiple_stress'):
        result,probabilities,truth=evaluate(model,loaders[split],device)
        accepted=[(p,t) for p,t in zip(probabilities,truth) if max(p)>=chosen]
        result['threshold_coverage']=round(len(accepted)/max(len(truth),1),4)
        result['accepted_accuracy']=round(sum(int(np.argmax(p))==t for p,t in accepted)/len(accepted),4) if accepted else None
        report[split]=result
    report['limitations']=['No true lot/session identifiers; consecutive filename proxy groups do not establish lot independence.','Single-bulb labels support broad health only, not defect subtypes or Grade A.','No bounding boxes or masks in supplied dataset. Multiple stress results are image-level only.','Leaf class is not a general non-onion detector. Unseen objects can be misclassified.','Softmax confidence is not a calibrated probability of correctness.']
    report['sha256']=hashlib.sha256((out/'bulb-health-v1.pt').read_bytes()).hexdigest()
    (out/'bulb-health-v1.json').write_text(json.dumps(report,indent=2));print('FINAL '+json.dumps(report),flush=True)

if __name__=='__main__': main()
