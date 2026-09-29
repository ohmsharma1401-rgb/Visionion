# Model card — bulb-health-all-v2 and bulb-health-v1

## Active all-image checkpoint

`bulb-health-all-v2` is the active local API checkpoint. It fine-tuned v1 for six additional GPU epochs on **all 16,271 unique usable images** from the supplied archive: 8,219 healthy bulbs, 4,014 unhealthy bulbs and 4,038 leaf-only images. This includes the former 8,177 training, 1,726 validation, 2,137 test and 4,231 multi-bulb stress images. The 4,231 multi-bulb images carry only image-level labels; this training does not teach instance detection or per-onion segmentation.

The active checkpoint is `ml/models/bulb-health-all-v2.pt`, SHA-256 `1fd4ea7f18c0a41625dd52dbaae16107f37c89483422a62c4b86c945c222bb4d`. Metadata and training history are in `ml/models/bulb-health-all-v2.json` and `ml/models/all-images-training-history.json`. The 0.65 review threshold was inherited from v1 and was not recalibrated after all-image training. **No independent holdout remains for v2.** A new, separately collected and labeled lot-level evaluation is required before estimating its deployment accuracy. The v1 metrics below describe v1 only.

Reproduce v2 after preparing the dataset and creating v1 using `python ml/training/train_all_health.py`. The script verifies source images and checkpoint hashes before training.

## Earlier evaluated checkpoint

**Status:** trained and integrated in the local app on 2026-09-29. This replaces the earlier fixed-demo-only runtime for supported broad bulb-health predictions.

## Scope and architecture

TorchVision MobileNetV3 Small with an ImageNet1K-pretrained backbone and a three-class head: HEALTHY_BULB, UNHEALTHY_BULB, LEAF_ONLY. Input is RGB, aspect-preserving padded to 256 then resized to 160, normalized using ImageNet mean/std. Per-onion operation requires a user-confirmed single bulb or separately drawn bulb regions. Region cropping is not learned segmentation and has not been independently benchmarked.

Healthy is broad visible-health evidence. Unhealthy is **not** automatically rotten, damaged, sprouted, mold or any other subtype. Leaf-only is a rejection category, not a general out-of-distribution detector. Other objects can still receive confident wrong predictions. The model cannot establish Grade A, URS, physical size, exact weight, internal quality or food safety.

## Data provenance

User-supplied nested archive: `Image Dataset of Red and White Onion Bulbs and Lea.zip`. Inspected contents: 16,300 JPEGs, 12,260 bulbs and 4,040 leaves, red/white varieties, healthy/unhealthy and single/multiple folders. Unlike a catalog's advertised size, these are the actual counts in the supplied archive. No boxes, masks, defect-subtype labels, lot/session IDs or measured diameters exist in this archive.

29 exact SHA-256 duplicates were removed, no conflicting-label hash duplicates or corrupt images were found. Source filenames, labels, group IDs and hashes are retained in the preparation manifest. Other named datasets were not merged; their labels and provenance were not supplied.

## Split and leakage limitations

Training: 8,177; validation: 1,726; held-out test: 2,137; separate multi-bulb stress set: 4,231. Single-bulb/leaf data are split by folder + blocks of 100 consecutive numeric filenames, targeting 70/15/15 by group, seed 42. Exact hash and proxy-group disjointness checks pass. Group sizes cause image proportions to differ from target percentages.

These are proxy groups, **not known independent lots**. The same bulb, adjacent scene, background or collection session may occur in different groups. Perceptual near-duplicates were not exhaustively grouped. High same-source metrics may reflect easier backgrounds or repeated subjects. A new expert-labeled, independently collected lot test is needed before deployment claims.

## Training

PyTorch 2.6.0 + CUDA 12.4, TorchVision 0.21.0, NVIDIA RTX 4050 Laptop GPU (6 GB). AdamW, initial learning rate 0.0003, weight decay 0.0001, batch 64, class-weighted cross entropy, cosine scheduler. Training-only mild crop (70–100% area), horizontal flip, ±12° rotation and restrained brightness/contrast/color variation. No synthetic defective labels or invented masks.

Maximum 12 epochs, patience 4 on validation macro F1. Training completed 10 epochs, selecting epoch 6. Approximately 524 seconds through checkpoint reload and validation; final held-out/stress inference adds time. Threshold 0.65 was selected using validation only to target ≥95% accepted validation accuracy. This does not calibrate softmax probabilities.

## Held-out test

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| Healthy bulb | 0.9980 | 0.9970 | 0.9975 | 1,000 |
| Unhealthy bulb | 0.9941 | 0.9941 | 0.9941 | 338 |
| Leaf only | 0.9988 | 1.0000 | 0.9994 | 799 |

Accuracy 0.9977; macro F1 0.9970. At confidence threshold 0.65, coverage 0.9986 and accepted accuracy 0.9981. These are provisional dataset results with the split caveats above.

Confusion matrix, rows = ground truth, columns = predictions; order healthy/unhealthy/leaf:

```text
997   2   1
  2 336   0
  0   0 799
```

Multi-bulb stress image-level accuracy: 0.8679. This drop is why a full pile is not treated as one bulb or a per-instance classification result. Its saved macro F1 0.5958 includes the leaf class with zero ground-truth support; interpret per-class results and accuracy alongside that convention. No instance mAP, segmentation IoU, Grade A error, size MAE or mobile latency is measurable from the supplied labels.

## Artifacts and reproducibility

- `ml/models/bulb-health-v1.pt`: selected state dict, 6.21 MB.
- `ml/models/bulb-health-v1.json`: metrics, threshold, limitations and checkpoint SHA-256.
- `ml/models/training-history.json`: each epoch's loss and validation metrics.
- `ml/models/bulb-health-v1.torchscript.pt`: CPU TorchScript export, checked against eager output for a reference tensor; no TFLite claim.
- `ml/datasets/prepared/manifest.json`: source image labels, hashes and split provenance.

The inference loader checks checkpoint SHA-256 against the evaluated model metadata. Audit records pin the model/spec version; new analysis snapshots also include the evaluated checkpoint hash. Fixed seed improves repeatability but GPU kernels may not be bitwise deterministic.
