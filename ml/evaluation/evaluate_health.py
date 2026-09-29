import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import torch
from torch.utils.data import DataLoader
from backend.inference import health_model
from ml.training.train_health import OnionImages,evaluate

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--split',choices=['val','test','multiple_stress'],default='test');args=parser.parse_args()
    rows=json.loads(Path('ml/datasets/prepared/manifest.json').read_text());model,_,_=health_model()
    result,_,_=evaluate(model,DataLoader(OnionImages([r for r in rows if r['split']==args.split]),batch_size=64),'cpu')
    print(json.dumps(result,indent=2))
