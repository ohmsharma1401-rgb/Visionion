import {useState} from 'react';
import {ArrowLeft,ArrowRight,Camera,Upload} from 'lucide-react';
import type {BatchDetails} from '../types';

export const emptyBatch:BatchDetails={batch_id:'',farm:'',operator:'',origin:'',expected_kg:null,notes:''};

export function InspectionSetup({value,onChange,onStart,onBack,variety,onVariety}:{value:BatchDetails;onChange:(value:BatchDetails)=>void;onStart:(method:'camera'|'upload')=>void;onBack:()=>void;variety:string;onVariety:(value:string)=>void}){
 const [method,setMethod]=useState<'camera'|'upload'>('camera');
 const field=(key:keyof BatchDetails,text:string,placeholder:string)=><label>{text}<input value={value[key]??''} placeholder={placeholder} onChange={event=>onChange({...value,[key]:event.target.value})}/></label>;
 return <div className="inspection-setup">
  <button className="text-back" onClick={onBack}><ArrowLeft size={15}/> Back to dashboard</button>
  <div className="page-block-title"><span className="eyebrow">NEW INSPECTION</span><h1>Start with the batch.</h1><p>Record the lot details, then capture an onion image for analysis.</p></div>
  <section className="setup-card"><h2><span className="step-dot">1</span> Batch details</h2><div className="setup-grid">
   {field('batch_id','Batch ID','Your lot or batch ID')}{field('farm','Farm / facility','Farm or facility name')}
   {field('operator','Operator name','Inspector or operator')}{field('origin','Origin','City, state or region')}
   <label>Expected quantity (kg)<input type="number" min="0" max="10000000" value={value.expected_kg??''} placeholder="Optional" onChange={event=>onChange({...value,expected_kg:event.target.value===''?null:Number(event.target.value)})}/></label>
   <label>Onion variety<select value={variety} onChange={event=>onVariety(event.target.value)}><option>Red onion</option><option>White onion</option><option>Mixed / unspecified</option></select></label>
   <label className="wide-field">Notes (optional)<textarea value={value.notes} maxLength={1000} placeholder="Storage conditions, handling or quality concerns" onChange={event=>onChange({...value,notes:event.target.value})}/></label>
  </div></section>
  <section className="setup-card"><h2><span className="step-dot">2</span> Capture method</h2><div className="method-grid">
   <button className={method==='camera'?'selected':''} onClick={()=>setMethod('camera')}><Camera size={22}/><strong>Camera capture</strong><small>Use the live guide and printed size marker.</small></button>
   <button className={method==='upload'?'selected':''} onClick={()=>setMethod('upload')}><Upload size={22}/><strong>File upload</strong><small>Select an image from your device.</small></button>
  </div></section>
  <button className="primary setup-start" onClick={()=>onStart(method)}>Continue to image capture <ArrowRight size={17}/></button>
  <p className="setup-note">Batch fields are saved with the analysis. Grade A and URS remain unresolved without the required expert labels and approved rules.</p>
 </div>;
}
