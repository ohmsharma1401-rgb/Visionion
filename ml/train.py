"""Run only after dataset annotation and lot-isolated splitting."""
import argparse
from ultralytics import YOLO

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',default='ml/dataset.yaml')
    parser.add_argument('--model',default='yolov8n-seg.pt')
    parser.add_argument('--epochs',type=int,default=100)
    args=parser.parse_args()
    YOLO(args.model).train(data=args.data,epochs=args.epochs,imgsz=640,seed=42,project='ml/runs',name='onion-baseline',degrees=15,fliplr=.5,hsv_v=.3,mosaic=.5,mixup=.1)
