"""App-defined visual health grades, independent of size and official eligibility."""

def grade_health(detections, threshold):
    for detection in detections:
        label = detection.get('health_label')
        if label not in ('HEALTHY_BULB', 'UNHEALTHY_BULB'):
            grade, reason = 'Review required', 'The model could not assess bulb health from this image.'
        elif detection['confidence'] < threshold or detection.get('classification_warnings') or detection.get('visibility_issues'):
            grade, reason = 'Review required', 'The prediction is uncertain or the selected bulb is not clearly visible.'
        elif label == 'HEALTHY_BULB':
            grade, reason = 'Good', 'The model predicts a healthy appearance in the assessed image.'
        else:
            grade, reason = 'Poor', 'The model predicts an unhealthy appearance in the assessed image.'
        detection['visual_grade'] = {'label': grade, 'reason': reason, 'policy': 'visual-health-v1', 'confidence_threshold': threshold}
    if len(detections) == 1:
        return dict(detections[0]['visual_grade'])
    grades = [d['visual_grade']['label'] for d in detections]
    grade = 'Review required' if not grades or 'Review required' in grades else 'Poor' if 'Poor' in grades else 'Good'
    return {'label': grade, 'reason': 'Selected regions: '+', '.join(f'{name}: {grades.count(name)}' for name in ('Good', 'Poor', 'Review required'))+'.', 'policy': 'visual-health-v1', 'confidence_threshold': threshold}
