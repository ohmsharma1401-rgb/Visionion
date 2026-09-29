"""Pure per-instance grading. Unresolved eligibility is None, never a fabricated pass."""
from collections import Counter
from copy import deepcopy
from statistics import mean
from .grading_spec import CLASSES, GradingSpec, URSRules

def analyze_onions(detections: list[dict], spec: GradingSpec, urs: URSRules) -> dict:
    output = []
    for item in detections:
        d = deepcopy(item)
        label, confidence = d['class'], d['confidence']
        if label not in CLASSES or not 0 <= confidence <= 1:
            raise ValueError('Invalid class or confidence')
        reasons, failures = [], []
        uncertain = confidence < spec.review_confidence or label == 'REVIEW_REQUIRED' or bool(d.get('visibility_issues'))
        if uncertain:
            reasons.append('AI is uncertain about this onion; exclude it from the resolved grading denominator.')
            reasons.extend(d.get('visibility_issues', []))
            reasons.extend(d.get('classification_warnings', []))
        diameter = d.get('diameter_mm')
        if diameter is not None:
            if not 0 < diameter < float('inf'):
                raise ValueError('Invalid physical diameter')
            if diameter < spec.size_range_mm.min:
                failures.append(f'Diameter {diameter:.1f} mm is below the {spec.size_range_mm.min:g} mm minimum.')
                if not uncertain and label == 'GOOD': d['class'] = 'UNDERSIZED'
            elif diameter > spec.size_range_mm.max:
                failures.append(f'Diameter {diameter:.1f} mm exceeds the {spec.size_range_mm.max:g} mm maximum.')
        if label == 'UNDERSIZED' and diameter is None:
            uncertain = True
            reasons.append('The model suggests undersize, but physical size requires calibration.')
        for defect in d.get('defects', []):
            kind = defect['type']
            if defect['confidence'] < spec.review_confidence:
                uncertain = True
                reasons.append(f'{kind}: low-confidence defect needs manual review.')
            elif spec.defect_rules.get(kind) == 'NOT_ALLOWED':
                failures.append(f'{kind.replace("_", " ").title()} is not allowed under {spec.spec_version}.')
            elif kind in spec.tolerances:
                measured = defect.get('surface_percent')
                if measured is None:
                    uncertain = True
                    reasons.append(f'{kind}: surface percentage unavailable; tolerance cannot be checked.')
                elif measured > spec.tolerances[kind]:
                    failures.append(f'{kind}: {measured:g}% exceeds the {spec.tolerances[kind]:g}% tolerance.')
            elif spec.defect_rules.get(kind) != 'ALLOWED':
                uncertain = True
                reasons.append(f'{kind}: no configured rule; manual review required.')
        if label in ('DAMAGED', 'ROTTEN', 'SPROUTED') and not d.get('defects'):
            uncertain = True
            reasons.append('Defect class has no supporting defect finding.')
        if uncertain:
            d['class'] = 'REVIEW_REQUIRED'
            candidate = None
        elif d.get('eligibility_blocked'):
            candidate = None
            reasons.append(d['eligibility_blocked'])
        elif failures:
            candidate = False
        elif diameter is None:
            candidate = None
            reasons.append('Physical size cannot be reliably estimated without a reference scale; Grade A eligibility is unresolved.')
        else:
            candidate = True
            reasons.append(f'Visible defect rules and {spec.size_range_mm.min:g}–{spec.size_range_mm.max:g} mm size band are met under {spec.spec_version}.')
        d.update(grade_a_candidate=candidate, review_required=candidate is None, classification_uncertain=uncertain, reasons=failures+reasons)
        output.append(d)
    counts = Counter({c: 0 for c in CLASSES})
    for d in output: counts[d['class']] += 1
    valid = [d for d in output if d['grade_a_candidate'] is not None]
    eligible = sum(d['grade_a_candidate'] is True for d in valid)
    grade_pct = round(eligible / len(valid) * 100, 2) if valid else None
    visual = [d for d in output if not d['classification_uncertain']]
    deductions = {c: round(sum(d['class'] == c for d in visual) * weight / len(visual), 3) if visual else 0 for c, weight in spec.quality_weights.items()}
    score = round(max(0, 100-sum(deductions.values())), 2) if visual and not any(d.get('eligibility_blocked') for d in output) else None
    urs_pct = round(sum(d['class'] in urs.classes for d in valid) / len(valid) * 100, 2) if urs.enabled and valid else None
    diameters = [d['diameter_mm'] for d in output if d.get('diameter_mm') is not None and not d['classification_uncertain']]
    review = sum(d['review_required'] for d in output)
    return {'detections': output, 'total_onions': len(output), 'valid_onions': len(valid), 'grade_a_count': eligible,
            'counts': dict(counts), 'good_count': counts['GOOD'], 'damaged_count': counts['DAMAGED'], 'rotten_count': counts['ROTTEN'],
            'sprouted_count': counts['SPROUTED'], 'undersized_count': counts['UNDERSIZED'], 'review_count': review,
            'grade_a_percentage': grade_pct, 'urs_percentage': urs_pct, 'urs_message': urs.message if not urs.enabled else f'URS rules: {urs.version}; source: {urs.authoritative_source}',
            'quality_score': score, 'quality_score_label': 'AI Visual Quality Score',
            'score_explanation': {'base': 100, 'weights': spec.quality_weights, 'deductions': deductions, 'denominator': len(visual), 'formula': '100 − sum(class count × configured penalty) / visually resolved onion count. Not an official grade.'},
            'denominator_policy': f'{len(valid)} resolved Grade A decisions / {len(output)} detections. {review} unresolved decisions excluded; percentage is partial when review is pending.',
            'review_required': bool(review or not output), 'status': 'REVIEW_REQUIRED' if review or not output else 'ANALYZED',
            'average_diameter': round(mean(diameters), 2) if diameters else None, 'min_diameter': min(diameters) if diameters else None, 'max_diameter': max(diameters) if diameters else None,
            'defect_distribution': dict(Counter(defect['type'] for d in output for defect in d.get('defects', []))),
            'confidence_statistics': {'mean': round(mean(d['confidence'] for d in output), 4) if output else None, 'min': min((d['confidence'] for d in output), default=None), 'max': max((d['confidence'] for d in output), default=None)}}
