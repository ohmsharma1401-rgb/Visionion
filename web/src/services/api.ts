export async function api(path:string,options:RequestInit={}){
 const response=await fetch('/api'+path,{...options,headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(sessionStorage.getItem('token')?{Authorization:`Bearer ${sessionStorage.getItem('token')}`} : {}),...options.headers}});
 if(!response.ok){let detail;try{detail=(await response.json()).detail;}catch{detail='The server is unavailable.';}if(response.status===401)sessionStorage.removeItem('token');throw Error(typeof detail==='string'?detail:detail?.reasons?.join(' ')||JSON.stringify(detail));}
 return response;
}
export function download(blob:Blob,name:string){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
export async function imageUrl(path:string){return URL.createObjectURL(await(await api(path.replace(/^\/api/,''))).blob());}
