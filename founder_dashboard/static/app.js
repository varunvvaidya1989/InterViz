'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const url = value => { try { const u = new URL(value); return u.protocol === 'https:' && u.hostname === 'github.com' ? esc(u.href) : '#'; } catch { return '#'; } };
const link = (value, text) => `<a href="${url(value)}" target="_blank" rel="noopener noreferrer">${esc(text)}</a>`;
const names = {ready:'Ready',running:'Running',reviewing:'In review',rework:'Rework',blocked:'Blocked',waiting:'Dependency wait',integrated:'Integrated',in_progress:'Running',queued:'Queued',pending:'Pending',waiting_run:'Waiting',success:'Passed',failure:'Failed',action_required:'Approval needed',cancelled:'Cancelled',timed_out:'Timed out',skipped:'Skipped',neutral:'Neutral'};
const roles = {'coding':'Coding','devops':'DevOps','lead':'Lead','ui-ux':'UI / UX','qa':'QA'};
const badge = (state, label) => `<span class="pill ${esc(state)}">${esc(label || names[state] || state.replaceAll('_',' '))}</span>`;
let data = null, currentView = 'overview', board = false, selectedTask = null, refreshing = false;
function ago(value) { const seconds = Math.max(0, Math.floor((Date.now() - (typeof value === 'number' ? value * 1000 : Date.parse(value))) / 1000)); if (!Number.isFinite(seconds)) return 'Unknown'; if(seconds < 60) return `${seconds}s ago`; if(seconds < 3600) return `${Math.floor(seconds/60)}m ago`; if(seconds < 86400) return `${Math.floor(seconds/3600)}h ago`; return `${Math.floor(seconds/86400)}d ago`; }
function localTime(value) { return new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(typeof value === 'number' ? value*1000 : value)); }
function showView(view) {currentView = view;document.querySelectorAll('.view').forEach(x=>x.hidden=x.id !== view+'-view');document.querySelectorAll('nav .nav').forEach(x=>x.classList.toggle('active',x.dataset.view===view));const titles={overview:['Overview','Your release, in focus.','A clear view of the work, the agents, and what needs you.'],work:['Work items','From direction to delivery.','The current approved scope, with dependencies and evidence in one place.'],agents:['Agent activity','Know what’s happening.','Live workflow steps, elapsed time, and links to the evidence.'],timeline:['Timeline','Every step, accounted for.','A chronological record of controller decisions and release progress.']};$('page-name').textContent=titles[view][0];$('page-title').textContent=titles[view][1];$('page-subtitle').textContent=titles[view][2];}
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
function table(tasks) { if(!tasks.length)return '<div class="empty">No work items match this view.</div>'; return `<div class="table-scroll"><table><thead><tr><th>Work item</th><th>Agent</th><th>Status</th><th>Attempts</th><th>Updated</th><th></th></tr></thead><tbody>${tasks.map(t=>`<tr><td class="task-name"><button class="task-open" data-task="${esc(t.release_id+':'+t.id)}"><small>${esc(t.id)}</small><strong>${esc(t.title)}</strong></button></td><td><span class="role"><span class="role-dot"></span>${esc(roles[t.role]||t.role)}</span></td><td>${badge(t.state)}</td><td>${t.attempts} / ${t.max_attempts}</td><td>${esc(ago(t.updated_at))}</td><td><button class="task-open task-arrow" data-task="${esc(t.release_id+':'+t.id)}" aria-label="Open ${esc(t.id)}">↗</button></td></tr>`).join('')}</tbody></table></div>`; }
function agentCards(runs) {return runs.length ? runs.map(r=>`<article class="agent-card"><div class="agent-card-top"><span class="agent-icon">⌘</span>${badge(r.status === 'in_progress'?'running':'waiting',r.status==='in_progress'?'Active':'Queued')}</div><h3>${esc(r.title)}</h3><p>${esc(r.step)}</p><div class="agent-card-bottom"><span>Started ${esc(ago(r.started_at))}</span>${link(r.url,'View run ↗')}</div></article>`).join('') : '<div class="agent-idle">No workflows are active right now.<p>Open work may be waiting on dependencies, review, or the next controller pulse.</p></div>'; }
function render() {
  if(!data)return;
  $('loading').hidden=true;$('content').hidden=false;$('nav-count').textContent=data.tasks.length;
  $('repo-name').textContent=data.repository.split('/')[1];
  const tasks=data.tasks, total=tasks.length, done=tasks.filter(t=>t.state==='integrated').length, working=tasks.filter(t=>['running','reviewing','rework'].includes(t.state)).length;
  const metrics=[['Approved work items',total,'Current ledger · excludes older tickets','▤',''],['Integrated',done,`${total ? Math.round(done/total*100):0}% of approved implementation work`,'✓',''],['Work in motion',working,`${data.running.length} active or queued workflows`,'⌘',''],['Needs attention',data.attention.length,'Decisions, failures & recovery','!','alert']];
  $('metrics').innerHTML=metrics.map(([label,value,note,symbol,cls])=>`<article class="metric ${cls}"><span class="metric-label">${label}</span><span class="metric-symbol">${symbol}</span><div class="metric-value">${value.toString().padStart(2,'0')}</div><div class="metric-note">${esc(note)}</div></article>`).join('');
  const release=data.releases.find(r=>r.state!=='RELEASED')||data.releases[0];
  if(release){$('release-id').textContent=release.id;$('release-title').textContent=release.title;$('release-description').textContent='Approved scope → reviewed code → verified candidate';$('release-badge').className='pill '+(release.state==='BUILDING'?'running':'ready');$('release-badge').textContent=release.state.replaceAll('_',' ');const approved=release.plan_approved_hash && release.plan_approved_hash===release.plan_hash;let stage=approved?1:0;if(release.state==='QA')stage=2;if(release.qa_passed)stage=3;if(release.state==='RELEASED')stage=4;$('pipeline').innerHTML=['Plan','Build','QA','Approval','Release'].map((s,i)=>`<div class="stage ${i<stage?'done':i===stage?'current':''}"><span>${i<stage?'✓':i+1}</span>${s}</div>`).join('');$('progress-text').textContent=`${done} of ${total} work items integrated`;$('progress-percent').textContent=`${total?Math.round(done/total*100):0}%`;$('progress-fill').style.width=`${total?done/total*100:0}%`;$('approval-note').textContent=approved?'✓ Plan approved by '+release.plan_approved_by:'Awaiting current-plan approval';$('plan-link').href=release.plan_url||'https://github.com/'+data.repository+'/pulls';}
  $('attention-count').textContent=data.attention.length;
  $('attention-list').innerHTML=data.attention.length?data.attention.map(a=>`<article class="attention-item ${esc(a.severity)}"><span class="attention-symbol">!</span><div><strong>${esc(a.title)}</strong><p>${esc(a.reason)}</p>${a.url?link(a.url,'Open evidence ↗'):''}</div></article>`).join(''):'<div class="empty">No attention flags detected in the latest snapshot.</div>';
  $('agent-preview').innerHTML=agentCards(data.running.slice(0,3));$('agent-full').innerHTML=agentCards(data.running);
  const priority={rework:0,blocked:1,running:2,reviewing:3,ready:4,waiting:5,integrated:6};
  $('work-preview').innerHTML=table([...tasks].sort((a,b)=>priority[a.state]-priority[b.state]).slice(0,5));
  $('run-history').innerHTML=`<div class="table-scroll"><table><thead><tr><th>Workflow</th><th>Result</th><th>Started · IST</th><th>Evidence</th></tr></thead><tbody>${data.recent_runs.map(r=>`<tr><td class="task-name"><strong>${esc(r.title)}</strong><small>#${r.id}</small></td><td>${badge(r.conclusion==='success'?'integrated':r.conclusion==='failure'?'blocked':r.status==='in_progress'?'running':'waiting',names[r.conclusion]||names[r.status]||r.status)}</td><td>${esc(localTime(r.created_at))}</td><td>${link(r.url,'View run ↗')}</td></tr>`).join('')}</tbody></table></div>`;
  $('timeline').innerHTML=data.events.length?data.events.map(e=>`<article class="timeline-event"><span class="timeline-dot"></span><div><strong>${esc(e.type.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase()))}</strong><p>${esc(e.release_id)} · ${esc(e.actor)}</p></div><time>${esc(localTime(e.created_at))}</time></article>`).join(''):'<div class="empty">No controller events yet.</div>';
  $('source-note').textContent='Ledger saved '+ago(data.ledger_updated_at);
  renderWork();bindTasks();
}
function renderWork(){if(!data)return;const search=$('search').value.toLowerCase(),status=$('status-filter').value,role=$('role-filter').value;const tasks=data.tasks.filter(t=>(status==='all'||t.state===status)&&(role==='all'||t.role===role)&&`${t.id} ${t.title}`.toLowerCase().includes(search));if(board){const columns=[['ready','Ready'],['running','Running'],['reviewing','In review'],['rework','Needs action'],['waiting','Dependency wait'],['integrated','Integrated']];$('work-results').innerHTML='<div class="board">'+columns.map(([state,label])=>{const items=tasks.filter(t=>state==='rework'?['rework','blocked'].includes(t.state):t.state===state);return `<section class="board-column"><h3>${label}<span>${items.length}</span></h3>${items.map(t=>`<button class="board-card" data-task="${esc(t.release_id+':'+t.id)}"><small>${esc(t.id)}</small><p>${esc(t.title)}</p>${badge(t.state)}</button>`).join('')}${!items.length?'<span class="subtle">No matching work</span>':''}</section>`;}).join('')+'</div>';}else{$('work-results').innerHTML=table(tasks);} $('legacy-note').textContent=`Showing ${tasks.length} of ${data.tasks.length} current work items. ${data.legacy_issues.length} open tickets are not in the current ledger and are excluded from progress. Running tasks appear after the controller saves its next snapshot.`;bindTasks();}
function bindTasks(){document.querySelectorAll('[data-task]').forEach(b=>{b.onclick=()=>openTask(b.dataset.task);});}
function openTask(key){const task=data.tasks.find(t=>t.release_id+':'+t.id===key);if(!task)return;selectedTask=key;$('task-detail').innerHTML=`<p class="subtle">${esc(task.release_id)} / ${esc(task.id)}</p><h2 class="detail-title">${esc(task.title)}</h2><div class="detail-status">${badge(task.state)}<p>${esc(task.reason)}</p></div><div class="detail-grid"><div><small>Assigned role</small><strong>${esc(roles[task.role]||task.role)}</strong></div><div><small>Attempts used</small><strong>${task.attempts} of ${task.max_attempts}</strong></div><div><small>Category</small><strong>${esc(task.category)}</strong></div><div><small>Updated</small><strong>${esc(localTime(task.updated_at))}</strong></div>${task.lease_until?`<div><small>Lease ends</small><strong>${esc(localTime(task.lease_until))}</strong></div>`:''}</div>${task.review_summary?`<section class="detail-section"><h3>Latest review</h3><pre>${esc(task.review_summary)}</pre></section>`:''}<section class="detail-section"><h3>Acceptance criteria</h3><ul>${task.acceptance.map(a=>`<li>${esc(a)}</li>`).join('')}</ul></section><section class="detail-section"><h3>Dependencies</h3><p>${esc(task.depends_on.join(', ')||'No prerequisites')}</p><h3>Allowed paths</h3><p>${task.paths.map(esc).join('<br>')}</p></section><div class="detail-links">${task.issue_url?link(task.issue_url,'View ticket ↗'):''}${task.pr_url?link(task.pr_url,'View pull request ↗'):''}</div>`;$('task-dialog').showModal();}
$('close-dialog').onclick=()=>$('task-dialog').close();$('task-dialog').addEventListener('click',e=>{if(e.target===$('task-dialog')){const b=$('task-dialog').getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)$('task-dialog').close();}});
['search','status-filter','role-filter'].forEach(id=>$(id).addEventListener(id==='search'?'input':'change',renderWork));
function setBoard(value){board=value;$('table-toggle').classList.toggle('selected',!value);$('board-toggle').classList.toggle('selected',value);$('table-toggle').setAttribute('aria-pressed',String(!value));$('board-toggle').setAttribute('aria-pressed',String(value));renderWork();}
$('table-toggle').onclick=()=>setBoard(false);$('board-toggle').onclick=()=>setBoard(true);

let approvalStrings = {}, approvalCsrf = '', approvalRequests = {}, approvalRenderingKey = '';
const approvalLocal = {};
const at = key => approvalStrings[key] || key;
function readableValue(value) {
  if(value == null)return '';
  if(Array.isArray(value))return `<ul class="approval-structured">${value.map(x=>`<li>${readableValue(x)}</li>`).join('')}</ul>`;
  if(typeof value === 'object')return `<ul class="approval-structured">${Object.entries(value).map(([key,v])=>`<li><strong>${esc(key.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase()))}:</strong> ${readableValue(v)}</li>`).join('')}</ul>`;
  return esc(value);
}
function approvalResult(request) {
  if(!request)return '';
  let key='approval.'+request.state;
  if(request.error)key='approval.error.'+request.error;
  return `<div class="approval-result ${['failed','stale'].includes(request.state)?'error':''}">${esc(at(key))}${request.workflow_url?link(request.workflow_url,at('approval.workflow')):''}</div>`;
}
function renderApprovals() {
  if(!Object.keys(approvalStrings).length || !data)return;
  const options=data.approvals || {cards:[],can_approve:false,workflow_available:false};
  const cards=options.cards || [], requests={...approvalLocal,...approvalRequests};
  const next=JSON.stringify([options,requests,!!approvalCsrf]);
  if(next===approvalRenderingKey)return;
  approvalRenderingKey=next;
  $('workspace-mode').textContent=at('workspace.approvals');
  document.querySelectorAll('[data-approval-i18n]').forEach(el=>el.textContent=at(el.dataset.approvalI18n));
  $('approval-access').textContent=!options.workflow_available?at('approval.unavailable'):!options.can_approve?at('approval.account'):'';
  $('approval-cards').innerHTML=cards.length?cards.map(card=>{
    const request=requests[card.id], disabled=!options.can_approve || !approvalCsrf || ['submitting','requested','confirmed','stale'].includes(request?.state);
    const label=request?.state==='submitting'?'approval.submitting':request?.state==='requested'?'approval.requested':request?.state==='confirmed'?'approval.confirmed':request?.state==='failed'?'approval.retry':'approval.'+card.kind;
    const scope=card.kind==='plan'?`${(card.stories||[]).map(story=>`<h4>${esc(story.title)}</h4><ul>${(story.acceptance||[]).map(a=>`<li>${esc(a)}</li>`).join('')}</ul>`).join('')}${Object.entries(card.sections||{}).filter(([,value])=>value).map(([key,value])=>`<h4>${esc(at('approval.sections.'+key))}</h4><div class="approval-section-body">${readableValue(value)}</div>`).join('')}`:`<h4>${esc(at('approval.changes'))}</h4><p>${esc(card.changelog||'')}</p>`;
    return `<article class="approval-card" data-approval-card="${esc(card.id)}" tabindex="-1"><div class="approval-card-top"><div><h3>${esc(card.title)}</h3><p class="approval-summary">${esc(at('approval.'+card.kind+'_summary'))}</p></div><button class="approval-button" data-approve="${esc(card.id)}" ${disabled?'disabled':''}>${esc(at(label))}</button></div>${card.kind==='release'&&!card.publication_enabled?`<p class="approval-note">${esc(at('approval.publishing_disabled'))}</p>`:''}<details><summary>${esc(at('approval.'+card.kind+'_scope'))}</summary><div class="approval-scope">${scope}${card.url?link(card.url,at('approval.reference')):''}</div></details>${approvalResult(request)}</article>`;
  }).join(''):`<div class="approval-empty">${esc(at('approval.empty'))}</div>`;
  const activeIds=new Set(cards.map(c=>c.id));
  $('approval-feedback').innerHTML=Object.entries(requests).filter(([id,r])=>!activeIds.has(id)&&['confirmed','failed','stale','requested'].includes(r.state)).map(([,r])=>`<div class="approval-receipt">${approvalResult(r)}</div>`).join('');
  $('approval-cards').querySelectorAll('[data-approve]').forEach(button=>button.onclick=()=>submitApproval(button.dataset.approve));
}
async function submitApproval(id) {
  const card=data?.approvals?.cards?.find(c=>c.id===id);
  if(!card || !data.approvals.can_approve || !approvalCsrf)return;
  approvalLocal[id]={state:'submitting'};
  renderApprovals();
  try {
    const response=await fetch('/api/approve',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':approvalCsrf},body:JSON.stringify({kind:card.kind,release_id:card.release_id,expected_hash:card.expected_hash,revision:card.revision})});
    const result=await response.json();
    if(!response.ok) {
      const error=['invalid_session','founder_required','approval_changed','dispatch_failed'].includes(result.error)?result.error:'dispatch_failed';
      approvalLocal[id]={state:error==='approval_changed'?'stale':'failed',error};
    } else {
      approvalLocal[id]={...result,state:'requested'};
    }
  } catch {
    approvalLocal[id]={state:'failed',error:'dispatch_failed'};
  }
  renderApprovals();
  const container=document.querySelector(`[data-approval-card="${CSS.escape(id)}"]`);
  if(container)container.focus({preventScroll:true});
  await poll();
}
async function startDashboard() {
  try { const response=await fetch('/en.json');if(response.ok)approvalStrings=await response.json(); } catch {}
  await poll();
  setInterval(poll,4000);
}
async function poll(){try{const response=await fetch('/api/status');if(!response.ok)throw Error('Local server unavailable');const status=await response.json();approvalCsrf=status.csrf_token||'';approvalRequests=status.approval_requests||{};refreshing=status.refreshing;$('refresh').disabled=refreshing;$('sync-label').textContent=refreshing?'Syncing with GitHub…':status.data?'Updated '+ago(status.data.fetched_at):'Waiting for connection';if(status.data){const changed=!data||data.fetched_at!==status.data.fetched_at;data=status.data;if(changed)render();}renderApprovals();const age=data?Date.now()-Date.parse(data.fetched_at):0;const message=status.error||(age>180000?'Data is stale. Last successful refresh: '+localTime(data.fetched_at)+'. Showing the last known state.':data?.warnings?.join(' · '));$('error').hidden=!message;$('error').textContent=message||'';if(status.error&&!data){$('loading').innerHTML='<h2>Could not connect to GitHub</h2><p>Check local GitHub authentication and network access, then select Refresh.</p>';}}catch{$('error').hidden=false;$('error').textContent='The local dashboard server is unavailable. Restart it to refresh progress.';$('refresh').disabled=false;}}
$('refresh').onclick=async()=>{try{await fetch('/api/refresh',{method:'POST'});await poll();}catch{await poll();}};
startDashboard();
