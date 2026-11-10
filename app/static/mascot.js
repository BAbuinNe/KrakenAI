/* KrakenAI friendly octopus canvas animation. No network requests or tracking. */
(()=>{
'use strict';
const motion=window.matchMedia('(prefers-reduced-motion: reduce)');
let mood='idle',start=performance.now(),frameId=0;
function arm(c,points,width){
 c.beginPath();c.moveTo(...points[0]);c.bezierCurveTo(...points[1],...points[2],...points[3]);
 c.lineCap='round';c.lineJoin='round';c.lineWidth=width+5;c.strokeStyle='#9d162c';c.stroke();
 c.lineWidth=width;c.strokeStyle='#e12d43';c.stroke();
}
function draw(canvas,t){
 const c=canvas.getContext('2d');if(!c)return;c.clearRect(0,0,420,420);c.save();
 const a=Math.sin(t*(mood==='thinking'?3:1.8)),b=Math.cos(t*1.3);
 c.translate(210,202+Math.sin(t*1.5)*6-(mood==='success'?8:0));
 c.rotate(Math.sin(t*.7)*.025+(mood==='error'?-.08:0));
 c.shadowColor='rgba(26,14,23,.12)';c.shadowBlur=14;c.shadowOffsetY=6;
 arm(c,[[-53,26],[-132,-45-12*a],[-166,83+15*b],[-92,80+8*a]],18);
 arm(c,[[53,26],[126,-35-8*b],[154,91+12*a],[92,78+7*b]],18);
 arm(c,[[-38,72],[-114,118+13*a],[-74,154+8*b],[-45,128]],16);
 arm(c,[[38,72],[110,122-15*a],[70,160+5*b],[45,130]],16);
 arm(c,[[-15,94],[-58,153],[-8,166+12*a],[-2,130]],14);
 arm(c,[[15,94],[57,152],[8,168-10*b],[-2,130]],14);
 c.shadowBlur=0;c.shadowOffsetY=0;
 c.fillStyle='#f9f9f9';c.strokeStyle='#ddd';c.lineWidth=3;
 c.beginPath();c.moveTo(-71,26);c.bezierCurveTo(-80,-63,-52,-116,0,-120);c.bezierCurveTo(52,-116,80,-65,71,26);c.bezierCurveTo(71,110,36,133,0,130);c.bezierCurveTo(-36,133,-71,108,-71,26);c.closePath();c.fill();c.stroke();
 c.strokeStyle='#fff';c.lineWidth=10;c.lineCap='round';c.beginPath();c.moveTo(-50,-58);c.quadraticCurveTo(-42,-95,-28,-100);c.stroke();
 c.fillStyle='#fff';c.beginPath();c.ellipse(-35,41,14,8,0,0,Math.PI*2);c.ellipse(35,41,14,8,0,0,Math.PI*2);c.fill();
 c.strokeStyle='#333';c.lineWidth=5;c.beginPath();const blink=Math.sin(t*1.8)>.995;
 c.moveTo(-30,3);c.quadraticCurveTo(-18,blink?3:-14,-7,3);c.moveTo(7,3);c.quadraticCurveTo(18,blink?3:-14,30,3);c.stroke();
 c.lineWidth=4;c.beginPath();c.moveTo(-13,34);c.quadraticCurveTo(0,mood==='success'?60:53,13,34);c.stroke();c.restore();
}
function mount(){
 document.querySelectorAll('svg.mascot').forEach(svg=>{
  const parent=svg.parentElement;if(!parent||parent.querySelector('.kr-mascot-live'))return;
  const c=document.createElement('canvas');c.width=420;c.height=420;c.className='kr-mascot-live';
  c.setAttribute('aria-hidden','true');svg.replaceWith(c);draw(c,0);
 });
}
function loop(now){
 if(!document.hidden){const t=motion.matches?0:(now-start)/1000;
  document.querySelectorAll('canvas.kr-mascot-live').forEach(c=>draw(c,t));}
 if(!motion.matches)frameId=requestAnimationFrame(loop);
}
function restart(){cancelAnimationFrame(frameId);start=performance.now();
 if(motion.matches)document.querySelectorAll('canvas.kr-mascot-live').forEach(c=>draw(c,0));
 else frameId=requestAnimationFrame(loop);}
window.KrakenMascot={setMood(next){mood=['idle','thinking','success','error'].includes(next)?next:'idle';restart();}};
window.addEventListener('kraken:state',e=>window.KrakenMascot.setMood(e.detail?.phase));
motion.addEventListener('change',restart);
document.addEventListener('visibilitychange',()=>{if(document.hidden)cancelAnimationFrame(frameId);else restart();});
function boot(){mount();const root=document.getElementById('chatView')||document.body;
 new MutationObserver(mount).observe(root,{childList:true,subtree:true});restart();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();