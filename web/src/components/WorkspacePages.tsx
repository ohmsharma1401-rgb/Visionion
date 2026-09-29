import {useMemo,useState} from 'react';
import {ArrowRight,CalendarDays,ClipboardList,Download,FileText,Search,Share2} from 'lucide-react';
import type {Analysis,Detection} from '../types';
import {api,download} from '../services/api';

const date=(value:string)=>new Date(value).toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'});
const percent=(value:number|null)=>value===null?'Unavailable':`${value.toFixed(1)}%`;
const name=(value:string)=>value.replaceAll('_',' ').toLowerCase().replace(/^./,letter=>letter.toUpperCase());

export function HomeScreen({history,onInspect,onHistory,signedIn}:{history:Analysis[];onInspect:()=>void;onHistory:()=>void;signedIn:boolean}){
 const actual=history.filter(item=>!item.demo);
 const today=actual.filter(item=>new Date(item.created_at).toDateString()===new Date().toDateString());
 const total=actual.reduce((sum,item)=>sum+item.total_onions,0);
 const resolved=actual.reduce((sum,item)=>sum+item.valid_onions,0);
 const eligible=actual.reduce((sum,item)=>sum+item.grade_a_count,0);
 const pending=actual.reduce((sum,item)=>sum+item.review_count,0);
 return <div className="mobile-page home-page">
  <div className="home-hello"><span className="eyebrow">INSPECTION WORKSPACE</span><h1>Good {new Date().getHours()<12?'morning':new Date().getHours()<17?'afternoon':'evening'}, Inspector.</h1><p>{date(new Date().toISOString())} · Onion quality inspection</p></div>
  <button className="new-inspection" onClick={onInspect}><span>+ New Inspection<small>Capture or upload onion images</small></span><ArrowRight size={22}/></button>
  <div className="home-section-head"><h2>At a glance</h2><span>{signedIn?'Saved inspections':'Sign in to see your records'}</span></div>
  <div className="overview-grid">
   <div><span>Today’s inspections</span><strong>{today.length}</strong><small>Saved today</small></div>
   <div><span>Onions analyzed</span><strong>{total}</strong><small>Across saved real analyses</small></div>
   <div><span>Grade A</span><strong>{resolved?`${(eligible/resolved*100).toFixed(1)}%`:'—'}</strong><small>{resolved?`${resolved} resolved decisions`:'No resolved decisions'}</small></div>
   <div><span>Needs review</span><strong>{pending}</strong><small>Unresolved findings</small></div>
  </div>
  <section className="home-info"><h3>Evidence before a grade</h3><p>Photograph onions clearly, include a known reference for size, and review uncertain findings before making a procurement decision.</p><button onClick={onHistory}>View inspection history <ArrowRight size={16}/></button></section>
  {history.some(item=>item.demo)&&<p className="demo-note">Demo analyses are excluded from the overview above.</p>}
 </div>;
}

export function OnionsScreen({history,onOpen}:{history:Analysis[];onOpen:(record:Analysis,id:number)=>void}){
 const findings=useMemo(()=>history.flatMap(record=>record.detections.map(detection=>({record,detection}))),[history]);
 const [filter,setFilter]=useState('all');
 const visible=findings.filter(({detection})=>filter==='all'||(filter==='review'?detection.review_required:detection.class===filter));
 const real=findings.filter(({record})=>!record.demo);
 return <div className="mobile-page"><div className="page-block-title"><span className="eyebrow">ONION INSPECTOR</span><h1>Onion findings.</h1><p>Individual findings from saved analyses. Demo findings are marked.</p></div>
  <div className="compact-total"><strong>{real.length}</strong><span>onion regions from real images<small>Automatic instance segmentation is not yet trained.</small></span></div>
  <div className="filter-strip" aria-label="Filter onions">{[['all','All'],['review','Review'],['GOOD','Good'],['DAMAGED','Damaged'],['ROTTEN','Rotten']].map(([value,title])=><button key={value} className={filter===value?'selected':''} onClick={()=>setFilter(value)}>{title}</button>)}</div>
  {!visible.length?<div className="empty-state">No onion findings in this view.</div>:<div className="record-list">{visible.slice(0,100).map(({record,detection}: {record:Analysis;detection:Detection})=><button key={record.id+'-'+detection.id} className="record-card" onClick={()=>onOpen(record,detection.id)}><span className="record-icon">#{detection.id}</span><span className="record-main"><strong>ONI-{String(detection.id).padStart(3,'0')} <small>{record.demo?'DEMO':''}</small></strong><span>{name(detection.health_label||detection.class)} · {detection.diameter_mm===null?'Size unavailable':`${detection.diameter_mm.toFixed(1)} mm · ${detection.size_category||'Uncategorized'}`}</span><small>{date(record.created_at)} · {(detection.confidence*100).toFixed(1)}% confidence</small></span><span className={'record-status '+(detection.review_required?'warn':'')}>{detection.review_required?'Review':'View'}</span></button>)}</div>}
 </div>;
}

export function HistoryScreen({history,onOpen,onInspect,signedIn}:{history:Analysis[];onOpen:(record:Analysis)=>void;onInspect:()=>void;signedIn:boolean}){
 const [query,setQuery]=useState(''),[filter,setFilter]=useState('all');
 const visible=history.filter(item=>(item.id+item.model_version).toLowerCase().includes(query.toLowerCase())&&(filter==='all'||(filter==='review'?item.review_required:!item.review_required)));
 return <div className="mobile-page"><div className="page-block-title"><span className="eyebrow">SAVED INSPECTIONS</span><h1>History.</h1><p>Trace each image analysis back to its evidence and report.</p></div>
  <div className="history-filters"><label><Search size={17}/><input aria-label="Search inspections" placeholder="Search ID or model" value={query} onChange={event=>setQuery(event.target.value)}/></label><select aria-label="Filter history" value={filter} onChange={event=>setFilter(event.target.value)}><option value="all">All statuses</option><option value="review">Needs review</option><option value="complete">Analyzed</option></select></div>
  {!signedIn?<div className="empty-state">Sign in to see your saved inspections.</div>:!visible.length?<div className="empty-state"><ClipboardList size={28}/><strong>No inspections yet</strong><p>Start your first inspection to see results here.</p><button className="primary" onClick={onInspect}>New inspection</button></div>:<div className="record-list">{visible.map(item=><button key={item.id} className="record-card" onClick={()=>onOpen(item)}><span className="record-icon"><CalendarDays size={20}/></span><span className="record-main"><strong>{item.id.slice(0,8).toUpperCase()} {item.demo&&<small>DEMO</small>}</strong><span>{item.total_onions} onion regions · Grade A {percent(item.grade_a_percentage)}</span><small>{date(item.created_at)} · {item.model_version}</small></span><span className={'record-status '+(item.review_required?'warn':'')}>{item.review_required?'Review':'Open'}</span></button>)}</div>}
 </div>;
}

export function ReportsScreen({history,onError,onOpen}:{history:Analysis[];onError:(message:string)=>void;onOpen:(record:Analysis)=>void}){
 const [busy,setBusy]=useState('');
 const getPdf=async(item:Analysis)=>{setBusy(item.id);try{const response=await api(`/report/${item.id}`,{method:'POST'});const metadata=await response.json();download(await(await api(`/report/${item.id}/pdf`)).blob(),`oniongrade-${item.id}.pdf`);return metadata;}catch(error){onError(error instanceof Error?error.message:'Report generation failed.');}finally{setBusy('');}};
 const share=async(item:Analysis)=>{const url=`${location.origin}/api/reports/verify/${item.report_hash}`;try{if(navigator.share)await navigator.share({title:'OnionGrade inspection verification',url});else{await navigator.clipboard.writeText(url);onError('Verification link copied to clipboard.');}}catch(error){if((error as DOMException).name!=='AbortError')onError('Unable to share the verification link.');}};
 return <div className="mobile-page"><div className="page-block-title"><span className="eyebrow">DIGITAL EVIDENCE</span><h1>Reports.</h1><p>Generate a PDF with images, calibration, model version and a verification hash.</p></div>
  {!history.length?<div className="empty-state"><FileText size={28}/><strong>No reports yet</strong><p>Complete an inspection to generate its digital report.</p></div>:<div className="record-list">{history.map(item=><section key={item.id} className="report-card"><div className="report-card-head"><FileText size={22}/><span><strong>{item.id.slice(0,8).toUpperCase()}</strong><small>{date(item.created_at)} · {item.demo?'Demo analysis':'Real image analysis'}</small></span><span className={'record-status '+(item.review_required?'warn':'')}>{item.review_required?'Review':'Analyzed'}</span></div><div className="report-stat"><span>{item.total_onions} onion regions</span><span>Grade A {percent(item.grade_a_percentage)}</span></div><div className="report-actions"><button onClick={()=>onOpen(item)}>View</button><button disabled={busy===item.id} onClick={()=>getPdf(item)}><Download size={15}/>{busy===item.id?'Preparing…':'Download PDF'}</button><button onClick={()=>share(item)}><Share2 size={15}/>Share</button></div></section>)}</div>}
 </div>;
}
