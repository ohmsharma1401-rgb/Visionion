const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');

(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const page=await browser.newPage({viewport:{width:390,height:844}});
 await page.addInitScript(()=>{
  Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia:async()=>{
   const canvas=document.createElement('canvas');canvas.width=640;canvas.height=480;
   canvas.getContext('2d').fillStyle='#57833a';canvas.getContext('2d').fillRect(0,0,640,480);
   return canvas.captureStream(5);
  }}});
 });
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('http://127.0.0.1:5173',{waitUntil:'networkidle'});
 await page.getByRole('button',{name:'Use camera'}).click();
 await page.getByRole('button',{name:'Capture image'}).waitFor();
 await page.waitForFunction(()=>document.querySelector('video')?.videoWidth>0);
 await page.getByRole('button',{name:'Capture image'}).click();
 await page.getByRole('button',{name:'Retake',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('video')?.videoWidth>0);
 await page.getByRole('button',{name:'Capture image'}).click();
 await page.getByRole('button',{name:'Use this capture'}).click();
 await page.getByText('onion-capture-', {exact:false}).first().waitFor();
 await page.getByRole('button',{name:'Use camera'}).count();
 await page.screenshot({path:'output/camera-capture-mobile.png',fullPage:true});
 const overflow=await page.evaluate(()=>({scrollWidth:document.documentElement.scrollWidth,innerWidth,wide:[...document.querySelectorAll('*')].filter(el=>el.getBoundingClientRect().right>innerWidth+1).slice(0,8).map(el=>({tag:el.tagName,className:el.className?.baseVal||el.className,right:el.getBoundingClientRect().right}))}));
 if(overflow.scrollWidth>overflow.innerWidth)throw Error('Mobile page overflow: '+JSON.stringify(overflow));
 const denied=await browser.newPage();
 await denied.addInitScript(()=>{
  Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia:async()=>{throw new DOMException('Denied','NotAllowedError');}}});
 });
 await denied.goto('http://127.0.0.1:5173',{waitUntil:'networkidle'});
 await denied.getByRole('button',{name:'Use camera'}).click();
 await denied.getByText('Camera permission was denied.',{exact:false}).first().waitFor();
 await denied.getByRole('button',{name:'Upload image instead'}).click();
 await denied.getByLabel('Upload file').setInputFiles('web/public/demo-calibrated-sample.jpg');
 await denied.getByText('demo-calibrated-sample.jpg',{exact:false}).first().waitFor();
 if(errors.length)throw Error(errors.join('\n'));
 console.log('PASS: live preview, capture, retake, camera upload, mobile layout, denied permission and upload fallback');
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});
