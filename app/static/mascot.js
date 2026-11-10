/* Kraken mascot: original video clips from approved white/red character. */
(() => {
  'use strict';
  const idle = "data:video/mp4;base64,AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAQybW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAC7gAAQAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAA110cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAAC7gAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAPAAAADwAAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAAAu4AAAQAAABAAAAAALVbWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAABAAAAAwABVxAAAAAAALWhkbHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAACgG1pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAAkBzdGJsAAAAsHN0c2QAAAAAAAAAAQAAAKBhdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAPAA8ABIAAAASAAAAAAAAAABFUxhdmM2MS4xOS4xMDEgbGlieDI2NAAAAAAAAAAAAAAAGP//AAAANmF2Y0MBZAAV/+EAGGdkABWscgRDx+hAAAADAEAAAAQDxYthGAEAB2joQ4dLIsD9+PgAAAAAFGJ0cnQAAAAAAAAyAgAAAAAAAAAYc3R0cwAAAAAAAAABAAAAGAAACAAAAAAUc3RzcwAAAAAAAAABAAAAAQAAALhjdHRzAAAAAAAAABUAAAABAAAQAAAAAAEAACgAAAAAAQAAEAAAAAABAAAAAAAAAAEAAAgAAAAAAQAAGAAAAAABAAAIAAAAAAEAACgAAAAAAQAAEAAAAAABAAAAAAAAAAEAAAgAAAAAAQAAIAAAAAACAAAIAAAAAAEAADgAAAAAAQAAGAAAAAACAAAAAAAAAAIAAAgAAAAAAQAAKAAAAAABAAAQAAAAAAEAAAAAAAAAAQAACAAAAAAcc3RzYwAAAAAAAAABAAAAAQAAABgAAAABAAAAdHN0c3oAAAAAAAAAAAAAABgAAAl5AAAAxgAAADwAAAAyAAAAKgAAAMgAAAAxAAABAAAAAFkAAABAAAAAOgAAAMUAAABMAAAANgAAAM0AAACBAAAAQAAAADoAAAA8AAAARAAAAIsAAAB2AAAARgAAAEgAAAAUc3RjbwAAAAAAAAABAAAEYgAAAGF1ZHRhAAAAWW1ldGEAAAAAAAAAIWhkbHIAAAAAAAAAAG1kaXJhcHBsAAAAAAAAAAAAAAAALGlsc3QAAAAkqXRvbwAAABxkYXRhAAAAAQAAAABMYXZmNjEuNy4xMDMAAAAIZnJlZQAAEsltZGF0AAACrwYF//+r3EXpvebZSLeWLNgg2SPu73gyNjQgLSBjb3JlIDE2NCByMzEwOCAzMWUxOWY5IC0gSC4yNjQvTVBFRy00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIwMDMtMjAyMyAtIGh0dHA6Ly93d3cudmlkZW9sYW4ub3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTEgcmVmPTE2IGRlYmxvY2s9MTowOjAgYW5hbHlzZT0weDM6MHgxMzMgbWU9dW1oIHN1Ym1lPTEwIHBzeT0xIHBzeV9yZD0xLjAwOjAuMDAgbWl4ZWRfcmVmPTEgbWVfcmFuZ2U9MjQgY2hyb21hX21lPTEgdHJlbGxpcz0yIDh4OGRjdD0xIGNxbT0wIGRlYWR6b25lPTIxLDExIGZhc3RfcHNraXA9MSBjaHJvbWFfcXBfb2Zmc2V0PS0yIHRocmVhZHM9NyBsb29rYWhlYWRfdGhyZWFkcz0xIHNsaWNlZF90aHJlYWRzPTAgbnI9MCBkZWNpbWF0ZT0xIGludGVybGFjZWQ9MCBibHVyYXlfY29tcGF0PTAgY29uc3RyYWluZWRfaW50cmE9MCBiZnJhbWVzPTggYl9weXJhbWlkPTIgYl9hZGFwdD0yIGJfYmlhcz0wIGRpcmVjdD0zIHdlaWdodGI9MSBvcGVuX2dvcD0wIHdlaWdodHA9MiBrZXlpbnQ9MjUwIGtleWludF9taW49OCBzY2VuZWN1dD00MCBpbnRyYV9yZWZyZXNoPTAgcmNfbG9va2FoZWFkPTYwIHJjPWNyZiBtYnRyZWU9MSBjcmY9MzMuMCBxY29tcD0wLjYwIHFwbWluPTAgcXBtYXg9NjkgcXBzdGVwPTQgaXBfcmF0aW89MS40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";
  const waveClip = "data:video/mp4;base64,AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAQybW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAC7gAAQAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAA110cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAAC7gAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAPAAAADwAAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAAAu4AAAQAAABAAAAAALVbWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAABAAAAAwABVxAAAAAAALWhkbHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAACgG1pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAAkBzdGJsAAAAsHN0c2QAAAAAAAAAAQAAAKBhdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAPAA8ABIAAAASAAAAAAAAAABFUxhdmM2MS4xOS4xMDEgbGlieDI2NAAAAAAAAAAAAAAAGP//AAAANmF2Y0MBZAAV/+EAGGdkABWscgRDx+hAAAADAEAAAAQDxYthGAEAB2joQ4dLIsD9+PgAAAAAFGJ0cnQAAAAAAABO4gAAAAAAAAAYc3R0cwAAAAAAAAABAAAAGAAACAAAAAAUc3RzcwAAAAAAAAABAAAAAQAAALhjdHRzAAAAAAAAABUAAAABAAAQAAAAAAEAACgAAAAAAQAAEAAAAAABAAAAAAAAAAEAAAgAAAAAAQAAIAAAAAACAAAIAAAAAAEAADAAAAAAAQAAEAAAAAABAAAAAAAAAAIAAAgAAAAAAQAAKAAAAAABAAAQAAAAAAEAAAAAAAAAAQAACAAAAAABAAAgAAAAAAIAAAgAAAAAAQAAKAAAAAABAAAQAAAAAAEAAAAAAAAAAQAACAAAAAAcc3RzYwAAAAAAAAABAAAAAQAAABgAAAABAAAAdHN0c3oAAAAAAAAAAAAAABgAAAktAAAAlQAAADIAAAA8AAAALwAAAJkAAAAnAAAAIwAAAoEAAABnAAAAUgAAALcAAACOAAAF1AAAAaMAAAFIAAABAgAAAXcAAABuAAAAPwAAANYAAACNAAAARQAAAEcAAAAUc3RjbwAAAAAAAAABAAAEYgAAAGF1ZHRhAAAAWW1ldGEAAAAAAAAAIWhkbHIAAAAAAAAAAG1kaXJhcHBsAAAAAAAAAAAAAAAALGlsc3QAAAAkqXRvbwAAABxkYXRhAAAAAQAAAABMYXZmNjEuNy4xMDMAAAAIZnJlZQAAHZ1tZGF0AAACrwYF//+r3EXpvebZSLeWLNgg2SPu73gyNjQgLSBjb3JlIDE2NCByMzEwOCAzMWUxOWY5IC0gSC4yNjQvTVBFRy00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIwMDMtMjAyMyAtIGh0dHA6Ly93d3cudmlkZW9sYW4ub3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTEgcmVmPTE2IGRlYmxvY2s9MTowOjAgYW5hbHlzZT0weDM6MHgxMzMgbWU9dW1oIHN1Ym1lPTEwIHBzeT0xIHBzeV9yZD0xLjAwOjAuMDAgbWl4ZWRfcmVmPTEgbWVfcmFuZ2U9MjQgY2hyb21hX21lPTEgdHJlbGxpcz0yIDh4OGRjdD0xIGNxbT0wIGRlYWR6b25lPTIxLDExIGZhc3RfcHNraXA9MSBjaHJvbWFfcXBfb2Zmc2V0PS0yIHRocmVhZHM9NyBsb29rYWhlYWRfdGhyZWFkcz0xIHNsaWNlZF90aHJlYWRzPTAgbnI9MCBkZWNpbWF0ZT0xIGludGVybGFjZWQ9MCBibHVyYXlfY29tcGF0PTAgY29uc3RyYWluZWRfaW50cmE9MCBiZnJhbWVzPTggYl9weXJhbWlkPTIgYl9hZGFwdD0yIGJfYmlhcz0wIGRpcmVjdD0zIHdlaWdodGI9MSBvcGVuX2dvcD0wIHdlaWdodHA9MiBrZXlpbnQ9MjUwIGtleWludF9taW49OCBzY2VuZWN1dD00MCBpbnRyYV9yZWZyZXNoPTAgcmNfbG9va2FoZWFkPTYwIHJjPWNyZiBtYnRyZWU9MSBjcmY9MzMuMCBxY29tcD0wLjYwIHFwbWluPTAgcXBtYXg9NjkgcXBzdGVwPTQgaXBfcmF0aW89MS40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";

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const instances = new Set();
  const size = 240;
  let mood = 'idle';
  let frame = 0, lastDraw = 0;
  // Video is drawn through Canvas so the *outer* white matte is transparent.
  // Flood-filling only from the edges preserves the character's white face/body.
  function eraseWhiteMatte(ctx) {
    const im = ctx.getImageData(0, 0, size, size);
    const d = im.data;
    const N = size*size, visited = new Uint8Array(N);
    const queue = new Int32Array(N);
    const bg=[d[0],d[1],d[2]];
    let head=0,tail=0;
    const nearWhite = i => {
      const k=i*4;
      return Math.abs(d[k]-bg[0])<19 && Math.abs(d[k+1]-bg[1])<19 &&
             Math.abs(d[k+2]-bg[2])<19 && d[k]>226 && d[k+1]>226 && d[k+2]>226;
    };
    function add(i) {
      if (!visited[i] && nearWhite(i)) {visited[i]=1;queue[tail++]=i;}
    }
    for(let x=0;x<size;x++){add(x);add((size-1)*size+x);}
    for(let y=0;y<size;y++){add(y*size);add(y*size+size-1);}
    while(head<tail) {
      const i=queue[head++],x=i%size,y=(i-x)/size;
      if(x>0)add(i-1);
      if(x<size-1)add(i+1);
      if(y>0)add(i-size);
      if(y<size-1)add(i+size);
    }
    for(let j=0;j<tail;j++)d[queue[j]*4+3]=0;
    // Feather one antialiased boundary pixel to reduce white fringing.
    for(let j=0;j<tail;j++){
      const i=queue[j],x=i%size,y=(i-x)/size;
      for(const n of [x>0?i-1:-1,x<size-1?i+1:-1,y>0?i-size:-1,y<size-1?i+size:-1]){
        if(n<0||visited[n])continue;
        const k=n*4,brightness=Math.min(d[k],d[k+1],d[k+2]);
        if(brightness>221)d[k+3]=Math.min(d[k+3],Math.round(255*(245-brightness)/24));
      }
    }
    ctx.putImageData(im,0,0);
  }
  function draw(item){
    const video=item.querySelector('video');
    const canvas=item.querySelector('canvas');
    if(!video || !canvas || video.readyState<2 || !video.videoWidth)return;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    if(!ctx)return;
    ctx.clearRect(0,0,size,size);
    ctx.drawImage(video,0,0,size,size);
    try{eraseWhiteMatte(ctx);}catch(e){console.warn('Kraken matte unavailable',e);}
    canvas.classList.add('kr-ready');
    item.classList.add('kr-has-frame');
    item.querySelector('svg.mascot')?.setAttribute('aria-hidden','true');
  }
  function frameLoop(time){
    frame=requestAnimationFrame(frameLoop);
    if(document.hidden||time-lastDraw<42)return; // capped at ~24 fps
    lastDraw=time;
    for(const item of instances){
      if(!item.isConnected){instances.delete(item);continue;}
      draw(item);
    }
  }
  function reset(item){
    const v=item.querySelector('video');if(!v)return;
    item.dataset.playing='false';
    v.pause();v.loop=true;v.src=idle;v.load();
    if(!reduce.matches && !document.hidden)v.play().catch(()=>{});
  }
  function wave(item){
    if(reduce.matches||item.dataset.playing==='true')return;
    const v=item.querySelector('video');if(!v)return;
    item.dataset.playing='true';v.pause();v.loop=false;
    v.src=waveClip;v.load();v.currentTime=0;
    v.play().catch(()=>reset(item));
  }
  function mount(){
    document.querySelectorAll('svg.mascot').forEach(svg=>{
      const parent=svg.closest('.mascot-wrap');
      if(!parent||parent.querySelector('.kr-mascot-button'))return;
      parent.removeAttribute('aria-hidden');
      const btn=document.createElement('button');
      btn.type='button';btn.className='kr-mascot-button';
      btn.setAttribute('aria-label','Помахать кракену');
      btn.title='Помахать кракену';
      btn.dataset.playing='false';
      svg.classList.add('kr-mascot-fallback');
      const canvas=document.createElement('canvas');
      canvas.width=size;canvas.height=size;
      canvas.className='kr-mascot-transparency';
      canvas.setAttribute('aria-hidden','true');
      const video=document.createElement('video');
      video.className='kr-video-source';
      video.muted=true;video.defaultMuted=true;video.playsInline=true;
      video.autoplay=true;video.loop=true;video.preload='auto';
      video.setAttribute('aria-hidden','true');
      video.src=idle;
      video.addEventListener('loadeddata',()=>draw(btn));
      video.addEventListener('ended',()=>reset(btn));
      btn.append(svg,canvas,video);
      parent.append(btn);
      instances.add(btn);
      btn.addEventListener('click',()=>wave(btn));
      if(reduce.matches){video.pause();}else video.play().catch(()=>{});
    });
  }
  function pointer(e){
    if(reduce.matches||e.pointerType==='touch')return;
    for(const btn of instances){
      if(!btn.isConnected){instances.delete(btn);continue;}
      const rect=btn.getBoundingClientRect();
      const x=(e.clientX-rect.left-rect.width/2)/190;
      const y=(e.clientY-rect.top-rect.height/2)/190;
      const distance=Math.hypot(x,y),weight=Math.max(0,1-distance);
      btn.style.setProperty('--kr-x',(x*weight*6).toFixed(2)+'px');
      btn.style.setProperty('--kr-y',(y*weight*4).toFixed(2)+'px');
      btn.style.setProperty('--kr-rotation',(x*weight*4).toFixed(2)+'deg');
    }
  }
  function neutral(){
    for(const btn of instances){
      btn.style.setProperty('--kr-x','0px');
      btn.style.setProperty('--kr-y','0px');
      btn.style.setProperty('--kr-rotation','0deg');
    }
  }
  function syncMotion(){
    for(const btn of instances){
      const video=btn.querySelector('video');if(!video)continue;
      if(reduce.matches||document.hidden){video.pause();if(reduce.matches)video.currentTime=0;}
      else video.play().catch(()=>{});
      if(reduce.matches)draw(btn);
    }
    if(reduce.matches)neutral();
  }
  document.addEventListener('pointermove',pointer,{passive:true});
  document.addEventListener('pointerout',e=>{if(!e.relatedTarget)neutral();});
  document.addEventListener('visibilitychange',syncMotion);
  reduce.addEventListener('change',syncMotion);
  window.addEventListener('kraken:state',e=>{
    mood=e.detail?.phase||'idle';
    if(mood==='success')for(const btn of instances)wave(btn);
  });
  window.KrakenMascot={
    setMood(phase){mood=phase;if(phase==='success')for(const btn of instances)wave(btn);},
    wave(){for(const btn of instances)wave(btn)}
  };
  function boot(){
    mount();
    const root=document.getElementById('chatView')||document.body;
    new MutationObserver(mount).observe(root,{childList:true,subtree:true});
    if(!frame)frame=requestAnimationFrame(frameLoop);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
  else boot();
})();
