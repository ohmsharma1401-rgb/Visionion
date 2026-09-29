import argparse
from ultralytics import YOLO

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('weights')
    parser.add_argument('--data',default='ml/dataset.yaml')
    args=parser.parse_args()
    YOLO(args.weights).export(format='tflite',int8=True,data=args.data,imgsz=640)
    # Promotion is manual: verify accuracy, latency and size on the target phone.
