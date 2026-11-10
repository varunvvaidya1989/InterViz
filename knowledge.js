'use strict';
const $ = selector=>document.querySelector(selector);
const $$ = selector=>[...document.querySelectorAll(selector)];
const escapeHTML = value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = n=>Number(n).toLocaleString('en-US');
const modeInfo={
  explain:['Get a grounded explanation with trade-offs, failure modes, and a question to test yourself.','Ask tutor ↗'],
  practice:['Practise one interview question at a time. Answer in your own words, then request feedback.','Start practice ↗'],
  review:['Compare your reasoning with the source material. Get specific feedback and a focused follow-up.','Review my answer ↗'],
  plan:['Build a short learning sequence from retrieved source material, with concrete practice tasks.','Build a path ↗'],
  search:['Search the indexed text locally. Read original passages and open the exact PDF pages.','Search documents ↗']
};
let library=null,selected=new Set(),track='',mode='explain',busy=false,history=[],lastPractice='',requestId=0;
const trackNames={'backend':'Backend engineering','system-design':'System design','low-level-design':'Low-level design','devops':'DevOps & production','ai-engineering':'AI engineering','other':'Other documents'};

async function api(path,options){
  const response=await fetch(path,options);let data;
  try{data=await response.json();}catch{throw new Error('The local RAG server is unavailable. Start it with: python -m rag.server');}
  if(!response.ok)throw new Error(data.error||`Request failed (${response.status}).`);
  return data;
}
function status(message,error=false){$('#request-status').textContent=message;$('#request-status').className=message?(error?'error':'loading'):'';}
function sourceURL(source){
  // Only local PDF links from the server are eligible to become clickable.
  return typeof source.url==='string'&&/^\/docs\/[^?#]+\.pdf#page=\d+$/.test(source.url)?source.url:'#';
}
function pdfPath(path,page=1){return '/'+path.split('/').map(encodeURIComponent).join('/')+'#page='+page;}
function setMode(next){
  mode=next;$$('[data-mode]').forEach(b=>{b.classList.toggle('selected',b.dataset.mode===mode);b.setAttribute('aria-pressed',String(b.dataset.mode===mode));});
  $('#answer-field').hidden=mode!=='review';$('#student-answer').required=mode==='review';
  $('#mode-description').textContent=modeInfo[mode][0];$('#submit-question').textContent=modeInfo[mode][1];
}
function scope(){return library.documents.filter(d=>selected.has(d.id)&&(!track||d.track===track)).map(d=>d.id);}
function updateScope(){
  if(!library)return;const count=scope().length;
  $('#scope-summary').textContent=`${count} selected source${count===1?'':'s'}${track?' · '+trackNames[track]:''} · page-level evidence`;
  $$('.document-filters label').forEach(label=>{const doc=library.documents.find(d=>d.id===label.dataset.doc);label.classList.toggle('excluded',!!track&&doc.track!==track);});
}
function clearSession(){history=[];lastPractice='';requestId++;$('#conversation').replaceChildren();$('#result-list').replaceChildren();$('#search-results').hidden=true;$('#student-answer').value='';status('');}
function renderDocuments(){
  $('#document-filters').innerHTML=library.documents.map(d=>`<label data-doc="${d.id}"><input type="checkbox" value="${d.id}" checked><span>${escapeHTML(d.title)}<small>${number(d.pages)} pages</small></span></label>`).join('');
  $$('.document-filters input').forEach(input=>input.onchange=()=>{if(input.checked)selected.add(input.value);else selected.delete(input.value);clearSession();updateScope();});
  $('#document-cards').innerHTML=library.documents.map(d=>`<article class="document-card"><span class="doc-type">${escapeHTML(trackNames[d.track]||d.track)} / ${escapeHTML(d.kind)}</span><h3>${escapeHTML(d.title)}</h3><div class="doc-meta"><span>${number(d.pages)} pages</span><span>${d.units.length} ${d.kind==='guide'?'modules':'topics'}</span>${d.questions?`<span>${d.questions} question pages</span>`:''}</div><details><summary>Explore sections & start learning</summary><ul class="unit-list">${d.units.map(u=>`<li><button data-unit-doc="${d.id}" data-unit="${escapeHTML(u.title)}">${escapeHTML(u.title)}<small>p.${u.page}${u.page===u.end?'':'–'+u.end}</small></button></li>`).join('')}</ul></details><a href="${pdfPath(d.path)}" target="_blank" rel="noopener">Open original document ↗</a></article>`).join('');
  $$('[data-unit]').forEach(b=>b.onclick=()=>{
    const doc=library.documents.find(d=>d.id===b.dataset.unitDoc);selected=new Set([doc.id]);track='';
    $$('.document-filters input').forEach(i=>i.checked=selected.has(i.value));$$('[data-track]').forEach(t=>{t.classList.toggle('selected',t.dataset.track==='');t.setAttribute('aria-pressed',String(t.dataset.track===''));});
    clearSession();updateScope();$('#question').value=`Help me understand ${b.dataset.unit}, including the key trade-offs and interview follow-ups.`;setMode('explain');$('#question').focus();$('.ask-workspace').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
  });
}
function highlight(text,query){
  const words=query.toLowerCase().match(/[a-z0-9-]{4,}/g)||[];
  if(!words.length)return escapeHTML(text);
  const expression=new RegExp('('+[...new Set(words)].map(w=>w.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|')+')','ig');
  return text.split(expression).map((part,i)=>i%2?`<mark>${escapeHTML(part)}</mark>`:escapeHTML(part)).join('');
}
function renderSearch(results,query){
  $('#search-results').hidden=false;$('#result-count').textContent=`${results.length} relevant page${results.length===1?'':'s'}`;
  $('#result-list').innerHTML=results.length?results.map((s,i)=>`<article class="source-result"><div class="result-meta"><span class="source-number">${i+1}</span><span>${escapeHTML(s.document_title)}</span><span>PAGE ${s.page}</span></div><h3>${escapeHTML(s.question_id?s.question_id+' · ':'')}${escapeHTML(s.title)}</h3><p>${highlight(s.snippet,query)}</p><a href="${escapeHTML(sourceURL(s))}" target="_blank" rel="noopener">Read original page ↗</a><details><summary>Inspect the complete retrieved passage</summary><pre>${escapeHTML(s.text)}</pre></details></article>`).join(''):'<div class="source-result"><h3>No supporting passages found.</h3><p>Try a more specific topic or select more source documents. The current library has no dedicated salary-negotiation guide.</p></div>';
}
function prose(text){return escapeHTML(text).replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>');}
function appendTurn(query,result,answer,requestedMode){
  const turn=document.createElement('article');turn.className='turn';
  const user=document.createElement('div');user.className='user-question';const bubble=document.createElement('div');bubble.textContent=query+(answer?'\n\nMy answer:\n'+answer:'');user.append(bubble);turn.append(user);
  const response=document.createElement('div');response.className='assistant-response';
  response.innerHTML=`<div class="assistant-label"><span>✦</span> ENTERVIEW · ${result.generated?'DOCUMENT-GROUNDED TUTOR':'SOURCE COVERAGE'}</div>`;
  const body=document.createElement('div');body.className='answer-prose';
  for(const block of result.blocks){const span=document.createElement('span');span.innerHTML=prose(block.text);body.append(span);for(const c of block.citations||[]){const anchor=document.createElement('a');anchor.className='citation';anchor.href=sourceURL(c);anchor.target='_blank';anchor.rel='noopener';anchor.textContent=`${c.source_index+1} · p.${c.page}`;anchor.title=`${c.document}, page ${c.page}\n${c.cited_text}`;body.append(anchor);}}
  response.append(body);
  if(result.generated&&!result.citation_count){const note=document.createElement('p');note.className='answer-note';note.textContent='This response has no attached source citations. Treat it as an illustrative exercise or suggestion, not a verified source claim.';response.append(note);}
  if(result.truncated){const note=document.createElement('p');note.className='answer-note';note.textContent='The response reached its length limit. Ask a focused follow-up to continue.';response.append(note);}
  if(result.sources.length){const evidence=document.createElement('details');evidence.className='answer-evidence';evidence.innerHTML=`<summary>Inspect the ${result.sources.length} passages supplied to the tutor</summary><div class="answer-source-links">${result.sources.map((s,i)=>`<a href="${escapeHTML(sourceURL(s))}" target="_blank" rel="noopener">${i+1}. ${escapeHTML(s.document_title)} · p.${s.page}</a>`).join('')}</div>`;response.append(evidence);}
  const follow=document.createElement('div');follow.className='followup-row';
  if(requestedMode==='practice'){
    lastPractice=result.blocks.map(b=>b.text).join('');
    const review=document.createElement('button');review.textContent='Write my answer & get feedback →';review.onclick=()=>{setMode('review');$('#question').value=lastPractice.slice(0,1800);$('#student-answer').focus();$('.ask-workspace').scrollIntoView({block:'start'});};follow.append(review);
  }else if(result.generated){
    const practise=document.createElement('button');practise.textContent='Practise this in an interview →';practise.onclick=()=>{setMode('practice');$('#question').value=query;$('#question').focus();$('.ask-workspace').scrollIntoView({block:'start'});};follow.append(practise);
  }
  if(follow.childElementCount)response.append(follow);
  turn.append(response);$('#conversation').append(turn);turn.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
}
async function submit(event){
  event.preventDefault();if(busy||!library)return;
  const query=$('#question').value.trim(),answer=$('#student-answer').value.trim(),docs=scope(),requestedMode=mode;
  if(!query)return;
  if(!docs.length){status('Select at least one document in the chosen track.',true);return;}
  if(mode==='review'&&!answer){status('Write your answer first, then request feedback.',true);return;}
  busy=true;$('#submit-question').disabled=true;const active=++requestId;
  status(mode==='search'?'Searching your local document index…':'Retrieving source passages and preparing a grounded response…');
  try{
    if(mode==='search'){
      const params=new URLSearchParams({q:query});docs.forEach(d=>params.append('document',d));
      const result=await api('/api/search?'+params);
      if(active!==requestId)return;renderSearch(result.results,query);status('');$('#search-results').scrollIntoView({block:'start'});
    }else{
      const result=await api('/api/tutor',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query,mode:requestedMode,documents:docs,answer:requestedMode==='review'?answer:'',history:history.slice(-6)})});
      if(active!==requestId)return;status('');appendTurn(query,result,requestedMode==='review'?answer:'',requestedMode);
      if(result.generated){history.push({role:'user',content:(query+(answer?'\nStudent answer: '+answer:'')).slice(0,2500)},{role:'assistant',content:result.blocks.map(b=>b.text).join('').slice(0,2500)});history=history.slice(-6);}
    }
  }catch(error){if(active===requestId)status(error.message,true);}
  finally{busy=false;$('#submit-question').disabled=false;}
}
async function initialise(){
  if(location.protocol==='file:'){
    $('#setup-message').hidden=false;$('#setup-message').innerHTML='The knowledge workspace needs the local Python server. The original animated labs still work by opening index.html.<code>python -m rag.ingest\npython -m rag.server</code>Then open http://127.0.0.1:8000/';
    $('#connection-state').textContent='Server needed';$('#tutor-badge').textContent='Local server required';$('#submit-question').disabled=true;return;
  }
  try{
    const [state,data]=await Promise.all([api('/api/status'),api('/api/library')]);library=data;selected=new Set(library.documents.map(d=>d.id));renderDocuments();updateScope();
    const t=state.totals;$('#corpus-stats').innerHTML=`<span><strong>${t.documents}</strong> source documents</span><span><strong>${number(t.pages)}</strong> pages</span><span><strong>${number(t.questions)}</strong> question pages</span><span><strong>${number(t.units)}</strong> sections & topics</span>`;
    $('#connection-state').textContent=`${number(t.chunks)} passages indexed`;$('#tutor-badge').textContent=state.tutor_configured?'✦ Hosted tutor configured':'Cited search ready';
    if(!state.tutor_configured){$('#setup-message').hidden=false;$('#setup-message').textContent='Cited search is ready. For explanations and feedback, set ANTHROPIC_API_KEY in the server environment and restart the server. No key belongs in browser code.';setMode('search');}
  }catch(error){$('#setup-message').hidden=false;$('#setup-message').textContent=error.message;$('#connection-state').textContent='Server unavailable';$('#tutor-badge').textContent='Setup needed';$('#submit-question').disabled=true;}
}
$$('[data-mode]').forEach(b=>b.onclick=()=>setMode(b.dataset.mode));
$$('[data-track]').forEach(b=>b.onclick=()=>{track=b.dataset.track;$$('[data-track]').forEach(x=>{x.classList.toggle('selected',x===b);x.setAttribute('aria-pressed',String(x===b));});clearSession();updateScope();});
$$('[data-prompt]').forEach(b=>b.onclick=()=>{$('#question').value=b.dataset.prompt;$('#question').focus();});
$('#select-all').onclick=()=>{if(!library)return;selected=new Set(library.documents.map(d=>d.id));$$('.document-filters input').forEach(i=>i.checked=true);clearSession();updateScope();};
$('#new-session').onclick=()=>{clearSession();$('#question').value='';$('#question').focus();};$('#ask-form').onsubmit=submit;
$('#toggle-sources').onclick=()=>{const open=$('#toggle-sources').getAttribute('aria-expanded')!=='true';$('#toggle-sources').setAttribute('aria-expanded',String(open));$('.knowledge-page .sidebar').classList.toggle('sources-open',open);};
$('#question').onkeydown=e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();$('#ask-form').requestSubmit();}};
initialise();
