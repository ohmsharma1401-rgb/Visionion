import argparse
import json
from pathlib import Path
from ultralytics import YOLO

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('weights');parser.add_argument('--data',default='ml/dataset.yaml');args=parser.parse_args()
    metrics=YOLO(args.weights).val(data=args.data,split='test')
    Path('ml/evaluation.json').write_text(json.dumps(metrics.results_dict,indent=2))
