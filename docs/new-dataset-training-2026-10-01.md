# New image-level health model

Owner requested retraining on the new 24,000-image archive and separate
Good/Poor/Review required quality for group photographs.

The uploaded outer ZIP contains one nested ZIP. Its 24,000 images decoded
successfully: 12,367 healthy-bulb, 5,461 unhealthy-bulb, and 6,172 leaf images.
Mixed folders describe red/white bulb ratios, all labeled Healthy, rather than
mixtures of healthy and unhealthy bulbs. No boxes, masks, defect subtypes,
physical measurements, or official grading labels were supplied.

Training uses a fresh ImageNet MobileNetV3 Small backbone, 160px RGB input,
256px gray-padded preparation, ImageNet normalization, balanced cross-entropy,
training-only spatial/color augmentation, AdamW and validation checkpoint
selection. The old all-image v2 checkpoint is not used as initialization.

The split reserves 16,542 training, 3,803 validation and 3,655 test photographs.
Source SHA-256 and filename proxy groups do not overlap. Group-bulb photos:
6,042 train, 1,403 validation, 1,286 test. The group evaluation is a subset of
the test set, not an additional independent dataset. The held-out photos are
not used in checkpoint or confidence-threshold selection.

Important limitation: representative photos contain repeated views of the
same onions and class-associated backgrounds. Consecutive-100 filename proxy
groups cannot guarantee independent objects, sessions or lots. Near-duplicate
independence is not established. Evaluation is an internal held-out estimate,
not validated farm-level performance or evidence of improved deployment
accuracy. Independent capture sessions remain needed.

The runtime produces image-level health for a group. It does not count bulbs
or establish the fraction healthy. Quality is Good, Poor or Review required;
the owner-defined A label requires healthy confidence strictly greater than
90% and no uncertainty warnings. It remains unofficial, separate from
official Grade A/URS and calibrated size. Neither the A rule nor retraining
adds supervised instance detection.

Training history and final evaluation are saved in `ml/models/` as
`v3-training-history.json` and `bulb-health-v3.json`. Preparation and training
commands are `ml/datasets/prepare_new_health.py` and
`ml/training/train_new_health.py --epochs 12 --workers 0` using the project
Python environment. Source contact sheet and representative provenance are
in `output/v3-training/`.

Completed 12 epochs in 926.7 seconds on RTX 4050; validation selected epoch 10.
Internal test accuracy 98.11%, macro F1 0.9782; group subset accuracy 99.69%,
supported-class macro F1 0.9964. Validation-selected review threshold: 0.65.
These results do not establish improved performance on independent farms.
All 12 representative original ZIP photos matched their source labels through
production inference; 10 passed the existing API image-quality gate. Group
samples produced Good/A for healthy photos and Poor for unhealthy photos.
Fourteen focused application tests and the production frontend build passed.
