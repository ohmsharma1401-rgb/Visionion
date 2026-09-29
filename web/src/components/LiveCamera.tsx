import {useEffect,useRef,useState} from 'react';
import {Camera,CameraOff,RefreshCcw,RotateCcw,Upload} from 'lucide-react';

type Props={onCapture:(file:File)=>void;onClose:()=>void;onUpload:()=>void};

export function LiveCamera({onCapture,onClose,onUpload}:Props){
 const video=useRef<HTMLVideoElement>(null),stream=useRef<MediaStream|null>(null);
 const [facing,setFacing]=useState<'environment'|'user'>('environment');
 const [revision,setRevision]=useState(0);
 const [state,setState]=useState<'starting'|'ready'|'denied'|'unavailable'|'error'>('starting');
 const [message,setMessage]=useState('Requesting camera permission…');
 const [captured,setCaptured]=useState<File|null>(null);
 const [snapshot,setSnapshot]=useState('');
 useEffect(()=>{
  let active=true;
  setState('starting');setMessage('Requesting camera permission…');
  if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia){
   setState('unavailable');setMessage(window.isSecureContext?'This browser does not support live camera access.':'Live camera requires HTTPS or localhost.');return;
  }
  const request=async(retry=true)=>{
   try{
    const media=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:facing},width:{ideal:1600},height:{ideal:1200}}});
    if(!active){media.getTracks().forEach(track=>track.stop());return;}
    stream.current=media;
    if(video.current){video.current.srcObject=media;video.current.play().catch(()=>setMessage('Tap the preview to start the camera.'));}
    setState('ready');setMessage('Place an onion and the 50 mm marker on the same flat surface. Keep the camera parallel.');
   }catch(unknown){
    const error=unknown as DOMException;
    if(active&&retry&&(error.name==='NotReadableError'||error.name==='AbortError')){
     window.setTimeout(()=>{if(active)request(false);},500);return;
    }
    if(!active)return;
    setState(error.name==='NotAllowedError'||error.name==='PermissionDeniedError'?'denied':'error');
    setMessage(error.name==='NotAllowedError'||error.name==='PermissionDeniedError'?'Camera permission was denied. Enable it in browser settings or upload an image.':`Camera unavailable (${error.name||'stream error'}). Check that another app is not using it, or upload an image.`);
   }
  };
  request();
  return()=>{active=false;stream.current?.getTracks().forEach(track=>track.stop());stream.current=null;};
 },[facing,revision]);
 useEffect(()=>()=>{if(snapshot)URL.revokeObjectURL(snapshot);},[snapshot]);
 const capture=()=>{
  const source=video.current;if(!source?.videoWidth||!source.videoHeight){setMessage('Camera is not ready. Wait for the live preview.');return;}
  const canvas=document.createElement('canvas');canvas.width=source.videoWidth;canvas.height=source.videoHeight;
  canvas.getContext('2d')?.drawImage(source,0,0);
  canvas.toBlob(blob=>{
   if(!blob){setMessage('Capture failed. Please try again.');return;}
   const file=new File([blob],`onion-capture-${Date.now()}.jpg`,{type:'image/jpeg'});
   setCaptured(file);setSnapshot(URL.createObjectURL(file));
   stream.current?.getTracks().forEach(track=>track.stop());stream.current=null;
   setMessage('Review the capture. Nothing is saved until you submit the inspection.');
  },'image/jpeg',0.9);
 };
 return <section className="card live-camera" aria-label="Live camera inspection">
  <div className="section-title"><div><h3>Live camera</h3><p>One steady image, with a reference beside each onion.</p></div><button className="secondary" onClick={onClose}>Close camera</button></div>
  <div className="camera-frame">
   {captured?<img src={snapshot} alt="Captured onion inspection"/>:<video ref={video} playsInline muted autoPlay onClick={()=>video.current?.play()}/>}
   {!captured&&state==='ready'&&<div className="camera-guide" aria-hidden="true"><div className="camera-onion-guide"/><div className="camera-marker-guide">50 mm marker</div></div>}
   {state!=='ready'&&!captured&&<div className="camera-unavailable"><CameraOff size={28}/><span>{message}</span></div>}
  </div>
  <p className="camera-message" role="status">{message}</p>
  <p className="camera-note">Place the printed marker beside the onion, in the same plane. Avoid glare and keep the full onion visible. The camera image stays on this device until you submit it.</p>
  <a className="marker-link" href="/api/calibration/marker.pdf" download="oniongrade-50mm-marker.pdf">Download printable 50 mm marker</a>
  <div className="camera-actions">
   {captured?<><button className="secondary" onClick={()=>{setCaptured(null);setSnapshot('');setRevision(value=>value+1);}}><RotateCcw size={16}/> Retake</button><button className="primary" onClick={()=>{onCapture(captured);onClose();}}>Use this capture</button></>:<><button className="secondary" onClick={()=>setFacing(current=>current==='environment'?'user':'environment')} disabled={state==='starting'}><RefreshCcw size={16}/> Switch camera</button><button className="capture-shutter" aria-label="Capture image" onClick={capture} disabled={state!=='ready'}><Camera size={25}/></button></>}
   <button className="secondary" onClick={()=>{onClose();onUpload();}}><Upload size={16}/> Upload image instead</button>
  </div>
 </section>;
}
