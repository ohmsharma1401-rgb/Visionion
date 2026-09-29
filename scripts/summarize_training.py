import json
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR',str(Path('tmp/matplotlib').resolve()))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

metadata=json.loads(Path('ml/models/bulb-health-v1.json').read_text())
history=json.loads(Path('ml/models/training-history.json').read_text())
fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
matrix=np.array(metadata['test']['confusion_matrix'])
axes[0].imshow(matrix,cmap='Greens');names=['Healthy bulb','Unhealthy bulb','Leaf only']
axes[0].set_xticks(range(3),names);axes[0].set_yticks(range(3),names)
axes[0].set(xlabel='Predicted label',ylabel='Source folder label',title='Held-out confusion matrix (2,137 images)')
for (y,x),value in np.ndenumerate(matrix):axes[0].text(x,y,str(value),ha='center',va='center',color='white' if value>500 else '#203c2c',fontsize=13)
axes[1].plot([r['epoch'] for r in history],[r['validation']['macro_f1'] for r in history],marker='o',color='#315d42')
axes[1].axvline(metadata['best_epoch'],linestyle='--',color='#bc9751',label='Selected epoch')
axes[1].set(xlabel='Epoch',ylabel='Validation macro F1',title='Validation-only checkpoint selection');axes[1].legend();axes[1].grid(alpha=.2)
fig.suptitle('OnionGrade bulb-health-v1 — provisional dataset evaluation',fontweight='bold')
fig.savefig('output/training-evaluation.png',dpi=160)
print('Saved output/training-evaluation.png')
