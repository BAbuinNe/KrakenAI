/* Small smiling Kraken: vector motion and mouse proximity, no third-party assets. */
(() => {
'use strict';
const reduce=matchMedia('(prefers-reduced-motion: reduce)');
const arms=[
 [100,121,78,138,64,129,65,110],[101,128,77,159,47,163,47,139],
 [109,133,99,160,82,181,73,169],[140,121,162,138,176,129,175,110],
 [139,128,163,159,193,163,193,139],[131,133,141,160,158,181,167,169]
];
const shape='<svg class="kr-octopus" viewBox="0 0 240 212" aria-hidden="true" focusable="false">'+
 '<g data-kr-pose><g data-kr-arms>'+
 arms.map((a,i)=>{
   const d='M'+a[0]+' '+a[1]+' C'+a[2]+' '+a[3]+' '+a[4]+' '+a[5]+' '+a[6]+' '+a[7];
   return '<path data-kr-arm="'+i+'" class="kr-arm-edge" d="'+d+'"/>'+
     '<path data-kr-arm="'+i+'" class="kr-arm-surface" d="'+d+'"/>';
 }).join('')+
 '</g><path class="kr-head" d="M89 124 C76 108 79 77 86 56 C94 29 107 24 120 24 C145 24 156 45 158 72 C163 101 155 116 150 124 C145 134 132 140 120 139 C105 140 95 135 89 124Z"/>'+
 '<path class="kr-eye" d="M101 88 Q107 79 113 88"/><path class="kr-eye" d="M127 88 Q133 79 139 88"/>'+
 '<path class="kr-smile" d="M113 106 Q120 112 127 106"/></g></svg>';
const clamp=(n,lo,hi)=>Math.max(lo,Math.min(hi,n));
const chars=new Set();
const target={x:0,y:0,p:0};
const current={x:0,y:0,p:0};
let mood='idle',waveUntil=0,frame=0,last=0;
function makePath(a,i,t){
 const s=Math.sin(t*1.5+i*1.6)*2.5;
 const near=current.p;
 const pullX=current.x*near*7, pullY=current.y*near*6;
 const wave=performance.now()<waveUntil && (i===3||i===4)?Math.sin(t*22)*12:0;
 const sign=i<3?1:-1;
 const fix=n=>n.toFixed(2);
 return 'M'+a[0]+' '+a[1]+' C'+fix(a[2]+s*.45)+' '+fix(a[3]+s)+
 ' '+fix(a[4]+pullX*.4*sign+s)+' '+fix(a[5]+pullY*.5+wave*.6)+
 ' '+fix(a[6]+pullX*sign+s)+' '+fix(a[7]+pullY+wave);
}
function render(t){
 for(const key of ['x','y','p'])current[key]+=(target[key]-current[key])*.085;
 for(const button of chars){
  if(!button.isConnected){chars.delete(button);continue;}
  const svg=button.querySelector('[data-kr-pose]');
  if(!svg)continue;
  const float=Math.sin(t*(mood==='thinking'?2.4:1.5))*1.8;
  const lift=performance.now()<waveUntil?-3:0;
  const x=current.x*current.p*3.5, y=current.y*current.p*2+float+lift;
  const tilt=current.x*current.p*4.5+Math.sin(t*.8)*1.1;
  svg.setAttribute('transform','translate('+x.toFixed(2)+' '+y.toFixed(2)+') rotate('+tilt.toFixed(2)+' 120 103)');
  for(let i=0;i<arms.length;i++){
   const path=makePath(arms[i],i,t);
   button.querySelectorAll('[data-kr-arm="'+i+'"]').forEach(el=>el.setAttribute('d',path));
  }
 }
}
function tick(now){
 if(document.hidden||reduce.matches){frame=0;return;}
 if(now-last>30){render(now/1000);last=now;}
 frame=requestAnimationFrame(tick);
}
function sync(){
 cancelAnimationFrame(frame);frame=0;
 if(reduce.matches||document.hidden){
  Object.assign(target,{x:0,y:0,p:0});
  Object.assign(current,{x:0,y:0,p:0});
  render(0);
 }else frame=requestAnimationFrame(tick);
}
function wave(){if(!reduce.matches)waveUntil=performance.now()+760;}
function mount(){
 document.querySelectorAll('svg.mascot').forEach(el=>{
  const holder=el.closest('.mascot-wrap');
  if(!holder||holder.querySelector('.kr-mascot-button'))return;
  holder.removeAttribute('aria-hidden');
  const button=document.createElement('button');
  button.type='button';button.className='kr-mascot-button';
  button.setAttribute('aria-label','Помахать кракену');
  button.title='Поприветствовать кракена';
  button.innerHTML=shape;
  button.addEventListener('click',wave);
  el.replaceWith(button);
  chars.add(button);
  render(reduce.matches?0:performance.now()/1000);
 });
}
function pointer(event){
 if(reduce.matches||event.pointerType==='touch')return;
 let best=null,d=Infinity;
 for(const button of chars){
  const r=button.getBoundingClientRect();
  if(!r.width)return;
  const cx=r.left+r.width/2,cy=r.top+r.height/2;
  const distance=Math.hypot(event.clientX-cx,event.clientY-cy);
  if(distance<d){d=distance;best={cx,cy,w:r.width};}
 }
 if(!best){target.p=0;return;}
 const radius=Math.max(165,best.w*1.4);
 target.p=clamp(1-d/radius,0,1);
 target.x=clamp((event.clientX-best.cx)/(radius*.7),-1,1);
 target.y=clamp((event.clientY-best.cy)/(radius*.7),-1,1);
}
document.addEventListener('pointermove',pointer,{passive:true});
document.addEventListener('pointerout',e=>{if(!e.relatedTarget)target.p=0;});
document.addEventListener('visibilitychange',sync);
reduce.addEventListener('change',sync);
window.addEventListener('kraken:state',event=>{
 mood=['idle','thinking','success','error'].includes(event.detail?.phase)?event.detail.phase:'idle';
 if(mood==='success')wave();
});
window.KrakenMascot={setMood(next){mood=next;if(next==='success')wave();},wave};
function boot(){
 mount();
 const root=document.getElementById('chatView')||document.body;
 new MutationObserver(mount).observe(root,{childList:true,subtree:true});
 sync();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
else boot();
})();