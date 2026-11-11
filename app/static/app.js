/* KrakenAI browser application — no third-party scripts, no untrusted HTML rendering. */
'use strict';

const $ = id => document.getElementById(id);
const state = {allConversations: [], analysisId: null, result: null, busy: false, view: 'chat', history: [], conversationId: null, streamController: null};
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
  const content=document.createElement('div');content.className='message-text';content.textContent=text;
  if(role==='assistant'){content.dataset.raw=text;window.KrakenMarkdown?.render(content,text);}
  bubble.append(content);
  if(extras){const card=document.createElement('div');card.className='result-inline';
    const left=document.createElement('div');const title=document.createElement('strong');title.textContent=extras.title;
    const subtitle=document.createElement('p');subtitle.textContent=extras.subtitle;
    left.append(title,subtitle);const button=document.createElement('button');button.textContent='Открыть аналитику';
    button.addEventListener('click',()=>{setView('analysis');renderAnalysis();});card.append(left,button);bubble.append(card);
  }
  row.append(bubble);$('messages').append(row);scrollMessages();return content;
}
function showFirstVisitGuide(){
  const welcome=$('welcome');
  if(!welcome||$('krWelcomeGuide'))return;
  try{if(localStorage.getItem('kraken_welcome_guide_v2')==='1')return;}catch{}
  const guide=document.createElement('div');
  guide.id='krWelcomeGuide';
  guide.className='kr-guide';
  guide.setAttribute('aria-label','Краткая инструкция');
  guide.innerHTML='<div class="kr-guide-title"><strong>Как работает KrakenAI</strong><button type="button" class="kr-guide-close" aria-label="Закрыть инструкцию" id="krCloseGuide">×</button></div>'+
    '<div class="kr-guide-steps"><div><b>01</b><span>Загрузите ТЗ и предложения</span></div>'+
    '<div><b>02</b><span>Проверьте таблицу и источники</span></div>'+
    '<div><b>03</b><span>Спросите Kraken о расхождениях</span></div></div>'+
    '<p>Выводы предварительные: Kraken не заменяет проверку специалистом.</p>';
  welcome.insertBefore(guide,welcome.querySelector('.prompts'));
  guide.querySelector('#krCloseGuide').addEventListener('click',()=>{
    guide.remove();
    try{localStorage.setItem('kraken_welcome_guide_v2','1');}catch{}
  });
}
function renderAnalysisQuestions(){
  const container=$('analysisQuestions');
  if(!container||!state.analysisId)return;
  container.replaceChildren();
  const q=['Почему выбранный поставщик подходит или не подходит?',
           'Какие требования ТЗ остались неподтверждёнными?',
           'Какие вопросы стоит направить поставщикам?'];
  for(const question of q){
    const b=document.createElement('button');
    b.type='button';b.className='kr-question';
    b.textContent=question;
    b.addEventListener('click',()=>streamConversation(question));
    container.append(b);
  }
}
function resetChat(){
  state.analysisId=null;state.result=null;state.conversationId=null;
  $('messages').replaceChildren();
  const w=document.createElement('section'); w.className='welcome';w.id='welcome';
  w.innerHTML=`<div class="mascot-wrap"><svg class="mascot" viewBox="0 0 240 212" fill="none" aria-hidden="true"><path d="M101 126 C65 165 43 146 65 110 M139 126 C175 165 197 146 175 110 M114 139 C92 173 77 178 73 169 M126 139 C148 173 163 178 167 169" stroke="#e5293e" stroke-width="8" stroke-linecap="round"/><path d="M89 124 C76 108 79 77 86 56 C94 29 107 24 120 24 C145 24 156 45 158 72 C163 101 155 116 150 124 C145 134 132 140 120 139 C105 140 95 135 89 124Z" fill="#fffafa" stroke="#f0eded" stroke-width="1.4"/><path d="M101 88Q107 79 113 88 M127 88Q133 79 139 88 M113 106Q120 112 127 106" stroke="#262626" stroke-width="3.5" stroke-linecap="round"/></svg></div><h1>Чем могу помочь?</h1><p>Привет, я Kraken. Помогу сравнить предложения поставщиков и найти важные расхождения.</p><div class="prompts"><button class="prompt-card" id="welcomeUpload"><svg class="prompt-symbol kr-icon" aria-hidden="true"><use href="/static/icons.svg#upload"></use></svg><strong>Анализ предложений</strong><small>Загрузить ТЗ и документы</small></button><button class="prompt-card" data-prompt="Как правильно сравнивать коммерческие предложения?"><svg class="prompt-symbol kr-icon" aria-hidden="true"><use href="/static/icons.svg#compare"></use></svg><strong>Как сравнить?</strong><small>Разобрать критерии выбора</small></button></div>`;
  $('messages').append(w);bindPrompts();showFirstVisitGuide(); $('composerHint').textContent='Загрузите ТЗ и предложения для анализа';setView('chat');
}
function bindPrompts(){
  $('welcomeUpload')?.addEventListener('click',openUpload);
  document.querySelectorAll('[data-prompt]').forEach(el=>el.addEventListener('click',()=>{ $('messageInput').value=el.dataset.prompt;sendMessage(); }));
}
const selectedOffers=[];
function fileKey(file){return [file.name,file.size,file.lastModified].join('::');}
function refreshOfferList(){
  const list=$('offerList');if(!list)return;
  list.replaceChildren();
  $('offerCounter').textContent=selectedOffers.length+' / 10';
  $('offerNames').textContent=selectedOffers.length>=10?'Достигнут лимит (10)':'+ Добавить ещё КП';
  $('offerFiles').disabled=state.busy||selectedOffers.length>=10;
  if(!selectedOffers.length){
    const empty=document.createElement('p');empty.className='kr-file-empty';
    empty.textContent='Файлы ещё не добавлены. Можно выбрать их за несколько раз.';
    list.append(empty);
  }
  selectedOffers.forEach((file,index)=>{
    const item=document.createElement('div');item.className='kr-file-entry';
    const icon=document.createElement('span');icon.className='kr-file-type';
    icon.textContent=(file.name.split('.').pop()||'FILE').slice(0,5).toUpperCase();
    const info=document.createElement('div');info.className='kr-file-info';
    const name=document.createElement('strong');name.textContent=file.name;name.title=file.name;
    const size=document.createElement('small');size.textContent=(file.size/1024).toFixed(1)+' КБ';
    info.append(name,size);
    const remove=document.createElement('button');remove.type='button';remove.className='kr-file-remove';
    remove.textContent='×';remove.title='Удалить '+file.name;remove.setAttribute('aria-label','Удалить '+file.name);
    remove.disabled=state.busy;
    remove.addEventListener('click',()=>{selectedOffers.splice(index,1);refreshOfferList();});
    item.append(icon,info,remove);list.append(item);
  });
}
function addOfferFiles(){
  const input=$('offerFiles');
  let duplicate=0,invalid=0,overflow=0;
  for(const file of input.files){
    if(!/\.(pdf|docx|xlsx|txt)$/i.test(file.name)||file.size===0||file.size>5*1024*1024){invalid++;continue;}
    if(selectedOffers.some(f=>fileKey(f)===fileKey(file))){duplicate++;continue;}
    if(selectedOffers.length>=10){overflow++;continue;}
    selectedOffers.push(file);
  }
  input.value='';
  refreshOfferList();
  const parts=[];
  if(duplicate)parts.push('Пропущено повторных файлов: '+duplicate);
  if(invalid)parts.push('Допустимы только PDF, DOCX, XLSX и TXT (UTF-8) до 5 МБ: '+invalid);
  if(overflow)parts.push('Лимит — 10 КП. Лишние файлы не добавлены: '+overflow);
  $('uploadFeedback').textContent=parts.join('. ');
}
function toggleAnalysisLoading(active){
  const overlay=$('krAnalysisLoading');
  if(!overlay)return;
  overlay.hidden=!active;
  document.body.classList.toggle('kr-analysis-busy',active);
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


function decisionFor(s){
  const mandatory=(s.checks||[]).filter(c=>c.mandatory!==false);
  const failed=mandatory.filter(c=>c.status==='fail').length;
  const unknown=mandatory.filter(c=>c.status==='unknown').length;
  const incomplete=mandatory.length===0;
  return {failed,unknown:incomplete?1:unknown,state:failed?'rejected':unknown||incomplete?'review':'eligible',
          label:failed?'Не подходит':unknown||incomplete?'Требует уточнения':'Подходит'};
}
function analysisOverview(result,suppliers){
  const eligible=suppliers.filter(s=>decisionFor(s).state==='eligible');
  const rejected=suppliers.filter(s=>decisionFor(s).state==='rejected');
  const review=suppliers.filter(s=>decisionFor(s).state==='review');
  const total=(result.requirements||[]).length;
  const lead=result.ranking?.recommended||result.recommended;
  const conclusion=lead
    ? 'Предварительно рекомендовано: '+lead+'. Проверьте источники и критерии оценки перед закупкой.'
    : eligible.length?'Есть подходящие предложения, однако итоговый выбор пока не определён.'
    : rejected.length===suppliers.length?'Не подходит: все предложения нарушают обязательные требования ТЗ.'
    : 'Требуется уточнение: пока нельзя подтвердить полное соответствие ТЗ.';
  const cards=[
    ['КП проанализировано',suppliers.length],['Требований выделено',total],
    ['Допущено',eligible.length],['Отклонено',rejected.length],
    ['Требует уточнения',review.length]
  ].map(([label,value])=>'<div class="kr-overview-stat"><span>'+safe(label)+'</span><strong>'+safe(value)+'</strong></div>').join('');
  const rows=suppliers.map(s=>{
    const d=decisionFor(s);
    const mandatory=(s.checks||[]).filter(c=>c.mandatory!==false);
    const passing=mandatory.filter(c=>c.status==='pass').length;
    const marks=d.state==='rejected'?'kr-rejected':d.state==='eligible'?'kr-eligible':'kr-review';
    const failedList=mandatory.filter(c=>c.status==='fail').slice(0,4).map(c=>safe(c.parameter)).join(', ');
    const missingList=mandatory.filter(c=>c.status==='unknown').slice(0,3).map(c=>safe(c.parameter)).join(', ');
    const priceFact=(s.facts||[]).find(f=>f.key==='price');
    const priceValue=s.price??priceFact?.value;
    const pricePart=typeof priceValue==='number'?'Цена: '+fmt(priceValue)+' ₽':'Цена: не подтверждена';
    const reason=d.failed?d.failed+' обязательных нарушений: '+failedList
      :d.unknown?'Нужно подтвердить: '+missingList
      :'Обязательные проверки пройдены';
    const rated=(result.ranking?.ranked||[]).find(x=>x.supplier===s.name);
    const position=(result.ranking?.ranked||[]).findIndex(x=>x.supplier===s.name);
    return '<tr><td><strong>'+safe(s.name)+'</strong></td><td><span class="kr-status '+marks+'">'+safe(d.label)+'</span></td>'+
      '<td>'+passing+' / '+mandatory.length+'</td><td>'+safe(reason)+'<div class="source">'+safe(pricePart)+'</div></td>'+
      '<td>'+(rated?'<strong>'+(position+1)+'</strong> · '+safe(fmt(rated.score))+' / 100':'—')+'</td></tr>';
  }).join('');
  return '<section class="kr-result-overview" aria-label="Итог анализа">'+
    '<div class="kr-overview-top"><span>ЗАКЛЮЧЕНИЕ KRAKEN AI</span><h2>Результат сравнения документов</h2><p>'+safe(conclusion)+'</p></div>'+
    '<div class="kr-overview-stats">'+cards+'</div>'+
    '<div class="data-card"><h2>Решение по каждому КП</h2><p class="kr-explain">В рейтинг попадают только предложения с подтверждённым выполнением обязательных пунктов. Неизвестное не считается совпадением.</p>'+
    '<div class="table-scroll"><table><thead><tr><th>КП</th><th>Решение</th><th>Подтверждено</th><th>Основание</th><th>Место и балл</th></tr></thead><tbody>'+rows+'</tbody></table></div></div></section>';
}
function requirementLabel(c){
  const prefix=c.operator==='min'?'≥ ':c.operator==='max'?'≤ ':c.operator==='lt'?'< ':c.operator==='range'?'от ':c.operator==='yes'?'Наличие: ':'= ';
  if(c.operator==='yes')return 'Обязательно наличие';
  return prefix+fmt(c.required)+(c.unit?' '+c.unit:'');
}

function evidenceRerankingMarkup(result){
  const data=result.evidence_retrieval;
  if(!data)return '';
  if(data.mode==='unavailable'){
    return '<div class="data-card"><h2>Нейросетевой поиск доказательств</h2><p class="kr-explain">Модель недоступна. Основная проверка характеристик выполнена по программным правилам.</p></div>';
  }
  const items=(data.results||[]).filter(x=>x.fragments?.length).slice(0,25);
  if(!items.length)return '';
  const content=items.map(x=>{
    const evidence=x.fragments.slice(0,3).map(f=>
      '<li><span class="kr-evidence-quote">«'+safe(f.quote)+'»</span>'+
      '<span class="kr-evidence-meta">'+safe(f.location)+' · строка '+safe(f.line)+' · релевантность '+safe(fmt(f.relevance_score))+'</span></li>'
    ).join('');
    return '<details class="kr-evidence-item"><summary><strong>'+safe(x.supplier)+'</strong> · '+safe(x.parameter)+'</summary><ol>'+evidence+'</ol></details>';
  }).join('');
  return '<section class="data-card kr-evidence-panel"><h2>Найденные доказательства</h2>'+
    '<p class="kr-explain">Поиск: '+(data.mode==='cross_encoder'?'нейросетевой Cross-Encoder':'совпадение слов')+
    '. Оценка показывает релевантность фрагмента требованию, а не соответствие ТЗ. Окончательное решение — в таблице проверок.</p>'+
    content+'</section>';
}
function badge(check){ const [label,css]=statuses[check?.status]||statuses.unknown;return `<span class="pill ${css}">${label}</span>`;}
function renderAnalysis(){
  const area=$('analysisContent');const result=state.result;
  if(!result){area.innerHTML='<div class="analysis-empty"><svg class="empty-symbol kr-icon" aria-hidden="true"><use href="/static/icons.svg#file-check"></use></svg><h2>Пока нет анализов</h2><p>Загрузите ТЗ и коммерческие предложения, чтобы увидеть сравнительную таблицу.</p><button id="analysisUpload" class="red-button">Загрузить документы</button></div>';
    $('analysisUpload').addEventListener('click',openUpload);return;}
  const suppliers=Array.isArray(result.suppliers)?result.suppliers:[];
  const rows=suppliers.map(s=>`<tr><td><strong>${safe(s.name)}</strong></td><td>${safe(s.passed)}</td><td>${safe(s.failed)}</td><td>${safe(s.unknown)}</td><td>${safe(s.coverage_percent)}%</td></tr>`).join('');
  const details=suppliers.map(s=>`<div class="data-card"><h2>${safe(s.name)}</h2><p class="kr-explain">${safe(decisionFor(s).label)} · ${safe(decisionFor(s).failed)} обязательных нарушений · ${safe(decisionFor(s).unknown)} неизвестных обязательных требований</p><div class="table-scroll"><table><thead><tr><th>Характеристика</th><th>Требование</th><th>Предложено</th><th>Результат</th></tr></thead><tbody>${(s.checks||[]).map(c=>`<tr><td><strong>${safe(c.parameter)}</strong><div class="source">ТЗ (${safe(locationLabel(c.requirement_locator))}): ${safe(c.requirement_source)}</div></td><td>${safe(requirementLabel(c))}</td><td>${c.actual==null?'Не найдено':`${safe(fmt(c.actual))} ${safe(c.unit)}`}<div class="source">КП (${safe(locationLabel(c.offer_locator))}): ${safe(c.offer_source||'Нет подтверждающей цитаты')}</div></td><td>${badge(c)}<div class="source">${safe(c.reason)}</div></td></tr>`).join('')}</tbody></table></div></div>`).join('');
  const caveat='<div class="kr-scope-note" role="note"><strong>Область проверки</strong><p>'+
    safe(result.scope_note||'Проверены только распознанные числовые условия. Нечисловые и нераспознанные требования требуют проверки специалистом.')+
    '</p></div>';
  const unknownDetails=suppliers.flatMap(s=>(s.checks||[]).filter(c=>c.status==='unknown').map(c=>({name:s.name,parameter:c.parameter}))).slice(0,6);
  const unresolved=unknownDetails.length?'<div class="data-card"><h2>Что нужно уточнить</h2><ul>'+
    unknownDetails.map(x=>'<li><strong>'+safe(x.name)+'</strong> — '+safe(x.parameter)+': недостаточно сведений</li>').join('')+
    '</ul></div>':'';
  const notes=(result.ai?.observations||[]).map(n=>`<div class="note"><strong>${safe(n.supplier)}</strong> — ${safe(n.finding)}<span>ТЗ: «${safe(n.requirement_quote)}»${n.offer_quote?' · КП: «'+safe(n.offer_quote)+'»':''} · ${safe(n.status)}</span></div>`).join('');
  const url=state.analysisId?'/api/analyses/'+encodeURIComponent(state.analysisId):'';
  area.innerHTML=analysisOverview(result,suppliers)+rankingMarkup(result,suppliers)+evidenceRerankingMarkup(result)+caveat+`<div class="summary-grid"><div class="metric"><span>Предложений</span><strong>${safe(suppliers.length)}</strong></div><div class="metric"><span>Проверено требований</span><strong>${safe(result.requirements?.length||0)}</strong></div><div class="metric"><span>Предварительный выбор</span><strong class="best">${safe(result.recommended||'Нужна проверка')}</strong></div></div><div class="data-card"><h2>Сводное сравнение</h2><div class="table-scroll"><table><thead><tr><th>Поставщик</th><th>Совпадений</th><th>Расхождений</th><th>Неизвестно</th><th>Покрытие</th></tr></thead><tbody>${rows}</tbody></table></div><p>${safe(result.warning)}</p></div>${details}<div class="data-card"><h2>Смысловые наблюдения AI</h2>${notes?`<div class="notes-list">${notes}</div>`:`<p>${result.ai?.enabled?'Наблюдения не найдены или сервис модели недоступен.':'Модель не подключена. Числовой анализ выполнен по правилам.'}</p>`}<p>Выводы предварительные: решение о закупке принимает специалист.</p></div>${unresolved}<div class="data-card kr-ask-card"><h2>Спросить Kraken о документах</h2><p>Чат использует результат анализа и найденные выдержки из файлов. Проверяйте важные ответы по первоисточникам.</p><div id="analysisQuestions" class="kr-questions"></div></div><div class="download-links"><a href="${url}/pdf">PDF</a><a href="${url}/xlsx">Excel</a><a href="${url}/csv">↓ Скачать CSV</a><a href="${url}/report">↓ JSON</a></div>`;
  bindRankingControls();renderAnalysisQuestions();
}
async function loadHistory(){
  try{const history=await request('/api/analyses');state.history=history;const pane=$('history');pane.replaceChildren();
    if(!history.length){const empty=document.createElement('span');empty.className='history-empty';empty.textContent='Ваши анализы появятся здесь';pane.append(empty);return;}
    for(const r of history){const button=document.createElement('button');button.className='history-item';button.title=r.filenames?.join(' · ');
      button.textContent=(r.filenames||[]).slice(1,2).join('')||'Анализ';button.addEventListener('click',()=>openHistory(r.id));pane.append(button);}
  }catch(e){console.warn('History unavailable:',e.message);}
}
async function openHistory(id){
  try{const result=await request('/api/analyses/'+encodeURIComponent(id));state.analysisId=id;state.result=result;state.conversationId=null;
    $('messages').replaceChildren();
    appendMessage('assistant','Вы открыли сохранённый анализ. Спросите меня о требованиях, расхождениях или источниках. Это предварительная проверка.');
    renderAnalysis();setView('analysis');}
  catch(e){appendMessage('assistant',e.message);}
}
async function uploadFiles(event){
  event.preventDefault();if(state.busy)return;
  const tz=$('tzFile').files[0],offers=selectedOffers.slice();
  if(!tz||offers.length<1||offers.length>10){$('uploadFeedback').textContent='Нужно ТЗ и от 1 до 10 предложений.';return;}
  if([tz,...offers].some(f=>f.size>5*1024*1024||f.size===0)){ $('uploadFeedback').textContent='Размер каждого файла: от 1 байта до 5 МБ.';return;}
  const fd=new FormData();fd.append('tz',tz);offers.forEach(f=>fd.append('proposals',f));
  $('uploadFeedback').textContent='Обрабатываем документы и проверяем доступные требования';
  $('uploadFeedback').classList.add('kr-uploading');
  setBusy(true);refreshOfferList();toggleAnalysisLoading(true);
  try{
    const payload=await request('/api/analyses',{method:'POST',body:fd});
    state.analysisId=payload.id;state.result=payload.result;state.conversationId=null;
    closeUpload();$('uploadForm').reset();selectedOffers.length=0;refreshOfferList();
    $('tzName').textContent='Выбрать файл';
    setView('chat');$('messages').replaceChildren();
    try{
      await ensureConversation();
    }catch(error){
      const result=payload.result;
      appendMessage('assistant','Анализ сохранён, но не удалось создать связанный чат. Откройте раздел аналитики.');
      console.warn('Analysis chat initialization failed:',error.name);
    }
    const r=payload.result;
    const title='Предварительная проверка '+offers.length+' предложений';
    const subtitle='Выделено требований: '+(r.requirements?.length||0)+' · Откройте решения, источники и нарушения';
    const last=$('messages').querySelector('.bubble-row.assistant:last-child .bubble');
    if(last&&!last.querySelector('.result-inline')){
      const content=last.querySelector('.message-text');
      if(content){
        const card=document.createElement('div');card.className='result-inline';
        const left=document.createElement('div');
        const head=document.createElement('strong');head.textContent=title;
        const note=document.createElement('p');note.textContent=subtitle;
        left.append(head,note);
        const open=document.createElement('button');open.type='button';open.textContent='Открыть сравнение';
        open.addEventListener('click',()=>{setView('analysis');renderAnalysis();});
        card.append(left,open);last.append(card);
      }
    }
    renderAnalysis();await Promise.allSettled([loadHistory(),loadConversations()]);
    window.dispatchEvent(new CustomEvent('kraken:state',{detail:{phase:'success'}}));
    $('composerHint').textContent='Задайте вопрос по требованиям или документам';
  }catch(e){$('uploadFeedback').textContent=e.message;}
  finally{toggleAnalysisLoading(false);$('uploadFeedback').classList.remove('kr-uploading');setBusy(false);refreshOfferList();}
}
async function loadConversations() {
  try {
    const chats=await request('/api/conversations');state.allConversations=chats;
    const pane=$('conversations');
    if (!pane) return;
    pane.replaceChildren();
    if (!chats.length) {const note=document.createElement('p');note.className='chat-list-empty';note.textContent='Здесь будут ваши диалоги';pane.append(note);return;}
    for (const chat of chats) {
      const row=document.createElement('div');row.className='chat-history-row';row.dataset.searchTitle=(chat.title||'Новый чат').toLocaleLowerCase('ru-RU');
      const button=document.createElement('button');button.type='button';button.className='chat-history-item';
      if (chat.id===state.conversationId) button.classList.add('selected');
      button.textContent=chat.title||'Новый чат';
      button.title=chat.title||'Новый чат';
      button.addEventListener('click',()=>openConversation(chat.id));
      const rename=document.createElement('button');rename.type='button';rename.className='chat-history-remove';
      rename.setAttribute('aria-label','Переименовать диалог '+(chat.title||'Новый чат'));
      rename.title='Переименовать';
      rename.innerHTML='<svg class="kr-icon" aria-hidden="true"><use href="/static/icons.svg#edit"></use></svg>';
      rename.addEventListener('click',()=>{
        const input=document.createElement('input');input.className='chat-history-edit';
        input.value=chat.title||'Новый чат';input.maxLength=90;
        const save=async()=>{
          if(!row.contains(input))return;
          const title=input.value.trim()||'Новый чат';
          try{await request('/api/conversations/'+encodeURIComponent(chat.id),{
            method:'PATCH',body:JSON.stringify({title})});await loadConversations();
          }catch(e){console.warn('Rename failed',e.message);await loadConversations();}
        };
        input.addEventListener('keydown',e=>{
          if(e.key==='Enter'){e.preventDefault();save();}
          if(e.key==='Escape'){loadConversations();}
        });
        input.addEventListener('blur',save,{once:true});
        row.replaceChildren(input);input.focus();input.select();
      });
      const remove=document.createElement('button');remove.type='button';remove.className='chat-history-remove';
      remove.setAttribute('aria-label','Удалить диалог '+(chat.title||'Новый чат'));
      remove.title='Удалить диалог';remove.innerHTML='<svg class="kr-icon" aria-hidden="true"><use href="/static/icons.svg#close"></use></svg>';
      remove.addEventListener('click',async()=>{
        try {await request('/api/conversations/'+encodeURIComponent(chat.id),{method:'DELETE'});
          if(state.conversationId===chat.id)resetChat();await loadConversations();
        }catch(e){console.warn('Delete conversation failed',e.message);}
      });
      row.append(button,rename,remove);pane.append(row);
    }
    filterConversations();
  } catch (e) {console.warn('Conversation list unavailable:',e.message);}
}
async function openConversation(id) {
  if(state.busy) return;
  try {
    const item=await request('/api/conversations/'+encodeURIComponent(id));
    state.conversationId=item.id;
    state.analysisId=item.analysis_id||null;
    state.result=null;
    if(state.analysisId){try{state.result=await request('/api/analyses/'+encodeURIComponent(state.analysisId));}catch{state.analysisId=null;}}
    $('messages').replaceChildren();setView('chat');
    for(const itemMessage of item.messages||[]) appendMessage(itemMessage.role,itemMessage.content);
    $('retryButton').hidden=!(item.messages||[]).some(x=>x.role==='user');
    await loadConversations();
  } catch(e){appendMessage('assistant','Не удалось открыть диалог: '+e.message);}
}
async function ensureConversation() {
  if(state.conversationId)return state.conversationId;
  const item=await request('/api/conversations',{method:'POST',body:JSON.stringify({
    title:state.analysisId?'Вопросы по анализу':'Новый чат',
    analysis_id:state.analysisId
  })});
  state.conversationId=item.id;
  if((item.messages||[]).length && !$('messages').querySelector('.bubble-row')){
    for(const message of item.messages)appendMessage(message.role,message.content);
  }
  return item.id;
}
function enrichAssistantMessage(node) {
  const bubble=node.closest('.bubble');if(!bubble||bubble.querySelector('.chat-actions'))return;
  const actions=document.createElement('div');actions.className='chat-actions';
  const copy=document.createElement('button');copy.type='button';copy.className='chat-action';
  copy.textContent='Копировать';copy.setAttribute('aria-label','Копировать ответ');
  copy.addEventListener('click',async()=>{
    try{await navigator.clipboard.writeText(node.dataset.raw||node.textContent);copy.textContent='Скопировано';setTimeout(()=>copy.textContent='Копировать',1500);}catch{copy.textContent='Недоступно';}
  });
  actions.append(copy);bubble.append(actions);
}
function filterConversations(){
 const input=$('conversationSearch');if(!input)return;
 const query=input.value.trim().toLocaleLowerCase('ru-RU');
 document.querySelectorAll('.chat-history-row').forEach(el=>el.hidden=!!query&&!el.dataset.searchTitle.includes(query));
}
function stopGenerating(){state.streamController?.abort();}
async function streamConversation(text, retry=false) {
  if(state.busy)return;
  const input=$('messageInput');
  let placeholder;
  setView('chat');
  try {
    const id=await ensureConversation();
    if(!retry){input.value='';input.style.height='';appendMessage('user',text);}
    state.streamController=new AbortController();
    setBusy(true);
    $('stopButton').hidden=false;
    $('sendButton').hidden=true;
    placeholder=appendMessage('assistant','');
    const indicator=document.createElement('div');
    indicator.className='kr-thinking-indicator';
    indicator.setAttribute('role','status');
    indicator.setAttribute('aria-label','Kraken анализирует запрос');
    indicator.innerHTML='<svg viewBox="0 0 52 32" aria-hidden="true" focusable="false">'+
      '<path d="M4 23C13 24 10 9 21 13S28 29 38 18 44 11 48 9" /></svg>'+
      '<span>Kraken думает</span><span class="kr-thinking-dots" aria-hidden="true"><i></i><i></i><i></i></span>';
    placeholder.append(indicator);
    let started=false;
    const response=await fetch('/api/conversations/'+encodeURIComponent(id)+'/stream',{
       method:'POST',credentials:'same-origin',cache:'no-store',
       headers:{'X-Kraken-Request':'1','Content-Type':'application/json'},
       body:JSON.stringify({message:retry?'':text,retry,analysis_id:state.analysisId}),
       signal:state.streamController.signal
    });
    if(!response.ok)throw new Error('Ошибка генерации ('+response.status+')');
    if(!response.body)throw new Error('Потоковые ответы не поддерживаются браузером');
    const reader=response.body.getReader();
    const decoder=new TextDecoder();
    let buffer='', complete=false;
    while(true) {
      const chunk=await reader.read();
      if(chunk.done)break;
      buffer+=decoder.decode(chunk.value,{stream:true});
      const blocks=buffer.split(/\r?\n\r?\n/);buffer=blocks.pop()||'';
      for(const block of blocks) {
        const type=block.match(/^event:\s*(\w+)/m)?.[1];
        const dataLine=block.match(/^data:\s*(.*)$/m)?.[1];
        if(!type||!dataLine)continue;
        const data=JSON.parse(dataLine);
        if(type==='delta'){if(!started){placeholder.replaceChildren();started=true;}placeholder.textContent+=data.text||'';scrollMessages();}
        if(type==='done'){complete=true;}
        if(type==='error'){throw new Error(data.message||'Ошибка модели');}
      }
    }
    if(!complete)throw new Error('Соединение прервано до завершения ответа');
    const rawAnswer=placeholder.textContent;
    placeholder.dataset.raw=rawAnswer;
    window.KrakenMarkdown?.render(placeholder,rawAnswer);
    enrichAssistantMessage(placeholder);
    $('retryButton').hidden=false;
    await loadConversations();
  } catch(e) {
    if(placeholder) placeholder.textContent= e.name==='AbortError'?'Генерация остановлена.':('Не удалось получить ответ: '+e.message);
  } finally {
    state.streamController=null;
    setBusy(false);$('stopButton').hidden=true;$('sendButton').hidden=false;
    input.focus();scrollMessages();
  }
}
async function retryMessage() {
  if(state.busy||!state.conversationId)return;
  await streamConversation('',true);
  if(state.conversationId&&!state.busy)await openConversation(state.conversationId);
}

async function sendMessage() {
  if(state.busy)return;
  const value=$('messageInput').value.trim();
  if(!value)return;
  return streamConversation(value,false);
}

function setTheme(theme){
  document.documentElement.dataset.theme=theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme==='dark'?'#171717':'#ffffff');
  try{localStorage.setItem('kraken_theme',theme)}catch{}
}
let themeTransitioning=false;
async function transitionTheme(trigger){
  if(themeTransitioning)return;
  const next=document.documentElement.dataset.theme==='dark'?'light':'dark';
  const reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(reduce||typeof document.startViewTransition!=='function'){setTheme(next);return;}
  themeTransitioning=true;
  const rect=trigger?.getBoundingClientRect();
  const x=rect?rect.left+rect.width/2:innerWidth/2;
  const y=rect?rect.top+rect.height/2:innerHeight/2;
  const radius=Math.hypot(Math.max(x,innerWidth-x),Math.max(y,innerHeight-y))+4;
  try{
    const transition=document.startViewTransition(()=>setTheme(next));
    await transition.ready;
    const animation=document.documentElement.animate({
      clipPath:[`circle(0px at ${x}px ${y}px)`,`circle(${radius}px at ${x}px ${y}px)`]
    },{duration:360,easing:'cubic-bezier(.25,.8,.25,1)',pseudoElement:'::view-transition-new(root)',fill:'both'});
    await animation.finished.catch(()=>{});
  }catch(error){
    // The color variables still switch even if browser cancels the animation.
    if(document.documentElement.dataset.theme!==next)setTheme(next);
  }finally{themeTransitioning=false;}
}
function init(){
  try{setTheme(localStorage.getItem('kraken_theme')==='dark'?'dark':'light');}catch{setTheme('light');}
  $('conversationSearch')?.addEventListener('input',filterConversations);
  document.addEventListener('keydown',e=>{
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){
      e.preventDefault();openSidebar();$('conversationSearch')?.focus();
    }
    if((e.ctrlKey||e.metaKey)&&e.shiftKey&&e.key.toLowerCase()==='o'){
      e.preventDefault();resetChat();$('messageInput')?.focus();
    }
  });
  $('themeButton').addEventListener('click',event=>transitionTheme(event.currentTarget));
  const menu=$('profileMenu'),profile=$('profileButton');
  function toggleProfile(open){
    if(!menu||!profile)return;
    menu.hidden=!open;
    profile.setAttribute('aria-expanded',String(open));
  }
  profile?.addEventListener('click',()=>toggleProfile(menu.hidden));
  $('profileTheme')?.addEventListener('click',event=>{toggleProfile(false);transitionTheme($('themeButton'));});
  $('profileSignout')?.addEventListener('click',()=>{$('logout').click();toggleProfile(false);});
  document.addEventListener('pointerdown',e=>{if(!e.target.closest('.profile-wrap'))toggleProfile(false);});
  $('railUpload')?.addEventListener('click',openUpload);
  $('railCompare')?.addEventListener('click',()=>{setView('analysis');renderAnalysis();});
  $('railCheck')?.addEventListener('click',()=>{if(state.result){setView('analysis');renderAnalysis();}else openUpload();});
  $('railReports')?.addEventListener('click',()=>{if(state.result){setView('analysis');renderAnalysis();}else openUpload();});
  $('openSidebar').addEventListener('click',openSidebar);$('closeSidebar').addEventListener('click',closeSidebar);$('menuBackdrop').addEventListener('click',closeSidebar);
  document.querySelectorAll('[data-view]').forEach(el=>el.addEventListener('click',()=>{setView(el.dataset.view);if(el.dataset.view==='analysis')renderAnalysis()}));
  $('newChat').addEventListener('click',resetChat);$('panelNewChat').addEventListener('click',resetChat);$('analysisNew').addEventListener('click',openUpload);
  $('stopButton').addEventListener('click',stopGenerating);$('retryButton').addEventListener('click',retryMessage);
  $('uploadButton').addEventListener('click',openUpload);$('closeUpload').addEventListener('click',closeUpload);
  $('uploadModal').addEventListener('click',e=>{if(e.target===$('uploadModal'))closeUpload();});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeUpload();closeSidebar();if($('profileMenu')){$('profileMenu').hidden=true;$('profileButton').setAttribute('aria-expanded','false');}}});
  $('tzFile').addEventListener('change',()=>{$('tzName').textContent=$('tzFile').files[0]?.name||'Выбрать файл'});
  $('offerFiles').addEventListener('change',addOfferFiles);
  refreshOfferList();
  $('uploadForm').addEventListener('submit',uploadFiles);
  $('sendButton').addEventListener('click',sendMessage);
  $('messageInput').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage()}});
  $('messageInput').addEventListener('input',()=>{const t=$('messageInput');t.style.height='auto';t.style.height=Math.min(t.scrollHeight,150)+'px';});
  $('logout').addEventListener('click',async()=>{try{await request('/api/logout',{method:'POST'})}catch{}showAuth();resetChat();$('history').replaceChildren();$('conversations').replaceChildren();});
  $('loginForm').addEventListener('submit',async e=>{e.preventDefault();$('authError').textContent='';
    try{const r=await request('/api/login',{method:'POST',body:JSON.stringify({password:$('passwordInput').value})});hideAuth();resetChat();showFirstVisitGuide();$('aiStatus').innerHTML='<span class="status-dot"></span> '+(r.ai_enabled?'AI настроен':'Локальная проверка');loadHistory();loadConversations();}
    catch(err){$('authError').textContent=err.message;}
  });
  bindPrompts();request('/api/me').then(r=>{hideAuth();showFirstVisitGuide();$('aiStatus').innerHTML='<span class="status-dot"></span> '+(r.ai_enabled?'AI настроен':'Локальная проверка');loadHistory();loadConversations();}).catch(showAuth);
}
document.addEventListener('DOMContentLoaded',init);
