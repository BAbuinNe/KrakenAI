/* KrakenAI animated mascot: built-in SVG asset, no CDN or data collection. */
(() => {
  'use strict';
  const svg = `<defs>
    <radialGradient id="kr-white" cx="28%" cy="16%" r="90%"><stop stop-color="#fff"/><stop offset=".65" stop-color="#fafafa"/><stop offset="1" stop-color="#ddd"/></radialGradient>
    <linearGradient id="kr-red"><stop stop-color="#f65767"/><stop offset="1" stop-color="#b7152c"/></linearGradient>
    <filter id="kr-soft" x="-30%" y="-30%" width="160%" height="180%"><feDropShadow dx="0" dy="4" stdDeviation="3" flood-color="#471528" flood-opacity=".20"/></filter>
   </defs><g class="kr-body" filter="url(#kr-soft)">
   <path class="kr-arm kr-left" d="M53 84C28 59 17 80 24 96S48 90 28 81" stroke="url(#kr-red)" stroke-width="12" fill="none" stroke-linecap="round"/>
   <path class="kr-arm kr-right" d="M108 84C134 62 145 79 139 97S117 88 135 79" stroke="url(#kr-red)" stroke-width="12" fill="none" stroke-linecap="round"/>
   <path class="kr-arm kr-lower" d="M57 99C31 110 38 125 50 129S64 112 55 115" stroke="url(#kr-red)" stroke-width="11" fill="none" stroke-linecap="round"/>
   <path class="kr-arm kr-lower" d="M104 99C130 110 132 126 119 129S99 114 109 115" stroke="url(#kr-red)" stroke-width="11" fill="none" stroke-linecap="round"/>
   <path d="M48 72Q48 21 81 21Q115 21 115 72V100Q115 133 81 133Q48 133 48 100Z" fill="url(#kr-white)" stroke="#dadada"/>
   <path d="M56 62Q59 41 73 32" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round"/>
   <g stroke="#2b2b2b" stroke-linecap="round" fill="none"><path d="M63 83q6-9 12 0M91 83q6-9 12 0" stroke-width="3.5"/><path d="M74 104q8 8 17 0" stroke-width="3.2"/></g>
   <g fill="#efb0b3"><ellipse cx="57" cy="94" rx="4" ry="2.4"/><ellipse cx="108" cy="94" rx="4" ry="2.4"/></g>
   </g>`;
  const style=document.createElement('style');
  style.textContent=`
    .mascot {width:142px!important;height:135px!important;overflow:visible;animation:kr-float 5.5s ease-in-out infinite!important}
    .kr-body{transform-origin:82px 82px;animation:kr-breathe 4.5s ease-in-out infinite}
    .kr-arm{transform-box:fill-box;transform-origin:center center}
    .kr-left{animation:kr-left 4.8s ease-in-out infinite}
    .kr-right{animation:kr-right 4.3s ease-in-out infinite}
    .kr-lower{animation:kr-left 5.8s ease-in-out infinite alternate}
    .kr-thinking .kr-arm{animation-duration:1.5s}
    .kr-success .kr-body{animation:kr-cheer .7s ease-in-out 2}
    .kr-error .kr-body{animation:kr-error .8s ease-in-out 2}
    @keyframes kr-float{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
    @keyframes kr-breathe{0%,100%{transform:scale(1) rotate(-2deg)}50%{transform:scale(1.02,.99) rotate(2deg)}}
    @keyframes kr-left{0%,100%{transform:rotate(-8deg)}50%{transform:rotate(13deg) translateY(-4px)}}
    @keyframes kr-right{0%,100%{transform:rotate(11deg)}50%{transform:rotate(-12deg) translateY(3px)}}
    @keyframes kr-cheer{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-13px) scale(1.07)}}
    @keyframes kr-error{0%,100%{transform:rotate(0)}50%{transform:rotate(-9deg)}}
    @media(max-width:680px){.mascot{width:102px!important;height:100px!important}}
    @media(prefers-reduced-motion:reduce){.mascot,.mascot *{animation:none!important}}
  `;
  document.head.append(style);
  function refresh(){document.querySelectorAll('svg.mascot:not([data-kr-ready])').forEach(n=>{
    n.dataset.krReady='1';n.setAttribute('viewBox','0 0 164 150');n.innerHTML=svg;
  });}
  let timer=0;
  window.KrakenMascot={setMood(mood){refresh();const n=document.querySelector('svg.mascot');if(!n)return;
    n.classList.remove('kr-thinking','kr-success','kr-error');
    if(mood==='thinking')n.classList.add('kr-thinking');
    if(mood==='success'||mood==='error'){n.classList.add(mood==='success'?'kr-success':'kr-error');
      clearTimeout(timer);timer=setTimeout(()=>n.classList.remove('kr-success','kr-error'),1800);}
  }};
  window.addEventListener('kraken:state',e=>window.KrakenMascot.setMood(e.detail?.phase||'idle'));
  function boot(){refresh();const scene=document.getElementById('chatView');if(scene)new MutationObserver(refresh).observe(scene,{childList:true,subtree:true});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();