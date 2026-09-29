from collections import defaultdict
from dataset_loader import load_manifest

rows=load_manifest();hashes=defaultdict(set);groups=defaultdict(set)
for row in rows:
    hashes[row['sha256']].add(row['split']);groups[row['group']].add(row['split'])
assert all(len(s)==1 for s in hashes.values()),'Exact duplicate crosses a split'
assert all(len(s)==1 for s in groups.values()),'Sequence proxy group crosses a split'
assert not any(r['multiple_bulbs'] and r['split']!='multiple_stress' for r in rows)
print(f'PASS: {len(rows)} images, no duplicate hash or proxy group crosses splits. True lot independence remains unknown.')
