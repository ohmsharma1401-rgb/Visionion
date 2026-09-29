# Dataset discovery

Public catalog checked 2026-09-29: [Image Dataset of Red and White Onion Bulbs and Leaves](https://data.mendeley.com/datasets/42bcyncfhy/1), DOI 10.17632/42bcyncfhy.1, version 1. The publisher lists 24,000 images, including red/white bulbs, healthy/unhealthy and single/multiple categories, with CC BY 4.0 licensing. It supplies raw images rather than the required five-class instance segmentation annotations.

Candidate only: no files were downloaded, audited or used for training. Verify labels, attribution, duplicates, collection permissions and lot identifiers before adoption. Annotate damaged/rotten/sprouted/undersized bulbs separately; obtain real diameter measurements. Preserve lot-isolated holdouts. Synthetic samples in `/samples` are software-test fixtures, never evidence of model quality.

The export scripts pin the Ultralytics 8.3 API series using `format='tflite', int8=True`. Newer versions use a unified [LiteRT export interface](https://docs.ultralytics.com/integrations/litert/); review and revalidate conversion when upgrading. Training/export were not executed in this prototype.
