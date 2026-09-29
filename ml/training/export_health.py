"""Export the trained classifier as TorchScript. Not a TFLite claim."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import torch
from backend.inference import health_model

model,_,_=health_model()
example=torch.zeros(1,3,160,160)
with torch.inference_mode():
    exported=torch.jit.trace(model,example)
    assert torch.allclose(model(example),exported(example),atol=1e-5)
    exported.save('ml/models/bulb-health-v1.torchscript.pt')
print('TorchScript exported; input is normalized RGB NCHW 1x3x160x160. Mobile runtime integration remains separate.')
