const input=document.getElementById('video'), zone=document.getElementById('dropzone');
const title=document.getElementById('fileTitle'), hint=document.getElementById('fileHint');
const form=document.getElementById('clipForm'), btn=document.getElementById('submitBtn');
const progress=document.getElementById('progressWrap'), status=document.getElementById('status');
const errorBox=document.getElementById('error'), results=document.getElementById('results');
input.addEventListener('change',()=>{if(input.files[0]){title.textContent=input.files[0].name;hint.textContent=(input.files[0].size/1024/1024).toFixed(1)+' MB · Ready to clip';}});
['dragenter','dragover'].forEach(e=>zone.addEventListener(e,x=>{x.preventDefault();zone.classList.add('over')}));
['dragleave','drop'].forEach(e=>zone.addEventListener(e,x=>{x.preventDefault();zone.classList.remove('over')}));
zone.addEventListener('drop',e=>{if(e.dataTransfer.files.length){input.files=e.dataTransfer.files;input.dispatchEvent(new Event('change'));}});
form.addEventListener('submit',async e=>{
 e.preventDefault(); errorBox.hidden=true; results.hidden=true;
 if(!input.files.length){errorBox.textContent='Choose a video before starting.';errorBox.hidden=false;return;}
 const data=new FormData();data.append('video',input.files[0]);
 btn.disabled=true;progress.hidden=false;status.textContent='Transcribing audio and finding highlights…';
 try{
  const response=await fetch('/api/clip',{method:'POST',body:data});
  const payload=await response.json();
  if(!response.ok)throw new Error(payload.error||'Something went wrong.');
  const list=document.getElementById('clipList');list.innerHTML='';
  payload.clips.forEach((clip,i)=>{
   const el=document.createElement('article');el.className='clip';
   const num=document.createElement('div');num.className='clip-number';num.textContent=String(i+1).padStart(2,'0');
   const info=document.createElement('div');info.className='clip-info';
   const name=document.createElement('b');name.textContent=clip.name+' · '+clip.duration+' sec';
   const desc=document.createElement('p');desc.textContent=clip.caption;
   info.append(name,desc);
   const link=document.createElement('a');link.className='download';link.href='/outputs/'+encodeURIComponent(clip.file);link.textContent='↓ Download';
   el.append(num,info,link);list.append(el);
  });
  document.getElementById('resultCount').textContent=payload.clips.length+' clips';
  results.hidden=false;status.textContent='Finished!';
 }catch(err){errorBox.textContent=err.message;errorBox.hidden=false;}
 finally{btn.disabled=false;progress.hidden=true;}
});
