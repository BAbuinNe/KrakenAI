/* KrakenAI mascot: transparent 60 FPS VP9 WebM; no color-key or browser-side pixel surgery. */
(() => {
  'use strict';
  const IDLE='/static/kraken-idle-smooth-alpha.webm';
  const WAVE='/static/kraken-wave-smooth-alpha.webm';
  const POSTER='/static/kraken-idle-poster.webp';
  const reduce=window.matchMedia('(prefers-reduced-motion: reduce)');
  const instances=new Set();
  let mood='idle';
  function activeMedia(item){
    return {idle:item.querySelector('.kr-video-idle'),wave:item.querySelector('.kr-video-wave')};
  }
  function resume(item){
    item.classList.remove('kr-waving');
    item.dataset.waving='false';
    const {idle,wave}=activeMedia(item);
    if(wave){wave.pause();try{wave.currentTime=0;}catch{}}
    if(idle&&!reduce.matches&&!document.hidden)idle.play().catch(()=>{});
  }
  function playWave(item){
    if(reduce.matches||item.dataset.waving==='true')return;
    const {idle,wave}=activeMedia(item);
    if(!idle||!wave)return;
    item.dataset.waving='true';
    // Both videos are preloaded: don't hide the idle frame until wave playback actually begins.
    const onPlaying=()=>{
      if(!item.isConnected||item.dataset.waving!=='true')return;
      item.classList.add('kr-waving');
      idle.pause();
    };
    wave.addEventListener('playing',onPlaying,{once:true});
    try{wave.currentTime=0;}catch{}
    wave.play().catch(()=>{wave.removeEventListener('playing',onPlaying);resume(item);});
  }
  function mount(){
    document.querySelectorAll('svg.mascot').forEach(svg=>{
      const parent=svg.closest('.mascot-wrap');
      if(!parent||parent.querySelector('.kr-mascot-button'))return;
      parent.removeAttribute('aria-hidden');
      const btn=document.createElement('button');
      btn.type='button';btn.className='kr-mascot-button';
      btn.title='Помахать кракену';btn.setAttribute('aria-label','Помахать кракену');
      btn.dataset.waving='false';
      const poster=document.createElement('img');
      poster.src=POSTER;poster.alt='';poster.className='kr-mascot-poster';
      poster.decoding='async';poster.draggable=false;
      const makeVideo=(cls,src,loop)=>{
        const video=document.createElement('video');
        video.className='kr-mascot-video '+cls;video.src=src;
        video.muted=true;video.defaultMuted=true;video.playsInline=true;
        video.setAttribute('playsinline','');video.setAttribute('aria-hidden','true');
        video.setAttribute('preload','auto');
        video.loop=loop;video.disablePictureInPicture=true;
        video.addEventListener('loadeddata',()=>{if(cls==='kr-video-idle')btn.classList.add('kr-video-ready');});
        return video;
      };
      const idle=makeVideo('kr-video-idle',IDLE,true);
      const wave=makeVideo('kr-video-wave',WAVE,false);
      wave.addEventListener('ended',()=>resume(btn));
      wave.addEventListener('error',()=>resume(btn));
      btn.append(poster,idle,wave);
      btn.addEventListener('click',()=>playWave(btn));
      svg.replaceWith(btn);
      instances.add(btn);
      if(!reduce.matches&&!document.hidden)idle.play().catch(()=>{});
    });
  }
  function pointer(event){
    if(reduce.matches||event.pointerType==='touch')return;
    for(const btn of instances){
      if(!btn.isConnected){instances.delete(btn);continue;}
      const r=btn.getBoundingClientRect();
      const x=(event.clientX-r.left-r.width/2)/190;
      const y=(event.clientY-r.top-r.height/2)/190;
      const p=Math.max(0,1-Math.hypot(x,y));
      btn.style.setProperty('--kr-x',(x*p*6).toFixed(2)+'px');
      btn.style.setProperty('--kr-y',(y*p*4).toFixed(2)+'px');
      btn.style.setProperty('--kr-rotation',(x*p*3.5).toFixed(2)+'deg');
    }
  }
  function neutral(){
    for(const btn of instances){
      btn.style.setProperty('--kr-x','0px');
      btn.style.setProperty('--kr-y','0px');
      btn.style.setProperty('--kr-rotation','0deg');
    }
  }
  function sync(){
    for(const btn of instances){
      if(!btn.isConnected){instances.delete(btn);continue;}
      const {idle,wave}=activeMedia(btn);
      if(reduce.matches||document.hidden){idle?.pause();wave?.pause();if(reduce.matches)resume(btn);}
      else if(btn.dataset.waving==='true')wave?.play().catch(()=>resume(btn));
      else idle?.play().catch(()=>{});
    }
    if(reduce.matches)neutral();
  }
  document.addEventListener('pointermove',pointer,{passive:true});
  document.addEventListener('pointerout',event=>{if(!event.relatedTarget)neutral();});
  document.addEventListener('visibilitychange',sync);
  reduce.addEventListener('change',sync);
  window.addEventListener('kraken:state',event=>{
    mood=event.detail?.phase||'idle';
    for(const btn of instances)btn.classList.toggle('kr-thinking-mode',mood==='thinking');
    if(mood==='success')for(const btn of instances)playWave(btn);
  });
  window.KrakenMascot={
    setMood(phase){mood=phase;for(const btn of instances)btn.classList.toggle('kr-thinking-mode',phase==='thinking');if(phase==='success')for(const btn of instances)playWave(btn);},
    wave(){for(const btn of instances)playWave(btn);}
  };
  function boot(){
    mount();
    const root=document.getElementById('chatView')||document.body;
    new MutationObserver(mount).observe(root,{childList:true,subtree:true});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
  else boot();
})();