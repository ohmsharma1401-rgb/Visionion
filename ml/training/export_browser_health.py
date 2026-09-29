"""Export the deployed health model and verify numerical parity before publishing it.

This checks conversion fidelity, not classification accuracy or browser preprocessing.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import onnx
import onnxruntime as ort
from PIL import Image
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.inference import health_model, METADATA_PATH, MODEL_PATH


def main():
    model, transform, labels = health_model()
    wrapper = torch.nn.Sequential(model, torch.nn.Softmax(dim=1)).eval()
    output = ROOT / 'ml/models/bulb-health-browser.onnx'
    example = torch.zeros(1, 3, 160, 160)
    torch.onnx.export(wrapper, example, str(output), input_names=['image'],
                      output_names=['probabilities'], opset_version=17, dynamo=False)
    onnx.checker.check_model(onnx.load(str(output)))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(output), sess_options=options, providers=['CPUExecutionProvider'])
    inputs = [example]
    generator = torch.Generator().manual_seed(43)
    inputs.extend(torch.randn(1, 3, 160, 160, generator=generator) for _ in range(3))
    manifest = ROOT / 'ml/datasets/prepared/manifest.json'
    if manifest.exists():
        rows = json.loads(manifest.read_text())
        for label in labels:
            for row in [r for r in rows if r['label'] == label][:2]:
                with Image.open(manifest.parent / row['path']) as image:
                    inputs.append(transform(image.convert('RGB')).unsqueeze(0))
    errors = []
    for tensor in inputs:
        with torch.inference_mode():
            expected = wrapper(tensor).numpy()
        actual = session.run(None, {'image': tensor.numpy()})[0]
        np.testing.assert_allclose(actual, expected, rtol=1e-4, atol=1e-5)
        assert actual.argmax() == expected.argmax(), 'Conversion changed the predicted class'
        errors.append(float(np.max(np.abs(actual - expected))))
    metadata = json.loads(METADATA_PATH.read_text())
    export = {
        'model_version': metadata['model_version'], 'labels': labels,
        'source_sha256': hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest(),
        'onnx_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'bytes': output.stat().st_size, 'opset': 17,
        'input': {'name': 'image', 'shape': [1, 3, 160, 160], 'dtype': 'float32',
                  'color': 'RGB', 'mean': [.485, .456, .406], 'std': [.229, .224, .225],
                  'preprocessing': 'EXIF orient; aspect-preserving pad to 256x256 with RGB 127; resize to 160x160; divide by 255; normalize; NCHW'},
        'output': {'name': 'probabilities', 'shape': [1, len(labels)]},
        'confidence_threshold': metadata['confidence_threshold'],
        'conversion_check': {'cases': len(inputs), 'max_absolute_error': max(errors),
                             'scope': 'PyTorch versus native ONNX Runtime, not browser or accuracy validation'},
        'limitations': metadata['limitations'],
    }
    output.with_suffix('.json').write_text(json.dumps(export, indent=2)+'\n')
    print(json.dumps({'file': str(output), 'bytes': export['bytes'], 'parity': export['conversion_check']}))


if __name__ == '__main__':
    main()
