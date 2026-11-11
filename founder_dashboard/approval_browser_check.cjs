// Synthetic browser checks only: no GitHub calls, approvals or workflow dispatches.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
let modulePath=process.env.PLAYWRIGHT_MODULE;
if(!modulePath){let location=__dirname;while(path.dirname(location)!==location){const candidate=path.join(location,'.tools/dashboard-qa/node_modules/playwright');if(fs.existsSync(candidate)){modulePath=candidate;break;}location=path.dirname(location);}}
const {chromium}=require(modulePath||'playwright');
const sha='a'.repeat(40),hash='b'.repeat(64),cardId='c'.repeat(64);
const plan={id:cardId,kind:'plan',release_id:'R-1',title:'Foundation delivery',expected_hash:hash,revision:sha,stories:[{title:'Account foundations',acceptance:['Sign in and set your background.','Keep the empty dashboard keyboard accessible.']}],sections:{architecture:'A typed application with server-authoritative decisions.',operations:{staging:'Review on desktop and phone.'}},url:'https://github.com/example/repo/pull/1'};
const now=()=>new Date().toISOString();
let status,mode='success',requests=[];
function fresh(card=plan){return {csrf_token:'fixture-csrf',approval_requests:{},refreshing:false,error:null,data:{repository:'example/repo',fetched_at:now(),ledger_updated_at:now(),tasks:[],releases:[{id:'R-1',title:'Foundation delivery',state:'PLAN_SUBMITTED',plan_hash:hash,plan_approved_hash:null}],running:[],recent_runs:[],attention:[],events:[],warnings:[],legacy_issues:[],approvals:{actor:'founder',can_approve:true,workflow_available:true,cards:[card]}}};}
const mime={'.html':'text/html','.css':'text/css','.js':'text/javascript','.json':'application/json'};
const server=http.createServer((req,res)=>{
 if(req.url==='/api/status'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify(status));return;}
 if(req.url==='/api/approve'){
  let body='';req.on('data',b=>body+=b);req.on('end',()=>{requests.push({body:JSON.parse(body),csrf:req.headers['x-csrf-token']});res.setHeader('Content-Type','application/json');if(mode==='stale'){res.writeHead(409);res.end(JSON.stringify({error:'approval_changed'}));}else if(mode==='failure'){res.writeHead(502);res.end(JSON.stringify({error:'dispatch_failed'}));}else{res.writeHead(202);res.end(JSON.stringify({state:'requested',requested_at:Date.now()/1000,workflow_url:'https://github.com/example/repo/actions/runs/1'}));}});return;
 }
 if(req.url==='/api/refresh'){res.writeHead(202);res.end('{}');return;}
 const names={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/en.json':'en.json'};
 const name=names[req.url];if(!name){res.writeHead(404);res.end();return;}
 res.setHeader('Content-Type',mime[path.extname(name)]);res.end(fs.readFileSync(path.join(__dirname,'static',name)));
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const address='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
 const page=await browser.newPage({viewport:{width:1440,height:1080}}),errors=[],external=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith(address+'/'))external.push(r.url());});
 try{
  status=fresh();await page.goto(address);await page.getByRole('button',{name:'Approve plan',exact:true}).waitFor();
  assert((await page.locator('#approvals-panel').innerText()).includes('No command comments needed'));
  assert(!(await page.locator('#approvals-panel').innerText()).includes(hash));
  assert(!(await page.locator('#approvals-panel').innerText()).includes(sha));
  await page.getByText('Review plan details',{exact:true}).click();
  assert((await page.locator('.approval-scope').innerText()).includes('Sign in and set your background.'));
  assert((await page.locator('.approval-scope').innerText()).includes('Review on desktop and phone.'));
  const approve=page.getByRole('button',{name:'Approve plan',exact:true});await approve.focus();await page.keyboard.press('Enter');
  await page.getByRole('button',{name:'Approval requested. Waiting for the controller to confirm.',exact:true}).waitFor();
  assert.equal(requests.length,1);assert.deepEqual(requests[0],{body:{kind:'plan',release_id:'R-1',expected_hash:hash,revision:sha},csrf:'fixture-csrf'});
  assert.equal(await page.getByRole('button',{name:'Approval requested. Waiting for the controller to confirm.',exact:true}).isDisabled(),true);
  assert(!(await page.locator('#approval-cards').innerText()).includes('Approval recorded by the controller.'));
  // Only confirmed controller evidence changes the requested state to approved.
  status.approval_requests[cardId]={state:'confirmed',workflow_url:'https://github.com/example/repo/actions/runs/1'};status.data.approvals.cards=[];status.data.releases[0].plan_approved_hash=hash;status.data.fetched_at=now();
  await page.evaluate(()=>poll());await page.getByText('Approval recorded by the controller.',{exact:false}).waitFor();
  // A newer target cannot inherit the previous request; stale errors stay visible.
  mode='stale';const next={...plan,id:'d'.repeat(64),expected_hash:'e'.repeat(64)};status=fresh(next);await page.reload();await page.getByRole('button',{name:'Approve plan',exact:true}).click();
  await page.getByText('This approval changed or was already recorded. Refresh the dashboard before trying again.',{exact:true}).waitFor();
  assert(await page.getByRole('button',{name:'Approve plan',exact:true}).isDisabled());
  // Dispatch/network failure is not a success and permits an explicit retry.
  mode='failure';status=fresh({...plan,id:'f'.repeat(64)});await page.reload();await page.getByRole('button',{name:'Approve plan',exact:true}).click();
  await page.getByText('The approval request could not be sent. Check your connection and try again.',{exact:true}).waitFor();assert(!(await page.getByRole('button',{name:'Retry approval',exact:true}).isDisabled()));
  // Release approval has a distinct readable summary; publication status is honest.
  const release={id:'1'.repeat(64),kind:'release',release_id:'R-1',title:'Foundation delivery',expected_hash:hash,revision:sha,changelog:'Added account foundations and keyboard-accessible onboarding.',publication_enabled:false};
  status=fresh(release);await page.reload();await page.getByRole('button',{name:'Approve release',exact:true}).waitFor();assert((await page.locator('#approvals-panel').innerText()).includes('Publishing awaits deployment configuration'));
  status.data.approvals.can_approve=false;await page.evaluate(()=>poll());assert(await page.getByRole('button',{name:'Approve release',exact:true}).isDisabled());assert((await page.locator('#approval-access').innerText()).includes('configured founder'));
  status=fresh();await page.reload();await page.getByRole('button',{name:'Approve plan',exact:true}).waitFor();await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  fs.mkdirSync('artifacts',{recursive:true});await page.screenshot({path:'artifacts/approval-mobile.png',fullPage:true});await page.setViewportSize({width:1440,height:1080});await page.screenshot({path:'artifacts/approval-desktop.png',fullPage:true});
  status.data.approvals.workflow_available=false;status.data.approvals.can_approve=false;await page.evaluate(()=>poll());assert((await page.locator('#approval-access').innerText()).includes('workflow is installed on main'));
  delete status.data.approvals;await page.reload();await page.locator('#content').waitFor({state:'visible'});assert(await page.locator('#approval-cards').isVisible());
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  console.log('PASS synthetic founder approval: scope, hidden intent, CSRF payload, keyboard submit, requested/confirmed separation, stale/failed state, release summary, founder authorization, mobile reflow, workflow unavailable, backward compatibility.');
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
