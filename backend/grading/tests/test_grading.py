import math
import pytest
from backend.grading import analyze_onions,load_spec,load_urs
from backend.grading.grading_spec import URSRules
from backend.grading.validators import calibration_scale,diameter_from_polygon

def item(label='GOOD',diameter=55,confidence=.9,defects=None,**extra):
    return {'id':1,'class':label,'confidence':confidence,'diameter_mm':diameter,'defects':defects or [],'visibility_issues':[],**extra}
def grade(items,spec=None,urs=None): return analyze_onions(items,spec or load_spec(),urs or load_urs())

@pytest.mark.parametrize('diameter,eligible',[(44.9,False),(45,True),(55,True),(65,True),(65.1,False),(None,None)])
def test_size_boundaries(diameter,eligible): assert grade([item(diameter=diameter)])['detections'][0]['grade_a_candidate'] is eligible
def test_uncertain_excluded_from_denominator():
    r=grade([item(),item(confidence=.49),item('DAMAGED',defects=[{'type':'MECHANICAL_INJURY','confidence':.95}])])
    assert r['valid_onions']==2 and r['grade_a_percentage']==50 and r['review_count']==1
    assert r['detections'][1]['class']=='REVIEW_REQUIRED'
def test_missing_calibration_is_not_a_fail_or_a_pass():
    r=grade([item(diameter=None)]);assert r['grade_a_percentage'] is None and r['review_required']
def test_urs_disabled_and_configured():
    data=[item(),item('ROTTEN',defects=[{'type':'ROTTING','confidence':.9}])]
    assert grade(data)['urs_percentage'] is None
    rules=URSRules(version='test-official',enabled=True,authoritative_source='Test-only source',classes=['ROTTEN'])
    assert grade(data,urs=rules)['urs_percentage']==50
    with pytest.raises(ValueError): URSRules(version='bad',enabled=True,classes=['ROTTEN'])
def test_quality_score_formula():
    r=grade([item(),item('ROTTEN',defects=[{'type':'ROTTING','confidence':.9}])]);assert r['quality_score']==85 and r['score_explanation']['deductions']['ROTTEN']==15
def test_broad_health_cannot_pass_grading():
    r=grade([item(eligibility_blocked='Subtype checks missing')]);assert r['grade_a_percentage'] is None and r['quality_score'] is None
def test_no_data_and_nan():
    assert grade([])['grade_a_percentage'] is None
    with pytest.raises(ValueError): grade([item(confidence=float('nan'))])
def test_calibration_math_and_validation():
    assert diameter_from_polygon([[0,0],[10,0],[10,10],[0,10]],None) is None
    assert calibration_scale(50,[[10,10],[110,10]],200,200)['mm_per_pixel']==.5
    assert diameter_from_polygon([[0,0],[10,0],[10,10],[0,10]],.5)==round(10/math.sqrt(math.pi),2)
    with pytest.raises(ValueError): calibration_scale(50,[[0,0],[1,1]],200,200)
    with pytest.raises(ValueError): calibration_scale(50,[[0,0],[201,0]],200,200)
    with pytest.raises(ValueError): calibration_scale(50,None,200,200)
def test_configurable_defect_and_surface_rules():
    spec=load_spec();spec.defect_rules['CUT_CRACK']='ALLOWED'
    assert grade([item(defects=[{'type':'CUT_CRACK','confidence':.9}])],spec)['grade_a_percentage']==100
    assert grade([item(defects=[{'type':'SMUT_SURFACE_PERCENT','confidence':.9,'surface_percent':11}])])['grade_a_percentage']==0
    assert grade([item(defects=[{'type':'SMUT_SURFACE_PERCENT','confidence':.9}])])['review_required']
