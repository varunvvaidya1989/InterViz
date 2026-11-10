'use strict';
const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
const esc = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => Math.round(n).toLocaleString('en-US');
const storage = {read(key, fallback){try{return JSON.parse(localStorage.getItem(key)) ?? fallback;}catch{return fallback;}},write(key,value){try{localStorage.setItem(key,JSON.stringify(value));}catch{/* The app remains usable with storage disabled. */}}};
let progress=storage.read('enterview-progress-v1',{});
if(!progress || typeof progress!=='object' || Array.isArray(progress)) progress={};
let reduced = storage.read('enterview-reduced-motion', matchMedia('(prefers-reduced-motion: reduce)').matches);
let current=LESSONS[0], tab='experiment', phase=-1, playing=false, timer=null, animation=0, animationGeneration=0;
let answers={}, libraryFilter='all', level=0, toastTimer;
let state, request=null;
const stages = {
  'load-balancing':['Arrive','Check health','Route','Respond'],
  caching:['Request','Look up','Fetch / reuse','Fill / return','Respond'],
  'url-shortener':['Request','Validate / look up','Generate / fetch','Store / prepare','Respond']
};
function initialState(){return {
  healthy:[true,true,true], counts:[0,0,0], algorithm:'round-robin', cursor:0, volume:3, total:0, rejected:0,
  key:'book', ttl:8, clock:0, cache:{}, db:{book:24,course:49,notebook:12}, hits:0, misses:0, stale:0,
  mode:'create', longUrl:'https://example.com/a/very/long/guide-to-system-design', alias:'', code:'learn01', lastCreated:'learn01', counter:1,
  links:Object.assign(Object.create(null),{learn01:'https://example.com/system-design'}), urlCache:Object.create(null), cacheOnline:true, created:0, resolved:0, dbReads:0,
  linksPerDay:100, readRatio:100, hitRate:98
};}
function toast(message){$('#toast').textContent=message;$('#toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),3500);}
function setMotion(){document.documentElement.classList.toggle('no-motion',!!reduced);$('#motion-toggle').textContent=`Motion: ${reduced?'reduced':'on'}`;$('#motion-toggle').setAttribute('aria-pressed',String(!!reduced));}
function renderNav(){
  $('#lesson-nav').innerHTML=LESSONS.map((l,i)=>`<button class="nav-item ${l.id===current.id?'active':''}" data-lesson="${l.id}" ${l.id===current.id?'aria-current="page"':''}><span class="nav-number">0${i+1}</span><span>${esc(l.title)}<small>${i<2?'Core concept':'Design problem'}</small></span>${progress[l.id]?'<span class="done" aria-label="Completed">✓</span>':''}</button>`).join('');
  const complete=LESSONS.filter(l=>progress[l.id]).length;
  $('#progress-count').textContent=`${complete} / 3`;$('#progress-fill').style.width=`${complete/3*100}%`;
}
function selectLesson(id, updateHash=true){
  clearTimeout(toastTimer);$('#toast').classList.remove('visible');
  current=LESSONS.find(l=>l.id===id)||LESSONS[0];stop();state=initialState();phase=-1;request=null;answers={};level=0;
  if(updateHash) history.replaceState(null,'',`#${current.id}`);
  document.title=`${current.title} — EnterView`;
  $('#lesson-eyebrow').textContent=current.category;
  $('#lesson-count').textContent=`LESSON 0${LESSONS.indexOf(current)+1} / 03`;
  $('#lesson-title').textContent=current.title;
  $('#lesson-intro').textContent=current.intro;
  $('#lesson-time').textContent=`◷  ${current.time} to explore`;
  $('#breadcrumb').textContent=current.id==='url-shortener'?'Design problems':'Core concepts';
  $('#source-link').href=`${current.source}#page=${current.page}`;
  $('#source-link').textContent=`Source · p.${current.page} ↗`;
  $('#diagram-title').textContent=current.diagram;
  $('#takeaway').textContent=current.takeaway;$('#model-note').textContent=current.note;
  $('#next-lesson').textContent=LESSONS.indexOf(current)===2?'Back to first lesson ↗':'Next lesson →';
  renderNav();renderControls();renderUnderstand();renderQuiz();switchTab('experiment');render();
}
function switchTab(next){
  if(next!=='experiment') stop();tab=next;
  for(const name of ['experiment','understand','check']){
    $(`#panel-${name}`).hidden=name!==next;
    $(`#tab-${name}`).setAttribute('aria-selected',String(name===next));
    $(`#tab-${name}`).tabIndex=name===next?0:-1;
  }
}
function stop(){playing=false;clearTimeout(timer);timer=null;cancelAnimationFrame(animation);if($('#play'))$('#play').innerHTML='▶ <span>Play flow</span>';}
function schedule(){clearTimeout(timer);if(playing)timer=setTimeout(()=>{advance();schedule();},Number($('#speed').value));}
function togglePlay(){
  if(playing){stop();return;}
  playing=true;$('#play').innerHTML='Ⅱ <span>Pause flow</span>';
  if(phase<0)advance();schedule();
}
function conditionChanged(message){stop();phase=-1;request=null;render();if(message)toast(message);}
function pickRoutes(){
  const slots=state.algorithm==='weighted'?[0,0,1,2]:[0,1,2];
  const eligible=slots.filter(i=>state.healthy[i]);const targets=[];
  if(eligible.length){for(let i=0;i<state.volume;i++)targets.push(eligible[(state.cursor+i)%eligible.length]);}
  return {targets,nextCursor:eligible.length?(state.cursor+state.volume)%eligible.length:0};
}
function begin(){
  if(current.id==='load-balancing'){request=pickRoutes();return true;}
  if(current.id==='caching'){
    state.clock++;const cached=state.cache[state.key];const hit=!!cached&&cached.expires>state.clock;
    request={key:state.key,hit,value:hit?cached.value:state.db[state.key],stale:hit&&cached.value!==state.db[state.key]};return true;
  }
  if(state.mode==='create'){
    const raw=state.longUrl.trim();let parsed;
    try{parsed=new URL(raw);if(!['http:','https:'].includes(parsed.protocol)||!parsed.hostname)throw new Error();}
    catch{urlStatus('Enter a valid URL beginning with https:// or http://.',true);return false;}
    const alias=state.alias.trim();
    if(alias&&!/^[a-zA-Z0-9_-]{3,16}$/.test(alias)){urlStatus('Alias must be 3–16 letters, numbers, hyphens, or underscores.',true);return false;}
    let counter=state.counter;let code=alias||base62(counter).padStart(7,'0');
    while(!alias&&Object.hasOwn(state.links,code))code=base62(++counter).padStart(7,'0');
    request={mode:'create',url:parsed.href,code,duplicate:Object.hasOwn(state.links,code),nextCounter:counter+1};
  }else{
    const code=state.code.trim();if(!code){urlStatus('Enter a short code, such as learn01.',true);return false;}
    const hit=state.cacheOnline&&Object.hasOwn(state.urlCache,code);
    request={mode:'resolve',code,hit,url:hit?state.urlCache[code]:(Object.hasOwn(state.links,code)?state.links[code]:undefined)};
  }return true;
}
function base62(n){const alphabet='0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';let code='';do{code=alphabet[n%62]+code;n=Math.floor(n/62);}while(n);return code;}
function commit(){
  if(current.id==='load-balancing'){
    request.targets.forEach(i=>state.counts[i]++);state.total+=request.targets.length;
    if(!request.targets.length)state.rejected+=state.volume;state.cursor=request.nextCursor;
  }else if(current.id==='caching'){
    if(request.hit){state.hits++;if(request.stale)state.stale++;}else{state.misses++;state.cache[request.key]={value:request.value,expires:state.clock+state.ttl};}
  }else if(request.mode==='create'){
    if(request.duplicate){urlStatus(`409 Conflict · “${request.code}” is already claimed. Choose another alias.`,true);}
    else{state.links[request.code]=request.url;state.counter=request.nextCounter;state.code=request.code;state.lastCreated=request.code;state.created++;urlStatus(`Created ev.local/${request.code} → ${request.url}`);}
  }else{
    if(!request.hit)state.dbReads++;
    if(!request.url){urlStatus(`404 Not Found · No mapping exists for “${request.code}”.`,true);}
    else{if(state.cacheOnline)state.urlCache[request.code]=request.url;state.resolved++;urlStatus(`302 Found · Location: ${request.url} (simulated)`);}
  }
}
function advance(){
  if(phase<0||phase===stages[current.id].length-1){
    if(!begin()){stop();return;}phase=0;
  }else phase++;
  if(phase===stages[current.id].length-1){commit();if(current.id==='url-shortener')stop();}
  render();
}
function reset(){stop();state=initialState();request=null;phase=-1;level=0;renderControls();renderUnderstand();render();toast('Experiment reset. Your quiz progress is kept.');}
function rangeControl(id,label,value,min,max,unit=''){return `<div class="control-group"><label class="control-label" for="${id}">${label}<output id="${id}-value" for="${id}">${value}${unit}</output></label><input type="range" id="${id}" min="${min}" max="${max}" value="${value}"><div class="range-ends"><span>${min}${unit}</span><span>${max}${unit}</span></div></div>`;}
function renderControls(){
  const root=$('#lab-controls');
  if(current.id==='load-balancing'){
    root.innerHTML=rangeControl('volume','Requests per round',state.volume,1,12)+`<div class="control-group"><label class="control-label" for="algorithm">Routing algorithm</label><select id="algorithm"><option value="round-robin">Round robin</option><option value="weighted">Weighted round robin</option></select><p class="control-hint" id="algorithm-hint">Each healthy server gets a turn.</p></div><div class="control-group"><div class="control-label">Server health <span>Toggle to test</span></div>${['A','B','C'].map((s,i)=>`<button class="server-toggle" data-server="${i}" aria-pressed="true" aria-label="Server ${s} healthy"><span>Server ${s} <small id="count-${i}">· 0 requests</small></span><span class="switch" aria-hidden="true"></span></button>`).join('')}</div><div class="challenge"><strong>↳ TRY BREAKING SOMETHING</strong><p>Take Server B offline. Does it still receive new requests? What happens when all three are down?</p></div>`;
    $('#volume').oninput=e=>{state.volume=Number(e.target.value);$('#volume-value').value=state.volume;conditionChanged();};
    $('#algorithm').onchange=e=>{state.algorithm=e.target.value;state.cursor=0;$('#algorithm-hint').textContent=state.algorithm==='weighted'?'A gets two turns; B and C get one each.':'Each healthy server gets a turn.';conditionChanged();};
    $$('[data-server]').forEach(button=>button.onclick=()=>{const i=Number(button.dataset.server);state.healthy[i]=!state.healthy[i];state.cursor=0;button.setAttribute('aria-pressed',String(state.healthy[i]));button.setAttribute('aria-label',`Server ${'ABC'[i]} ${state.healthy[i]?'healthy':'offline'}`);conditionChanged(`Server ${'ABC'[i]} ${state.healthy[i]?'is back online.':'is offline. New rounds skip it.'}`);});
  }else if(current.id==='caching'){
    root.innerHTML=`<div class="control-group"><label class="control-label" for="cache-key">Requested product</label><select id="cache-key"><option value="book">System design book</option><option value="course">Interview course</option><option value="notebook">Notebook</option></select><p class="control-hint">Repeat a product for a hit. Switch to a new one for a miss.</p></div>`+rangeControl('ttl','Cache lifetime (TTL)',state.ttl,2,20,'s')+`<div class="control-group"><div class="control-label">The source of truth</div><button id="update-price" class="secondary full-button">Update source price +$5</button><p class="control-hint" id="db-value">Database price: $24</p><button id="expire-cache" class="mini-action">Expire all cached copies ↗</button></div><div class="challenge"><strong>↳ FIND A STALE READ</strong><p>Fill the cache. Update the source price. Read again before expiry. Which price comes back?</p></div>`;
    $('#cache-key').onchange=e=>{state.key=e.target.value;$('#db-value').textContent=`Database price: $${state.db[state.key]}`;conditionChanged();};
    $('#ttl').oninput=e=>{state.ttl=Number(e.target.value);$('#ttl-value').value=`${state.ttl}s`;conditionChanged();};
    $('#update-price').onclick=()=>{state.db[state.key]+=5;$('#db-value').textContent=`Database price: $${state.db[state.key]}`;conditionChanged('Database updated. Existing cached copies have not changed.');};
    $('#expire-cache').onclick=()=>{state.cache={};conditionChanged('Cache expired. The next request takes the database path.');};
  }else{
    root.innerHTML=`<div class="control-group"><div class="segmented" aria-label="Operation"><button id="mode-create" class="selected" aria-pressed="true">Create a link</button><button id="mode-resolve" aria-pressed="false">Resolve a link</button></div><div id="create-fields"><label class="input-label" for="long-url">Destination URL</label><input class="text-input" id="long-url" type="url" value="${esc(state.longUrl)}"><label class="input-label" for="alias">Custom alias (optional)</label><input class="text-input" id="alias" maxlength="16" placeholder="e.g. my-guide"><p class="control-hint">Leave blank for a generated Base62 code.</p></div><div id="resolve-fields" hidden><label class="input-label" for="short-code">Short code</label><input class="text-input" id="short-code" value="learn01"><button id="use-last" class="mini-action">Use last created link ↗</button></div><div id="url-status" class="status-message" role="status">A sample link, learn01, is ready to resolve.</div></div><div class="control-group"><button id="cache-online" class="server-toggle" aria-pressed="true"><span>Cache available</span><span class="switch" aria-hidden="true"></span></button><button id="flush-url-cache" class="mini-action">Clear redirect cache ↗</button><p class="control-hint">Pause the cache to trace a direct database lookup.</p></div><div class="challenge"><strong>↳ CONNECT THE PIECES</strong><p>Create a link, then resolve its code twice. The second read can skip the database.</p></div>`;
    $('#long-url').oninput=e=>{state.longUrl=e.target.value;conditionChanged();};$('#alias').oninput=e=>{state.alias=e.target.value;conditionChanged();};$('#short-code').oninput=e=>{state.code=e.target.value;conditionChanged();};
    for(const mode of ['create','resolve'])$(`#mode-${mode}`).onclick=()=>{state.mode=mode;$('#create-fields').hidden=mode!=='create';$('#resolve-fields').hidden=mode!=='resolve';for(const m of ['create','resolve']){$(`#mode-${m}`).classList.toggle('selected',mode===m);$(`#mode-${m}`).setAttribute('aria-pressed',String(mode===m));}$('#short-code').value=state.code;conditionChanged();};
    $('#use-last').onclick=()=>{state.code=state.lastCreated;$('#short-code').value=state.code;conditionChanged('Ready to resolve the most recently created link.');};
    $('#cache-online').onclick=()=>{state.cacheOnline=!state.cacheOnline;$('#cache-online').setAttribute('aria-pressed',String(state.cacheOnline));conditionChanged(`Cache ${state.cacheOnline?'available':'unavailable'}.`);};
    $('#flush-url-cache').onclick=()=>{state.urlCache=Object.create(null);conditionChanged('Redirect cache cleared.');};
  }
}
function urlStatus(message,error=false){const el=$('#url-status');if(el){el.textContent=message;el.classList.toggle('error-text',error);}}
function narration(){
  if(phase<0)return ['Ready when you are',current.id==='load-balancing'?'Press Play to send traffic, or Step to follow one round at your own pace.':current.id==='caching'?'Press Play to trace a product lookup. The first read is cold; the next can reuse the cached copy.':'Choose Create or Resolve, then press Play or Step to trace the operation.'];
  if(current.id==='load-balancing'){
    const healthy=state.healthy.filter(Boolean).length;const routes=request.targets.map(i=>'ABC'[i]).join(' → ');
    return [
      ['Requests arrive',`${state.volume} request${state.volume===1?'':'s'} reach the public entry point. Clients do not choose a backend.`],
      ['Check the eligible pool',`${healthy} of 3 servers are healthy. ${healthy?'Offline servers are excluded before routing.':'No backend can serve this round; the balancer must fail fast.'}`],
      [healthy?'Choose a destination':'No healthy upstream',healthy?`${state.algorithm==='weighted'?'Weighted round robin':'Round robin'} assigns this round: ${routes}.`:'With every backend offline, these requests cannot be routed. A real proxy typically returns an unavailable response.'],
      [healthy?'Responses return':'Requests rejected',healthy?`${request.targets.length} requests completed. Distribution totals below include this round.`:`${state.volume} requests were rejected. Bring a server back online to restore service.`]
    ][phase];
  }
  if(current.id==='caching'){
    const product={book:'the book',course:'the course',notebook:'the notebook'}[request.key];
    return [
      ['Request a product',`Look up ${product} at simulated t = ${state.clock}s. Its database price is $${state.db[request.key]}.`],
      [request.hit?'Cache hit':'Cache miss',request.hit?`A valid cached copy exists. Its value is $${request.value}.${request.stale?' The database has changed: this is a stale read.':''}`:'No unexpired copy exists for this key. A cache miss is not the same as a missing product.'],
      [request.hit?'Skip the database':'Read the source of truth',request.hit?'The app can return the cached value without making a database read.':`Fetch the current price, $${request.value}, from the database. This is the expensive path.`],
      [request.hit?'Reuse the copy':'Fill the cache',request.hit?'The original expiry stays in place. This lab does not extend TTL on a read.':`Store the fetched value for ${state.ttl} simulated seconds, starting when this request finishes.`],
      ['Return the result',`Returned $${request.value} via ${request.hit?'the cache (5 ms)':'the database (55 ms)'}.${request.stale?' The cached result is stale; expiry or invalidation will refresh it.':''}`]
    ][phase];
  }
  if(request.mode==='create')return [
    ['POST /links','A create request arrives with a destination URL and an optional custom alias.'],
    ['Validate the destination','The URL must use HTTP or HTTPS. Real deployments also need abuse controls and ownership rules.'],
    ['Choose a short code',`This request claims “${request.code}”. Generated codes encode a local counter in Base62; they are predictable in this demo.`],
    [request.duplicate?'Alias already exists':'Claim the mapping',request.duplicate?'A conditional insert would reject this duplicate code. The existing destination stays intact.':`Store ${request.code} → the full destination in the simulated key-value store.`],
    [request.duplicate?'409 Conflict':'201 Created',request.duplicate?'Choose a different alias and retry. Uniqueness must be enforced by the storage layer.':`Your local demonstration code is ${request.code}. Switch to Resolve and follow its read path.`]
  ][phase];
  return [
    ['GET /{code}',`A reader requests “${request.code}”. The read service needs one exact-key lookup.`],
    [request.hit?'Cache hit':state.cacheOnline?'Cache miss':'Cache unavailable',request.hit?'A destination is already cached. No database read is needed.':state.cacheOnline?'This code is not cached yet. Fall back to the key-value store.':'Bypass the unavailable cache. Every cold read now reaches the database.'],
    [request.hit?'Skip storage':'Look up the mapping',request.hit?'Reuse the cached destination.':request.url?'The key-value store found the original URL.':'No record exists for this code. Return a not-found response.'],
    [request.url?'Prepare the response':'Prepare a 404',request.url?`${!request.hit&&state.cacheOnline?'Populate the cache for future requests. ':''}Prepare a temporary redirect with the destination in Location.`:'Do not cache a successful redirect for a missing mapping.'],
    [request.url?'302 Found':'404 Not Found',request.url?`Location: ${request.url}. This is a simulated response; the lesson stays open.`:'The requested short code is unknown. Try learn01 or create a new mapping.']
  ][phase];
}
function node(id,x,y,title,subtitle,icon,active=false,down=false,w=106){
  return `<g class="node ${active?'active':''} ${down?'down':''}" transform="translate(${x} ${y})"><rect class="node-box" x="${-w/2}" y="-35" width="${w}" height="70" rx="9"/><text class="node-icon" y="-10" text-anchor="middle">${esc(icon)}</text><text class="node-title" y="9" text-anchor="middle">${esc(title)}</text><text class="node-sub" y="25" text-anchor="middle">${esc(subtitle)}</text></g>`;
}
function wire(points,active=false){return `<polyline class="wire ${active?'active':''}" points="${points.map(p=>p.join(',')).join(' ')}"/>`;}
function renderDiagram(){
  const id=current.id;let inner='',paths=[];
  if(id==='load-balancing'){
    const ys=[62,150,238];const targets=request?.targets||[];const activeTargets=new Set(phase>=2?targets:[]);
    inner=`<text x="74" y="25" text-anchor="middle" class="diagram-label">PUBLIC INTERNET</text><text x="259" y="25" text-anchor="middle" class="diagram-label">ROUTING LAYER</text><text x="459" y="18" text-anchor="middle" class="diagram-label">BACKEND POOL</text>`;
    inner+=wire([[127,150],[204,150]],phase===0);
    ys.forEach((y,i)=>inner+=wire([[314,150],[354,150],[354,y],[404,y]],phase>=2&&activeTargets.has(i)));
    inner+=node('client',74,150,'Clients',`${state.volume} per round`,'▣',phase===0);
    inner+=node('lb',259,150,'Balancer',state.algorithm==='weighted'?'weights 2 : 1 : 1':'round robin','⇄',phase===1);
    ys.forEach((y,i)=>inner+=node('s'+i,459,y,'Server '+'ABC'[i],state.healthy[i]?`${state.counts[i]} served`:'offline','▤',activeTargets.has(i)&&phase>=2,!state.healthy[i]));
    if(phase===0)paths=[[[127,150],[204,150]]];
    if(phase===2)paths=targets.slice(0,8).map(i=>[[314,150],[354,150],[354,ys[i]],[404,ys[i]]]);
    if(phase===3)paths=[...new Set(targets)].map(i=>[[404,ys[i]],[354,ys[i]],[354,150],[127,150]]);
  }else if(id==='caching'){
    const hit=request?.hit;const cached=state.cache[state.key];const valid=cached&&cached.expires>state.clock;
    inner=`<text x="85" y="57" text-anchor="middle" class="diagram-label">APPLICATION</text><text x="280" y="57" text-anchor="middle" class="diagram-label">FAST COPY</text><text x="477" y="57" text-anchor="middle" class="diagram-label">SOURCE OF TRUTH</text>`;
    inner+=wire([[140,145],[225,145]],phase===0||phase===4);
    // Cache-aside: the application reads the DB; the cache does not fetch for it.
    inner+=wire([[85,180],[85,225],[477,225],[477,180]],phase===2&&!hit);
    inner+=node('app',85,145,'App',phase===4?`returned $${request.value}`:'product lookup','▣',phase===0||phase===4, false,110);
    inner+=node('cache',280,145,'Cache',valid?`$${cached.value} · ${Math.max(0,cached.expires-state.clock)}s left`:'empty / expired','▥',phase===1||phase===3,false,110);
    inner+=node('db',477,145,'Database',`price: $${state.db[state.key]}`,'▰',phase===2&&!hit,false,110);
    inner+=`<text x="281" y="250" text-anchor="middle" class="diagram-label">APP READS DATABASE ON A MISS</text><text x="281" y="94" text-anchor="middle" class="node-sub">simulated clock · ${state.clock}s</text>`;
    if(phase===0)paths=[[[140,145],[225,145]]];
    if(phase===1)paths=[[[225,145],[140,145]]];
    if(phase===2&&!hit)paths=[[[85,180],[85,225],[477,225],[477,180]]];
    if(phase===2&&hit)paths=[[[225,145],[140,145]]];
    if(phase===3&&!hit)paths=[[[477,180],[477,225],[85,225],[85,180]],[[140,145],[225,145]]];
    if(phase===4)paths=[[[225,145],[140,145]]];
  }else{
    const creating=(request?.mode||state.mode)==='create';const hit=request?.hit;
    inner=`<text x="69" y="27" text-anchor="middle" class="diagram-label">CLIENT</text><text x="256" y="27" text-anchor="middle" class="diagram-label">APPLICATION</text><text x="458" y="27" text-anchor="middle" class="diagram-label">DATA LAYER</text>`;
    inner+=wire([[122,150],[201,150]],phase===0||phase===4);
    inner+=wire([[311,150],[351,150],[351,83],[403,83]],!creating&&phase===1);
    inner+=wire([[311,150],[351,150],[351,221],[403,221]],creating&&phase===3||!creating&&phase===2&&!hit);
    inner+=node('client',69,150,'Client',creating?'POST /links':'GET /{code}','▣',phase===0||phase===4);
    inner+=node('service',256,150,creating?'Write service':'Read service',creating?'validate · claim':'lookup · redirect','⇄',phase===1||phase===2);
    inner+=node('cache',458,83,'Cache',state.cacheOnline?`${Object.keys(state.urlCache).length} entries`:'unavailable','▥',!creating&&phase===1,!state.cacheOnline);
    inner+=node('kv',458,221,'KV store',`${Object.keys(state.links).length} mappings`,'▰',creating&&phase===3||!creating&&phase===2&&!hit);
    if(phase===0)paths=[[[122,150],[201,150]]];
    if(!creating&&phase===1&&state.cacheOnline)paths=[[[311,150],[351,150],[351,83],[403,83]]];
    if(!creating&&phase===2&&!hit||creating&&phase===3)paths=[[[311,150],[351,150],[351,221],[403,221]]];
    if(!creating&&phase===2&&hit)paths=[[[403,83],[351,83],[351,150],[311,150]]];
    if(phase===4)paths=[[[201,150],[122,150]]];
  }
  $('#diagram').innerHTML=`<svg viewBox="0 0 550 290" role="img" aria-labelledby="svg-title svg-description"><title id="svg-title">${esc(current.diagram)}</title><desc id="svg-description">${esc(narration().join('. '))}</desc>${inner}<g id="packets" aria-hidden="true"></g></svg><div class="diagram-key"><span><i></i>Active path</span><span><i></i>Available connection</span></div>`;
  animatePackets(paths);
}
function animatePackets(paths){
  cancelAnimationFrame(animation);const generation=++animationGeneration;const group=$('#packets');if(!group||!paths.length)return;
  const circles=paths.map(()=>{const c=document.createElementNS('http://www.w3.org/2000/svg','circle');c.setAttribute('r','4');c.setAttribute('class','packet');group.append(c);return c;});
  const lengths=paths.map(points=>points.slice(1).map((p,i)=>Math.hypot(p[0]-points[i][0],p[1]-points[i][1])));
  function pointAt(points,lens,t){let distance=lens.reduce((a,b)=>a+b,0)*t;for(let i=0;i<lens.length;i++){if(distance<=lens[i]||i===lens.length-1){const f=lens[i]?Math.min(1,distance/lens[i]):0;return [points[i][0]+(points[i+1][0]-points[i][0])*f,points[i][1]+(points[i+1][1]-points[i][1])*f];}distance-=lens[i];}return points[0];}
  const duration=Number($('#speed').value)*.8;const start=performance.now();
  function frame(now){if(generation!==animationGeneration)return;const t=reduced?.65:Math.min(1,(now-start)/duration);circles.forEach((c,i)=>{const p=pointAt(paths[i],lengths[i],Math.max(0,Math.min(1,t-i*.025)));c.setAttribute('cx',p[0]);c.setAttribute('cy',p[1]);});if(!reduced&&t<1)animation=requestAnimationFrame(frame);}
  frame(start);
}
function metric(label,value,note,emphasis=false){return `<div class="metric ${emphasis?'emphasis':''}"><div class="metric-label">${esc(label)}</div><strong>${esc(value)}</strong><small>${esc(note)}</small></div>`;}
function renderMetrics(){
  if(current.id==='load-balancing'){
    $('#metrics').innerHTML=metric('REQUESTS SERVED',fmt(state.total),'Completed across all rounds')+metric('HEALTHY SERVERS',`${state.healthy.filter(Boolean).length} / 3`,'Eligible for new requests',true)+metric('TRAFFIC SPLIT',state.counts.join(' / '),'Cumulative · A / B / C')+metric('REQUESTS REJECTED',fmt(state.rejected),'Rounds with no healthy backend');
    state.counts.forEach((n,i)=>{const el=$(`#count-${i}`);if(el)el.textContent=`· ${n} requests`;});
  }else if(current.id==='caching'){
    const count=state.hits+state.misses;
    $('#metrics').innerHTML=metric('CACHE HIT RATE',count?`${Math.round(state.hits/count*100)}%`:'—','Measured over completed reads',true)+metric('DATABASE READS',fmt(state.misses),'One read for every cache miss')+metric('MODEL AVG. LATENCY',count?`${((state.hits*5+state.misses*55)/count).toFixed(1)} ms`:'—','Illustrative · 5 ms hit / 55 ms miss')+metric('STALE READS',fmt(state.stale),'Cached value differed from source');
  }else{
    $('#metrics').innerHTML=metric('LINKS CREATED',fmt(state.created),'Excludes the seeded sample link')+metric('REDIRECTS RESOLVED',fmt(state.resolved),'Successful simulated 302 responses',true)+metric('DATABASE READS',fmt(state.dbReads),'Includes not-found lookups')+metric('CACHED MAPPINGS',fmt(Object.keys(state.urlCache).length),state.cacheOnline?'Cache is available':'Cache is currently bypassed');
  }
}
function render(){
  renderDiagram();renderMetrics();const [title,description]=narration();
  $('#step-title').textContent=title;$('#step-description').textContent=description;$('#step-number').textContent=phase<0?'→':String(phase+1).padStart(2,'0');
  $('#timeline').innerHTML=stages[current.id].map((s,i)=>`<button tabindex="-1" disabled title="${esc(s)}" aria-label="Step ${i+1}: ${esc(s)}" class="${i===phase?'current':i<phase?'past':''}" ${i===phase?'aria-current="step"':''}></button>`).join('');
}
function renderUnderstand(){
  const root=$('#panel-understand');
  root.innerHTML=`<div class="reading-grid"><article class="reading-card wide"><span class="eyebrow">START WITH AN ANALOGY</span><p class="analogy">${esc(current.analogy)}</p></article>${current.cards.map(([tag,title,body],i)=>`<article class="reading-card"><span class="eyebrow">0${i+1} / ${esc(tag.toUpperCase())}</span><h2>${esc(title)}</h2><p>${esc(body)}</p></article>`).join('')}${current.id==='url-shortener'?scalePanel():`<article class="reading-card wide"><span class="eyebrow">EXPERIMENT WITH INTENT</span><h2>${current.id==='caching'?'Can you make both a hit and a stale hit?':'Can you predict the next destination?'}</h2><p>${current.id==='caching'?'Read the same key twice, change its source price, and read it again. Then expire the cached copy. Explain which requests reached the database and why.':'Run two rounds, change the algorithm, then disable a server. Predict the next round before pressing Step. Compare new assignments with the cumulative counts.'}</p></article>`}</div><div class="reading-actions"><button class="secondary" id="back-to-lab">← Back to experiment</button><button class="primary" id="go-quiz">Check my understanding →</button><a class="text-button" target="_blank" rel="noopener" href="${current.source}#page=${current.page}">Read the original source ↗</a></div>`;
  $('#back-to-lab').onclick=()=>switchTab('experiment');$('#go-quiz').onclick=()=>switchTab('check');
  if(current.id==='url-shortener')bindScale();
}
function scalePanel(){return `<article class="reading-card wide"><span class="eyebrow">FROM FOUNDATION TO FAILURE MODES</span><h2>How much work reaches the database?</h2><div class="mini-levels"><button data-level="0" class="selected">L1 · Shape</button><button data-level="1">L2 · Scale</button><button data-level="2">L3 · Failure</button></div><p id="level-copy">Start with client → service → key-value store. A code maps to a full URL. Split create and resolve responsibilities before adding infrastructure.</p><div class="reading-grid">${rangeControl('daily-links','New links per day',state.linksPerDay,1,200,' M')}${rangeControl('read-ratio','Reads per write',state.readRatio,1,200,'×')}${rangeControl('hit-rate','Assumed cache hit rate',state.hitRate,0,100,'%')}</div><table class="model-table"><thead><tr><th>Estimate</th><th>Result</th><th>Calculation</th></tr></thead><tbody id="capacity-results"></tbody></table><p class="control-hint">Assumptions: uniform average writes, 3× peak reads, 500 bytes per link, 365 days per year, five-year retention. Storage uses decimal TB; replication and indexes are excluded.</p></article>`;}
function bindScale(){
  const copies=[
    'Start with client → service → key-value store. A code maps to a full URL. Split create and resolve responsibilities before adding infrastructure.',
    'At scale, read traffic dominates. Add a cache for popular codes. Keep click analytics asynchronous so counting a click does not block the redirect.',
    'Try setting the hit rate to 0% to model total cache failure. The database must absorb every read unless the system limits traffic or degrades safely. A failure plan matters as much as the happy path.'
  ];
  $$('[data-level]').forEach(b=>b.onclick=()=>{level=Number(b.dataset.level);$$('[data-level]').forEach(x=>x.classList.toggle('selected',x===b));$('#level-copy').textContent=copies[level];});
  for(const [id,key,suffix] of [['daily-links','linksPerDay',' M'],['read-ratio','readRatio','×'],['hit-rate','hitRate','%']])$(`#${id}`).oninput=e=>{state[key]=Number(e.target.value);$(`#${id}-value`).value=state[key]+suffix;updateCapacity();};
  updateCapacity();
}
function updateCapacity(){const writes=state.linksPerDay*1e6/86400;const reads=writes*state.readRatio*3;const rows=[['Average writes',`${fmt(writes)} /s`,'daily links ÷ 86,400'],['Peak reads',`${fmt(reads)} /s`,'writes × read ratio × 3'],['Database reads',`${fmt(reads*(1-state.hitRate/100))} /s`,'peak reads × cache miss fraction'],['Raw storage, 5 years',`${(state.linksPerDay*1e6*500*365*5/1e12).toFixed(2)} TB`,'daily links × 500 B × 365 × 5']];$('#capacity-results').innerHTML=rows.map(r=>`<tr>${r.map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`).join('');}
function renderQuiz(){
  $('#quiz-dot').classList.toggle('complete',!!progress[current.id]);
  $('#panel-check').innerHTML=`<p class="quiz-intro">Three questions to make the idea stick. Choose an answer to see the reasoning. Get all three right to complete the lesson.</p>${current.quiz.map((q,i)=>`<article class="quiz-card"><span class="eyebrow">QUESTION 0${i+1} / 03</span><h3>${esc(q.q)}</h3><div class="quiz-options">${q.options.map((option,j)=>`<button class="quiz-option" data-q="${i}" data-answer="${j}" aria-pressed="false"><span>${'ABC'[j]}</span>${esc(option)}</button>`).join('')}</div><div class="quiz-feedback" id="feedback-${i}" aria-live="polite"></div></article>`).join('')}<div id="quiz-result"></div>`;
  $$('[data-answer]').forEach(b=>b.onclick=()=>{
    const i=Number(b.dataset.q),choice=Number(b.dataset.answer),q=current.quiz[i];answers[i]=choice;
    $$(`[data-q="${i}"]`).forEach(option=>{const selected=Number(option.dataset.answer)===choice;option.classList.toggle('correct',selected&&choice===q.answer);option.classList.toggle('incorrect',selected&&choice!==q.answer);option.setAttribute('aria-pressed',String(selected));});
    $(`#feedback-${i}`).textContent=`${choice===q.answer?'✓ Correct.':'Try again.'} ${q.why}`;
    const answered=Object.keys(answers).length;const correct=current.quiz.filter((q,i)=>answers[i]===q.answer).length;
    if(answered===3){$('#quiz-result').innerHTML=`<div class="quiz-result">${correct===3?'✓ Lesson complete. You can explain the idea and its trade-offs.':`${correct} / 3 correct. Review the explanations and try another answer.`}${correct===3?'<button class="text-button" id="quiz-next">Next lesson →</button>':''}</div>`;if(correct===3){progress[current.id]=true;storage.write('enterview-progress-v1',progress);renderNav();$('#quiz-dot').classList.add('complete');$('#quiz-next').onclick=nextLesson;}}
  });
}
function nextLesson(){selectLesson(LESSONS[(LESSONS.indexOf(current)+1)%LESSONS.length].id);window.scrollTo({top:0,behavior:reduced?'instant':'smooth'});}
function openLibrary(){stop();$('#library-dialog').showModal();$('#library-search').value='';renderLibrary();$('#library-search').focus();}
function renderLibrary(){
  const query=$('#library-search').value.toLowerCase().trim();const rows=LIBRARY.filter(l=>(libraryFilter==='all'||l.type===libraryFilter)&&l.title.toLowerCase().includes(query));
  $('#library-results').innerHTML=rows.length?rows.map(l=>`<div class="library-row"><span>${String(LIBRARY.indexOf(l)+1).padStart(2,'0')}</span><div><h3>${esc(l.title)}</h3><small>${l.type==='concept'?'Core concept':'Design problem · L1–L3'} · ${l.end===l.page?'page '+l.page:'pages '+l.page+'–'+l.end}</small></div>${l.lab?`<button data-library-lesson="${l.lab}">Open lab</button>`:''}<a href="${l.source}#page=${l.page}" target="_blank" rel="noopener">Read PDF ↗</a></div>`).join(''):'<p class="empty">No matching topics. Try “cache”, “chat”, or “scaling”.</p>';
  $$('[data-library-lesson]').forEach(b=>b.onclick=()=>{$('#library-dialog').close();selectLesson(b.dataset.libraryLesson);});
}
$('#lesson-nav').onclick=e=>{const b=e.target.closest('[data-lesson]');if(b)selectLesson(b.dataset.lesson);};
$$('[data-tab]').forEach(b=>b.onclick=()=>switchTab(b.dataset.tab));
$('.tabs').onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const names=['experiment','understand','check'];let i=names.indexOf(tab);i=e.key==='Home'?0:e.key==='End'?2:(i+(e.key==='ArrowRight'?1:2))%3;switchTab(names[i]);$(`#tab-${names[i]}`).focus();};
$('#play').onclick=togglePlay;$('#step').onclick=()=>{stop();advance();};$('#reset').onclick=reset;$('#speed').onchange=()=>{if(playing)schedule();};
$('#understand-next').onclick=()=>switchTab('understand');$('#next-lesson').onclick=nextLesson;
$('#open-library').onclick=openLibrary;$('#browse-docs').onclick=openLibrary;$('#close-library').onclick=()=>$('#library-dialog').close();
$('#library-search').oninput=renderLibrary;
$('#library-dialog').addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();$('#library-dialog').close();}},true);
$$('[data-filter]').forEach(b=>b.onclick=()=>{libraryFilter=b.dataset.filter;$$('[data-filter]').forEach(x=>x.classList.toggle('selected',x===b));renderLibrary();});
$('#library-dialog').addEventListener('click',e=>{if(e.target!==$('#library-dialog'))return;const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();});
$('#motion-toggle').onclick=()=>{reduced=!reduced;storage.write('enterview-reduced-motion',reduced);setMotion();renderDiagram();};
matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',e=>{if(e.matches){reduced=true;setMotion();renderDiagram();}});
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&!$('#library-dialog').open){e.preventDefault();openLibrary();}});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
window.addEventListener('hashchange',()=>selectLesson(location.hash.slice(1),false));
setMotion();selectLesson(location.hash.slice(1)||'load-balancing',false);
