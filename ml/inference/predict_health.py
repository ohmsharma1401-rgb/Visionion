import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from PIL import Image
from backend.inference import health_predict

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('image');args=parser.parse_args()
    with Image.open(args.image) as image: label,confidence,probabilities=health_predict(image)
    print(json.dumps({'label':label,'confidence':confidence,'probabilities':probabilities,'scope':'Broad health of one user-confirmed bulb, not defect type or Grade A.'},indent=2))
