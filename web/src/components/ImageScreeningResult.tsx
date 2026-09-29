import {ArrowRight,CheckCircle2,Info,ShieldAlert} from 'lucide-react';
import type {Analysis} from '../types';
import {AnnotatedImage} from './AnnotatedImage';

const display=(health:string|undefined)=>health==='HEALTHY_BULB'?'Likely healthy':health==='UNHEALTHY_BULB'?'Unhealthy · review recommended':health==='LEAF_ONLY'?'Bulb health could not be assessed':'Needs manual review';

export function ImageScreeningResult({result,onNew,onReport,onJson,busy}:{result:Analysis;onNew:()=>void;onReport:()=>void;onJson:()=>void;busy:boolean}){
 const detection=result.detections[0];
 const healthy=detection?.health_label==='HEALTHY_BULB'&&detection.class==='GOOD';
 const uncertain=!!detection?.classification_warnings?.length||detection?.health_label==='LEAF_ONLY'||detection?.health_label==='HEALTHY_BULB'&&!healthy;
 const title=result.visual_grade?.label||(detection?.health_label==='LEAF_ONLY'?'Unable to assess bulb health':uncertain?'Needs manual review':display(detection?.health_label));
 return <div className="image-screening-result">
  <div className="screening-heading"><span className="eyebrow">WHOLE PHOTO · TRAINED BULB HEALTH MODEL</span><h2>Photo health screening</h2><p>The AI assessed the uploaded image as a whole. It does not draw onion outlines or separate bulbs in this result.</p></div>
  <div className="screening-actions"><span className="pill">{result.model_version}</span><div className="buttons"><button className="secondary" onClick={onNew}>New photo</button><button className="secondary" onClick={onJson}>JSON</button><button className="primary" disabled={busy} onClick={onReport}>{busy?'Generating…':'Download report'} <ArrowRight size={15}/></button></div></div>
  <div className="screening-grid"><AnnotatedImage result={result} selected={detection?.id||1} onSelect={()=>{}}/><section className="card screening-card"><span className="eyebrow">AI VISUAL GRADE</span><div className={'screening-verdict '+(healthy?'healthy':'review')}>{healthy?<CheckCircle2 size={26}/>:<ShieldAlert size={26}/>}<strong>{title}</strong></div><div className="screening-confidence"><span>Model confidence</span><strong>{detection?`${(detection.confidence*100).toFixed(1)}%`:'Not available'}</strong></div>{result.visual_grade&&<p>{result.visual_grade.reason}</p>}<div className="screening-note"><Info size={18}/><span>For the clearest result, upload one well-lit onion. If the photo contains a pile, this result combines the visible evidence and may not represent every bulb.</span></div><div className="screening-unavailable"><span>Grade A</span><b>Not assessed</b><span>URS</span><b>Not assessed</b><span>Size</span><b>Needs a scale and an individual outline</b></div></section></div>
  {uncertain&&<div className="callout amber">{detection?.classification_warnings?.length?detection.classification_warnings.join(" "):"The model is uncertain. Retake a clear close-up or inspect the onion manually."}</div>}
  {detection?.health_probabilities&&<section className="card panel"><h3>Model prediction scores</h3><p>These scores describe the model output, not the percentage of healthy onions or a guarantee of correctness.</p>{Object.entries(detection.health_probabilities).map(([name,value])=><div className="small-row" key={name}><span>{name==='HEALTHY_BULB'?'Healthy bulb':name==='UNHEALTHY_BULB'?'Unhealthy bulb':'Leaf-only / bulb health unsupported'}</span><b>{(value*100).toFixed(1)}%</b></div>)}</section>}<section className="card panel screening-limitations"><h3>What this result can tell you</h3>{result.limitations.map((item,index)=><p key={index}>{item}</p>)}<p>Want separate findings for each bulb? Start a new photo and use the optional “Outline onion” tool. Outlines enable individual classification and measurement; they are not automatic detections.</p></section>
 </div>;
}
