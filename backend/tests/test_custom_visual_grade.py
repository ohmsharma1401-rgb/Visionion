import pytest
from backend.grading.visual_grade import grade_health

@pytest.mark.parametrize('label,confidence,expected',[
    ('HEALTHY_BULB',.90001,'A'),('HEALTHY_BULB',.90,'Good'),
    ('HEALTHY_BULB',.89,'Good'),('UNHEALTHY_BULB',.99,'Poor'),
    ('LEAF_ONLY',.99,'Review required')])
def test_custom_threshold(label,confidence,expected):
    result=grade_health([{'health_label':label,'confidence':confidence}],.65)
    assert result['label']==expected

def test_warnings_prevent_custom_a():
    assert grade_health([{'health_label':'HEALTHY_BULB','confidence':.99,
                         'classification_warnings':['Uncertain crop']}],.65)['label']=='Review required'

def test_mixed_regions_do_not_get_collective_a():
    assert grade_health([{'health_label':'HEALTHY_BULB','confidence':c} for c in (.99,.89)],.65)['label']=='Good'
