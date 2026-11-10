/* KrakenAI safe Markdown renderer; no HTML injection. */
(()=>{
"use strict";
const t=String.fromCharCode(96);
const inlinePattern=/(\*\*[^*]+\*\*|\u0060[^\u0060]+\u0060|\[[^\]]+\]\(https:\/\/[^\s)]+\))/g;
function inline(parent,value){
  const text=String(value||"");let last=0;
  for(const m of text.matchAll(inlinePattern)){
    if(m.index>last)parent.append(document.createTextNode(text.slice(last,m.index)));
    const v=m[0];let el;
    if(v.startsWith("**")){el=document.createElement("strong");el.textContent=v.slice(2,-2);}
    else if(v.startsWith(t)){el=document.createElement("code");el.textContent=v.slice(1,-1);}
    else{
      el=document.createElement("a");const cut=v.lastIndexOf("](");
      el.textContent=v.slice(1,cut);
      try{const u=new URL(v.slice(cut+2,-1));if(u.protocol==="https:")el.href=u.href;}catch{}
      el.target="_blank";el.rel="noopener noreferrer";
    }
    parent.append(el);last=m.index+v.length;
  }
  if(last<text.length)parent.append(document.createTextNode(text.slice(last)));
}
function code(parent,source,lang){
 const box=document.createElement("div");box.className="md-code-wrap";
 const top=document.createElement("div");top.className="md-code-header";
 const label=document.createElement("span");label.textContent=lang||"Код";
 const button=document.createElement("button");button.type="button";button.textContent="Копировать код";
 button.addEventListener("click",async()=>{
  try{await navigator.clipboard.writeText(source);button.textContent="Скопировано";}
  catch{button.textContent="Недоступно";}
  setTimeout(()=>button.textContent="Копировать код",1500);
 });
 top.append(label,button);
 const pre=document.createElement("pre");const code=document.createElement("code");code.textContent=source;pre.append(code);
 box.append(top,pre);parent.append(box);
}
function render(node,content){
 node.replaceChildren();node.classList.add("md-answer");
 const lines=String(content||"").slice(0,20000).replace(/\r\n?/g,"\n").split("\n");let i=0;
 while(i<lines.length){
  const line=lines[i];if(!line.trim()){i++;continue;}
  if(line.trimStart().startsWith(t.repeat(3))){
   const lang=line.trim().slice(3).replace(/[^a-zA-Z0-9+#-]/g,"").slice(0,24),linesCode=[];i++;
   while(i<lines.length&&!lines[i].trimStart().startsWith(t.repeat(3)))linesCode.push(lines[i++]);
   if(i<lines.length)i++;
   code(node,linesCode.join("\n"),lang);continue;
  }
  const heading=line.match(/^(#{1,3})\s+(.+)/);
  if(heading){
   const h=document.createElement("h"+(heading[1].length+1));inline(h,heading[2]);node.append(h);i++;continue;
  }
  const num=/^\s*\d+\.\s+(.+)/.test(line),bul=/^\s*[-*]\s+(.+)/.test(line);
  if(num||bul){
   const list=document.createElement(num?"ol":"ul"),pattern=num?/^\s*\d+\.\s+(.+)/:/^\s*[-*]\s+(.+)/;
   while(i<lines.length){const item=lines[i].match(pattern);if(!item)break;
    const li=document.createElement("li");inline(li,item[1]);list.append(li);i++;
   }
   node.append(list);continue;
  }
  const paragraph=[];
  while(i<lines.length&&lines[i].trim()&&!/^(#{1,3})\s+|^\s*[-*]\s+|^\s*\d+\.\s+/.test(lines[i])&&!lines[i].trimStart().startsWith(t.repeat(3)))paragraph.push(lines[i++]);
  if(!paragraph.length){i++;continue;}
  const p=document.createElement("p");paragraph.forEach((str,j)=>{if(j)p.append(document.createElement("br"));inline(p,str);});node.append(p);
 }
}
window.KrakenMarkdown={render};
})();