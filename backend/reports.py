from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
import qrcode
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak,KeepTogether

def render_pdf(record:dict,verify_url:str,data_dir:Path)->bytes:
    output=BytesIO();styles=getSampleStyleSheet();styles['Title'].textColor=colors.HexColor('#214e3d')
    styles['BodyText'].fontSize=9;styles['BodyText'].leading=12
    P=lambda text:Paragraph(escape(str(text).replace('−','-').replace('–','-')),styles['BodyText'])
    def table(rows,widths):
        t=Table([[P(c) for c in row] for row in rows],colWidths=widths,repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e2ecd9')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f5f7f1'),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));return t
    fmt=lambda x,s='': 'Unavailable' if x is None else f'{x:g}{s}'
    story=[Paragraph('OnionGrade AI',styles['Title']),Paragraph('DEMO ANALYSIS - MOCK PREDICTIONS' if record['demo'] else 'VISIBLE BULB HEALTH ANALYSIS',styles['Heading2'])]
    for key in ('id','created_at','inspector','variety','model_version','grading_spec'):
        story.extend([P(f'{key.replace("_"," ").title()}: {record[key]}'),Spacer(1,4)])
    story.extend([Spacer(1,10),table([['Measure','Result'],['Detected / marked regions',record['total_onions']],['Grade A (resolved subset)',fmt(record['grade_a_percentage'],'%')],['Pending review',record['review_count']],['URS',fmt(record['urs_percentage'],'%')],['AI Visual Quality Score (unofficial)',fmt(record['quality_score'],' / 100')],['Mean model confidence',fmt(record['confidence_statistics']['mean'])],['Diameter avg / min / max (mm)',' / '.join(fmt(record[k]) for k in ('average_diameter','min_diameter','max_diameter'))]], [240,270]),Spacer(1,10),P(record['denominator_policy']),Spacer(1,6),P(record['urs_message']),Spacer(1,6),P(record['score_explanation']['formula']),P('Score weights: '+str(record['score_explanation']['weights'])),P('Weighted deductions: '+str(record['score_explanation']['deductions'])),Spacer(1,8),P('Calibration: '+record['calibration']['message'])])
    if record['calibration']['available']: story.append(P(f"Measurement method: {record['calibration']['method']}; reference {record['calibration']['reference_mm']} mm; scale {record['calibration']['mm_per_pixel']:.6f} mm/pixel; marker or line points {record['calibration']['points']}"))
    story.extend([Spacer(1,12),Paragraph('Limitations',styles['Heading3'])]+[P(x) for x in record['limitations']])
    story.extend([PageBreak(),Paragraph('Image evidence',styles['Heading1'])])
    for suffix,label in [('original','Original image'),('annotated','Annotated image - '+('mock geometry' if record['demo'] else 'user regions / trained health predictions'))]:
        path=data_dir/f"{record['id']}-{suffix}.jpg"
        w,h=ImageReader(str(path)).getSize();scale=min(500/w,265/h)
        story.extend([Paragraph(label,styles['Heading3']),Image(str(path),width=w*scale,height=h*scale),Spacer(1,12)])
    story.extend([PageBreak(),Paragraph('Per-onion findings',styles['Heading1']),table([['Class','Count']]+[[k,v] for k,v in record['counts'].items()],[340,170]),Spacer(1,12)])
    for d in record['detections']:
        eligibility='UNRESOLVED' if d['grade_a_candidate'] is None else 'ELIGIBLE' if d['grade_a_candidate'] else 'NOT ELIGIBLE'
        measure=d.get('measurement') or {}
        text=[Paragraph(f"Onion #{d['id']} - {escape(d.get('health_label',d['class']))}",styles['Heading3']),P(f"Class: {d['class']} | Confidence: {d['confidence']:.1%} | Diameter: {fmt(d['diameter_mm'],' mm')} | Size: {d.get('size_category') or 'Unavailable'} | Grade A: {eligibility}"),P(f"Width / height: {fmt(measure.get('width_mm'),' mm')} / {fmt(measure.get('height_mm'),' mm')}"),P('Region source: '+d['region_source']),P('Defects: '+(', '.join(x['type'] for x in d['defects']) or 'No specific defect finding'))]+[P(reason) for reason in d['reasons']]+[Spacer(1,8)]
        story.append(KeepTogether(text))
    qr=BytesIO();qrcode.make(verify_url).save(qr,format='PNG');qr.seek(0)
    story.extend([Spacer(1,12),Paragraph('Verification',styles['Heading2']),Image(qr,width=75,height=75),P('SHA-256 of canonical analysis record (not a digital signature):'),P(record['report_hash']),P('The separate PDF byte hash is supplied by the report endpoint and public verification API. Scan the QR to compare. Grading rules are illustrative, not legally authoritative.')])
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.grey);canvas.drawString(42,22,'OnionGrade AI | '+('DEMO ANALYSIS' if record['demo'] else 'Broad health model; manual grading review required'));canvas.drawRightString(552,22,str(doc.page))
    SimpleDocTemplate(output,pagesize=(595,842),leftMargin=42,rightMargin=42,topMargin=32,bottomMargin=38).build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
