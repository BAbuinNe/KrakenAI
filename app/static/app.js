/* KrakenAI browser application — no third-party scripts, no untrusted HTML rendering. */
'use strict';

const $ = id => document.getElementById(id);
const state = {analysisId: null, result: null, busy: false, view: 'chat', history: []};
const safe = value => String(value ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = value => value == null ? 'Не указано' : typeof value === 'number' ? new Intl.NumberFormat('ru-RU',{maximumFractionDigits:3}).format(value) : String(value);
const statuses = {pass:['Соответствует','pass'],fail:['Расхождение','fail'],unknown:['Проверить','unknown']};

async function request(path, options={}) {
  const headers = {'X-Kraken-Request':'1', ...(options.headers||{})};
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type']='application/json';
  let response;
  try { response=await fetch(path,{credentials:'same-origin',cache:'no-store',...options,headers}); }
  catch {throw new Error('Сервер недоступен. Проверьте интернет-соединение.');}
  if (response.status===401 && path!=='/api/login') showAuth();
  if (!response.ok) {
    let detail='Ошибка сервера ('+response.status+')';
    try { detail=(await response.json()).detail||detail; } catch {}
    throw new Error(typeof detail==='string'?detail:'Ошибка обработки запроса');
  }
  return response.json();
}
function showAuth(){ $('authOverlay').hidden=false; }
function hideAuth(){ $('authOverlay').hidden=true; $('authError').textContent=''; $('passwordInput').value=''; }
function setBusy(busy){ window.dispatchEvent(new CustomEvent('kraken:state',{detail:{phase:busy?'thinking':'idle'}})); state.busy=busy; $('sendButton').disabled=busy; $('uploadSubmit').disabled=busy; $('messageInput').disabled=busy; }
function scrollMessages(){ const el=$('messages'); el.scrollTop=el.scrollHeight; }
function closeSidebar(){ $('sidebar').classList.remove('is-open'); $('menuBackdrop').hidden=true; }
function openSidebar(){ $('sidebar').classList.add('is-open'); $('menuBackdrop').hidden=false; }
function setView(view){
  state.view=view;
  $('chatView').hidden=view!=='chat'; $('analysisView').hidden=view!=='analysis'; $('infoView').hidden=view!=='info';
  $('pageName').textContent=view==='chat'?'Kraken AI':view==='analysis'?'Аналитика':'О проекте';
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
  closeSidebar();
}
function appendMessage(role, text, extras=null){
  $('welcome')?.remove();
  const row=document.createElement('div'); row.className='bubble-row '+(role==='user'?'user':'assistant');
  const bubble=document.createElement('div');bubble.className='bubble';
  if(role==='assistant'){const label=document.createElement('span');label.className='bubble-label';label.textContent='KRAKEN';bubble.append(label);}
  const content=document.createElement('span');content.textContent=text;bubble.append(content);
  if(extras){const card=document.createElement('div');card.className='result-inline';
    const left=document.createElement('div');const title=document.createElement('strong');title.textContent=extras.title;
    const subtitle=document.createElement('p');subtitle.textContent=extras.subtitle;
    left.append(title,subtitle);const button=document.createElement('button');button.textContent='Открыть аналитику';
    button.addEventListener('click',()=>{setView('analysis');renderAnalysis();});card.append(left,button);bubble.append(card);
  }
  row.append(bubble);$('messages').append(row);scrollMessages();return content;
}
function resetChat(){
  state.analysisId=null;state.result=null;
  $('messages').replaceChildren();
  const w=document.createElement('section'); w.className='welcome';w.id='welcome';
  w.innerHTML=`<div class="mascot-wrap" aria-hidden="true"><svg class="mascot" viewBox="0 0 160 146" fill="none"><path class="arm arm-left" d="M44 89C18 86 12 105 22 117c10 12 28 0 17-12" stroke="#D1242D" stroke-width="11" stroke-linecap="round"/><path class="arm arm-right" d="M118 89c26-3 32 16 22 28-10 12-28 0-17-12" stroke="#D1242D" stroke-width="11" stroke-linecap="round"/><path d="M39 69C39 43 57 25 81 25s42 18 42 44v23c0 25-18 43-42 43s-42-18-42-43V69Z" fill="#D1242D"/><path d="M53 86c0-3 2-5 5-5s5 2 5 5M99 86c0-3 2-5 5-5s5 2 5 5" stroke="white" stroke-width="4" stroke-linecap="round"/><path d="M72 106c6 7 14 7 20 0" stroke="white" stroke-width="3.4" stroke-linecap="round"/></svg></div><h1>Чем могу помочь?</h1><p>Привет, я Kraken. Помогу сравнить предложения поставщиков и найти важные расхождения.</p><div class="prompts"><button class="prompt-card" id="welcomeUpload"><svg class="prompt-symbol kr-icon" aria-hidden="true"><use href="/static/icons.svg#upload"></use></svg><strong>Анализ предложений</strong><small>Загрузить ТЗ и документы</small></button><button class="prompt-card" data-prompt="Как правильно сравнивать коммерческие предложения?"><svg class="prompt-symbol kr-icon" aria-hidden="true"><use href="/static/icons.svg#compare"></use></svg><strong>Как сравнить?</strong><small>Разобрать критерии выбора</small></button></div>`;
  $('messages').append(w);bindPrompts(); $('composerHint').textContent='Загрузите ТЗ и предложения для анализа';setView('chat');
}
function bindPrompts(){
  $('welcomeUpload')?.addEventListener('click',openUpload);
  document.querySelectorAll('[data-prompt]').forEach(el=>el.addEventListener('click',()=>{ $('messageInput').value=el.dataset.prompt;sendMessage(); }));
}
function openUpload(){ if(state.busy)return; $('uploadFeedback').textContent='';$('uploadModal').hidden=false; $('tzFile').focus();closeSidebar(); }
function closeUpload(){ $('uploadModal').hidden=true; }

let rankingTimer = null;
function locationLabel(locator) {
  if (!locator) return 'место не определено';
  if (locator.kind === 'page') return 'стр. ' + locator.value;
  if (locator.kind === 'sheet') return 'лист ' + locator.value;
  return 'строка ' + locator.value;
}
function rankingMarkup(result, suppliers) {
  const rank = result.ranking;
  if (!rank) return '';
  const names = {compliance:'Соответствие ТЗ',price:'Цена',delivery:'Срок поставки',reliability:'Надёжность'};
  const weightControls = Object.keys(names).map(key =>
    `<label class="ranking-weight"><span>${safe(names[key])}</span><input data-ranking-weight="${key}" type="number" step="5" min="0" max="100" value="${safe(rank.weights?.[key] ?? 0)}" aria-label="Вес: ${safe(names[key])}"></label>`
  ).join('');
  const reliabilityControls = suppliers.map(s => 
    `<label class="reliability-control"><span>${safe(s.name)}</span><input type="number" step="1" min="0" max="100" data-ranking-reliability data-supplier="${safe(s.name)}" aria-label="Ручная оценка надёжности ${safe(s.name)}" placeholder="Нет" value="${safe(rank.reliability?.[s.name] ?? '')}"></label>`
  ).join('');
  const rankingRows = (rank.ranked || []).map((r,i) => {
    const reasons=Object.values(r.components || {}).map(c =>
      `${safe(c.label)}: ${safe(fmt(c.contribution))} б.`).join(' · ');
    return `<tr><td>${i+1}</td><td><strong>${safe(r.supplier)}</strong></td><td><strong>${safe(fmt(r.score))} / 100</strong></td><td><span class="ranking-reasons">${reasons}</span></td></tr>`;
  }).join('');
  const excluded = (rank.excluded || []).map(e =>
    `<li><strong>${safe(e.supplier)}</strong>: ${safe(e.reason)}</li>`).join('');
  const audit = (result.audit_log || []).slice(-3).reverse().map(e =>
    `<li>${safe(new Date(e.at).toLocaleString('ru-RU'))}: веса изменены (${safe(e.actor)}).</li>`).join('');
  return `<section class="data-card ranking-panel" id="rankingPanel">
    <div class="ranking-heading"><div><h2>Рейтинг поставщиков</h2><p>Изменяйте веса — рейтинг пересчитается. Обязательные требования нельзя компенсировать низкой ценой.</p></div><span class="ranking-state" id="rankingStatus" role="status" aria-live="polite"></span></div>
    <div class="ranking-weights">${weightControls}</div>
    <details class="ranking-reliability"><summary>Ручные оценки надёжности</summary><p>Необязательные оценки от 0 до 100, которые вводит специалист. Kraken их не проверяет.</p><div class="reliability-grid">${reliabilityControls}</div></details>
    <div class="table-scroll"><table><thead><tr><th>Место</th><th>Поставщик</th><th>Оценка</th><th>Вклад критериев</th></tr></thead><tbody>${rankingRows || '<tr><td colspan="4">Недостаточно проверенных данных для рейтинга</td></tr>'}</tbody></table></div>
    <p class="ranking-warning">${safe(rank.warning || '')}</p>
    ${rank.unavailable?.length ? `<p class="ranking-warning">Не учтены из-за неполных данных: ${safe(rank.unavailable.join(', '))}.</p>` : ''}
    ${excluded ? `<details class="ranking-excluded"><summary>Не допущены к рейтингу</summary><ul>${excluded}</ul></details>` : ''}
    ${audit ? `<details class="ranking-audit"><summary>Изменения критериев (временный журнал)</summary><ol>${audit}</ol></details>` : ''}
  </section>`;
}
async function applyRanking() {
  if (!state.analysisId) return;
  const panel = $('rankingPanel');
  if (!panel) return;
  const rid = state.analysisId;
  const weights = {};
  const reliability = {};
  for (const input of panel.querySelectorAll('[data-ranking-weight]')) {
    if (input.value === '' || !input.checkValidity()) return;
    weights[input.dataset.rankingWeight] = Number(input.value);
  }
  for (const input of panel.querySelectorAll('[data-ranking-reliability]')) {
    if (input.value !== '') {
      if (!input.checkValidity()) return;
      reliability[input.dataset.supplier] = Number(input.value);
    }
  }
  const indicator = $('rankingStatus');
  if (indicator) indicator.textContent = 'Пересчитываю…';
  try {
    const response = await request('/api/analyses/' + encodeURIComponent(rid) + '/ranking', {
      method:'POST', body:JSON.stringify({weights,reliability})
    });
    if (state.analysisId === rid) {
      state.result = response.result;
      renderAnalysis();
    }
  } catch (error) {
    if (indicator) indicator.textContent = 'Не удалось пересчитать: ' + error.message;
  }
}
function bindRankingControls() {
  const panel = $('rankingPanel');
  if (!panel) return;
  panel.addEventListener('input', event => {
    if (!event.target.matches('[data-ranking-weight], [data-ranking-reliability]')) return;
    clearTimeout(rankingTimer);
    rankingTimer = setTimeout(applyRanking, 550);
  });
}

function badge(check){ const [label,css]=statuses[check?.status]||statuses.unknown;return `<span class="pill ${css}">${label}</span>`;}
function renderAnalysis(){
  const area=$('analysisContent');const result=state.result;
  if(!result){area.innerHTML='<div class="analysis-empty"><svg class="empty-symbol kr-icon" aria-hidden="true"><use href="/static/icons.svg#file-check"></use></svg><h2>Пока нет анализов</h2><p>Загрузите ТЗ и коммерческие предложения, чтобы увидеть сравнительную таблицу.</p><button id="analysisUpload" class="red-button">Загрузить документы</button></div>';
    $('analysisUpload').addEventListener('click',openUpload);return;}
  const suppliers=Array.isArray(result.suppliers)?result.suppliers:[];
  const rows=suppliers.map(s=>`<tr><td><strong>${safe(s.name)}</strong></td><td>${safe(s.passed)}</td><td>${safe(s.failed)}</td><td>${safe(s.unknown)}</td><td>${safe(s.coverage_percent)}%</td></tr>`).join('');
  const details=suppliers.map(s=>`<div class="data-card"><h2>${safe(s.name)}</h2><div class="table-scroll"><table><thead><tr><th>Характеристика</th><th>Требование</th><th>Предложено</th><th>Результат</th></tr></thead><tbody>${(s.checks||[]).map(c=>`<tr><td><strong>${safe(c.parameter)}</strong><div class="source">ТЗ (${safe(locationLabel(c.requirement_locator))}): ${safe(c.requirement_source)}</div></td><td>${safe(c.operator==='min'?'≥ ':c.operator==='max'?'≤ ':'= ')}${safe(fmt(c.required))} ${safe(c.unit)}</td><td>${c.actual==null?'Не найдено':`${safe(fmt(c.actual))} ${safe(c.unit)}`}<div class="source">КП (${safe(locationLabel(c.offer_locator))}): ${safe(c.offer_source||'Нет подтверждающей цитаты')}</div></td><td>${badge(c)}<div class="source">${safe(c.reason)}</div></td></tr>`).join('')}</tbody></table></div></div>`).join('');
  const notes=(result.ai?.observations||[]).map(n=>`<div class="note"><strong>${safe(n.supplier)}</strong> — ${safe(n.finding)}<span>ТЗ: «${safe(n.requirement_quote)}»${n.offer_quote?' · КП: «'+safe(n.offer_quote)+'»':''} · ${safe(n.status)}</span></div>`).join('');
  const url=state.analysisId?'/api/analyses/'+encodeURIComponent(state.analysisId):'';
  area.innerHTML=rankingMarkup(result,suppliers)+`<div class="summary-grid"><div class="metric"><span>Предложений</span><strong>${safe(suppliers.length)}</strong></div><div class="metric"><span>Проверено требований</span><strong>${safe(result.requirements?.length||0)}</strong></div><div class="metric"><span>Предварительный выбор</span><strong class="best">${safe(result.recommended||'Нужна проверка')}</strong></div></div><div class="data-card"><h2>Сводное сравнение</h2><div class="table-scroll"><table><thead><tr><th>Поставщик</th><th>Совпадений</th><th>Расхождений</th><th>Неизвестно</th><th>Покрытие</th></tr></thead><tbody>${rows}</tbody></table></div><p>${safe(result.warning)}</p></div>${details}<div class="data-card"><h2>Смысловые наблюдения AI</h2>${notes?`<div class="notes-list">${notes}</div>`:`<p>${result.ai?.enabled?'Наблюдения не найдены или сервис модели недоступен.':'Модель не подключена. Числовой анализ выполнен по правилам.'}</p>`}<p>Выводы предварительные: решение о закупке принимает специалист.</p></div><div class="download-links"><a href="${url}/pdf">PDF</a><a href="${url}/xlsx">Excel</a><a href="${url}/csv">↓ Скачать CSV</a><a href="${url}/report">↓ JSON</a></div>`;
  bindRankingControls();
}
async function loadHistory(){
  try{const history=await request('/api/analyses');state.history=history;const pane=$('history');pane.replaceChildren();
    if(!history.length){const empty=document.createElement('span');empty.className='history-empty';empty.textContent='Ваши анализы появятся здесь';pane.append(empty);return;}
    for(const r of history){const button=document.createElement('button');button.className='history-item';button.title=r.filenames?.join(' · ');
      button.textContent=(r.filenames||[]).slice(1,2).join('')||'Анализ';button.addEventListener('click',()=>openHistory(r.id));pane.append(button);}
  }catch(e){console.warn('History unavailable:',e.message);}
}
async function openHistory(id){
  try{const result=await request('/api/analyses/'+encodeURIComponent(id));state.analysisId=id;state.result=result;renderAnalysis();setView('analysis');}
  catch(e){appendMessage('assistant',e.message);}
}
async function uploadFiles(event){
  event.preventDefault();if(state.busy)return;
  const tz=$('tzFile').files[0],offers=[...$('offerFiles').files];
  if(!tz||offers.length<1||offers.length>10){$('uploadFeedback').textContent='Нужно ТЗ и от 1 до 10 предложений.';return;}
  if([tz,...offers].some(f=>f.size>5*1024*1024||f.size===0)){ $('uploadFeedback').textContent='Размер каждого файла: от 1 байта до 5 МБ.';return;}
  const fd=new FormData();fd.append('tz',tz);offers.forEach(f=>fd.append('proposals',f));
  $('uploadFeedback').textContent='Документы обрабатываются…';setBusy(true);
  try{const payload=await request('/api/analyses',{method:'POST',body:fd});state.analysisId=payload.id;state.result=payload.result;
    closeUpload();$('uploadForm').reset();$('tzName').textContent='Выбрать файл';$('offerNames').textContent='Выбрать файлы';
    setView('chat');appendMessage('user','Проанализируй техническое задание и '+offers.length+' коммерческих предложения.');
    const r=payload.result;const title=r.recommended?'Предварительно подходит: '+r.recommended:'Анализ завершён: необходима проверка';
    appendMessage('assistant',r.warning,{title,subtitle:`Требований: ${r.requirements.length} · Поставщиков: ${r.suppliers.length}`});
    renderAnalysis();loadHistory();window.dispatchEvent(new CustomEvent('kraken:state',{detail:{phase:'success'}}));$('composerHint').textContent='Задайте вопрос по результатам анализа';
  }catch(e){$('uploadFeedback').textContent=e.message;}
  finally{setBusy(false);}
}
async function sendMessage(){
  if(state.busy)return;const text=$('messageInput').value.trim();if(!text)return;
  $('messageInput').value='';$('messageInput').style.height='';setView('chat');appendMessage('user',text);
  setBusy(true);const placeholder=appendMessage('assistant','Думаю…');
  try{const answer=await request('/api/chat',{method:'POST',body:JSON.stringify({message:text,analysis_id:state.analysisId})});placeholder.textContent=answer.answer;}
  catch(e){placeholder.textContent='Не удалось получить ответ: '+e.message;}
  finally{setBusy(false);$('messageInput').focus();scrollMessages();}
}
function setTheme(theme){document.documentElement.dataset.theme=theme;try{localStorage.setItem('kraken_theme',theme)}catch{}}
function init(){
  try{setTheme(localStorage.getItem('kraken_theme')==='dark'?'dark':'light');}catch{setTheme('light');}
  $('themeButton').addEventListener('click',()=>setTheme(document.documentElement.dataset.theme==='light'?'dark':'light'));
  $('openSidebar').addEventListener('click',openSidebar);$('closeSidebar').addEventListener('click',closeSidebar);$('menuBackdrop').addEventListener('click',closeSidebar);
  document.querySelectorAll('[data-view]').forEach(el=>el.addEventListener('click',()=>{setView(el.dataset.view);if(el.dataset.view==='analysis')renderAnalysis()}));
  $('newChat').addEventListener('click',resetChat);$('panelNewChat').addEventListener('click',resetChat);$('analysisNew').addEventListener('click',openUpload);
  $('uploadButton').addEventListener('click',openUpload);$('closeUpload').addEventListener('click',closeUpload);
  $('uploadModal').addEventListener('click',e=>{if(e.target===$('uploadModal'))closeUpload();});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeUpload();closeSidebar();}});
  $('tzFile').addEventListener('change',()=>{$('tzName').textContent=$('tzFile').files[0]?.name||'Выбрать файл'});
  $('offerFiles').addEventListener('change',()=>{$('offerNames').textContent=[...$('offerFiles').files].map(f=>f.name).join(' · ')||'Выбрать файлы'});
  $('uploadForm').addEventListener('submit',uploadFiles);
  $('sendButton').addEventListener('click',sendMessage);
  $('messageInput').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage()}});
  $('messageInput').addEventListener('input',()=>{const t=$('messageInput');t.style.height='auto';t.style.height=Math.min(t.scrollHeight,150)+'px';});
  $('logout').addEventListener('click',async()=>{try{await request('/api/logout',{method:'POST'})}catch{}showAuth();resetChat();$('history').replaceChildren();});
  $('loginForm').addEventListener('submit',async e=>{e.preventDefault();$('authError').textContent='';
    try{const r=await request('/api/login',{method:'POST',body:JSON.stringify({password:$('passwordInput').value})});hideAuth();resetChat();$('aiStatus').innerHTML='<span class="status-dot"></span> '+(r.ai_enabled?'AI подключён':'Локальная проверка');loadHistory();}
    catch(err){$('authError').textContent=err.message;}
  });
  bindPrompts();request('/api/me').then(r=>{hideAuth();$('aiStatus').innerHTML='<span class="status-dot"></span> '+(r.ai_enabled?'AI подключён':'Локальная проверка');loadHistory();}).catch(showAuth);
}
document.addEventListener('DOMContentLoaded',init);
