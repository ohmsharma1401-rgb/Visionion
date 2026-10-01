from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
import qrcode
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak,KeepTogether

def render_pdf(record:dict,verify_url:str,data_dir:Path)->bytes:
    output=BytesIO();styles=getSampleStyleSheet();styles['Title'].textColor=colors.HexColor('#7d2747')
    styles['BodyText'].fontSize=9;styles['BodyText'].leading=12
    P=lambda text:Paragraph(escape(str(text).replace('−','-').replace('–','-')),styles['BodyText'])
    def table(rows,widths):
        t=Table([[P(c) for c in row] for row in rows],colWidths=widths,repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f0dfd1')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#fbf6ef'),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));return t
    fmt=lambda x,s='': 'Unavailable' if x is None else f'{x:g}{s}'
    story=[Paragraph('Visionion',styles['Title']),Paragraph('DEMO ANALYSIS - MOCK PREDICTIONS' if record['demo'] else 'ONION QUALITY EVIDENCE REPORT',styles['Heading2'])]
    if record.get('model_version') == 'bulb-health-all-v2':
        story.extend([P('Training base: 16,271 usable images. No independent holdout evaluation exists for this checkpoint; no validated accuracy figure is claimed. Model confidence is not accuracy.'), P('Good, Poor and Review required are visual health assessments, not official procurement grades. Grade A and URS require an applicable official specification and sufficient observations. Whole-photo predictions do not establish individual onion counts or lot-level percentages.'), Spacer(1,8)])
    visual_grade=record.get('visual_grade')
    if visual_grade:
        if visual_grade.get('quality_label'):
            story.append(Paragraph('Visual quality: '+escape(visual_grade['quality_label']),styles['Heading2']))
        story.extend([Paragraph('AI visual grade: '+escape(visual_grade['label']),styles['Heading2']),P(visual_grade['reason']),P('Based on visible appearance. Policy: '+visual_grade['policy']),Spacer(1,8)])
    for key in ('id','created_at','inspector','variety','model_version','grading_spec'):
        story.extend([P(f'{key.replace("_"," ").title()}: {record[key]}'),Spacer(1,4)])
    details=record.get('batch_details') or {}
    for key in ('batch_id','farm','operator','origin','expected_kg','notes'):
        if details.get(key) not in (None,''):
            story.extend([P(f'{key.replace("_"," ").title()}: {details[key]}'),Spacer(1,4)])
    image_level=record.get('analysis_scope')=='whole_image'
    story.extend([Spacer(1,10),table([['Measure','Result'],['Photos assessed' if image_level else 'Detected / marked regions',1 if image_level else record['total_onions']],['Grade A', 'Not assessed' if image_level else fmt(record['grade_a_percentage'],'%')],['Review status','Manual review recommended' if image_level else record['review_count']],['URS', 'Not assessed' if image_level else fmt(record['urs_percentage'],'%')],['AI Visual Quality Score (unofficial)',fmt(record['quality_score'],' / 100')],['Mean model confidence',fmt(record['confidence_statistics']['mean'])],['Diameter avg / min / max (mm)','Not measured' if image_level else ' / '.join(fmt(record[k]) for k in ('average_diameter','min_diameter','max_diameter'))]], [240,270]),Spacer(1,10),P(record['denominator_policy']),Spacer(1,6),P(record['urs_message']),Spacer(1,6),P(record['score_explanation']['formula']),P('Score weights: '+str(record['score_explanation']['weights'])),P('Weighted deductions: '+str(record['score_explanation']['deductions'])),Spacer(1,8),P('Calibration: '+record['calibration']['message'])])
    if record['calibration']['available']: story.append(P(f"Measurement method: {record['calibration']['method']}; reference {record['calibration']['reference_mm']} mm; scale {record['calibration']['mm_per_pixel']:.6f} mm/pixel; marker or line points {record['calibration']['points']}"))
    story.extend([Spacer(1,12),Paragraph('Limitations',styles['Heading3'])]+[P(x) for x in record['limitations']])
    story.extend([PageBreak(),Paragraph('Image evidence',styles['Heading1'])])
    for suffix,label in [('original','Original image'),('annotated','Annotated image - '+('mock geometry' if record['demo'] else 'whole-image health screen; no onion boundaries' if image_level else 'user regions / trained health predictions'))]:
        path=data_dir/f"{record['id']}-{suffix}.jpg"
        w,h=ImageReader(str(path)).getSize();scale=min(500/w,265/h)
        story.extend([Paragraph(label,styles['Heading3']),Image(str(path),width=w*scale,height=h*scale),Spacer(1,12)])
    story.extend([PageBreak(),Paragraph('Photo-level health result' if image_level else 'Per-onion findings',styles['Heading1']),table([['Class','Count']]+[[k,v] for k,v in record['counts'].items()],[340,170]),Spacer(1,12)])
    for d in record['detections']:
        eligibility='NOT ASSESSED' if image_level else 'UNRESOLVED' if d['grade_a_candidate'] is None else 'ELIGIBLE' if d['grade_a_candidate'] else 'NOT ELIGIBLE'
        measure=d.get('measurement') or {}
        item_name='Whole photo' if image_level else f"Onion #{d['id']}"
        text=[Paragraph(f"{item_name} - {escape(d.get('health_label',d['class']))}",styles['Heading3']),P(f"Class: {d['class']} | Confidence: {d['confidence']:.1%} | Diameter: {fmt(d['diameter_mm'],' mm')} | Size: {d.get('size_category') or 'Unavailable'} | Grade A: {eligibility}"),P(f"Width / height: {fmt(measure.get('width_mm'),' mm')} / {fmt(measure.get('height_mm'),' mm')}"),P('Region source: '+d['region_source']),P('Defects: '+(', '.join(x['type'] for x in d['defects']) or 'No specific defect finding'))]+[P(reason) for reason in d['reasons']]+[Spacer(1,8)]
        if d.get('visual_grade'):
            text.insert(1,P('AI visual grade: '+d['visual_grade']['label']))
        story.append(KeepTogether(text))
    qr=BytesIO();qrcode.make(verify_url).save(qr,format='PNG');qr.seek(0)
    story.extend([Spacer(1,12),Paragraph('Verification',styles['Heading2']),Image(qr,width=75,height=75),P('SHA-256 of canonical analysis record (not a digital signature):'),P(record['report_hash']),P('The separate PDF byte hash is supplied by the report endpoint and public verification API. Scan the QR to compare. Grading rules are illustrative, not legally authoritative.')])
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#7d2747'));canvas.drawString(42,22,'Visionion | '+('DEMO ANALYSIS' if record['demo'] else 'Broad health model; manual grading review required'));canvas.drawRightString(552,22,str(doc.page))
    SimpleDocTemplate(output,pagesize=(595,842),leftMargin=42,rightMargin=42,topMargin=32,bottomMargin=38).build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
