// Dev-only verification. Set PLAYWRIGHT_MODULE to an installed Playwright module
// path if it is not available through ordinary Node module resolution.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const path = require('node:path');
const fs = require('node:fs');

(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  const context=await browser.newContext({viewport:{width:1440,height:1100}});
  const page=await context.newPage();const errors=[];const remoteRequests=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(/^https?:/.test(r.url()))remoteRequests.push(r.url());});
  const checks=[];
  async function check(name,fn){await fn();checks.push(name);console.log('PASS '+name);}
  const steps=async n=>{for(let i=0;i<n;i++)await page.locator('#step').click();};
  const metric=async i=>page.locator('.metric strong').nth(i).innerText();
  try{
    await page.goto(pathToFileURL(path.resolve(__dirname,'../index.html')).href);
    await check('Offline entry and round-robin distribution',async()=>{await steps(4);assert.equal(await metric(0),'3');assert.equal(await metric(2),'1 / 1 / 1');});
    await check('Failed backends are excluded; all-down rejects',async()=>{
      await page.locator('[data-server="1"]').click();await steps(4);assert.equal(await metric(2),'3 / 1 / 2');
      await page.locator('[data-server="0"]').click();await page.locator('[data-server="2"]').click();await steps(4);assert.equal(await metric(3),'3');assert.equal(await metric(1),'0 / 3');
    });
    await check('Weighted routing sends A twice the traffic',async()=>{
      await page.locator('#reset').click();await page.locator('#algorithm').selectOption('weighted');
      await page.locator('#volume').fill('4');await steps(4);assert.equal(await metric(2),'2 / 1 / 1');
    });
    await check('Playback pause stops further assignments',async()=>{
      await page.locator('#speed').selectOption('500');await page.locator('#play').click();await page.waitForTimeout(2100);await page.locator('#play').click();
      const value=await metric(0);await page.waitForTimeout(650);assert.equal(await metric(0),value);assert.match(await page.locator('#play').innerText(),/Play flow/);
    });
    await page.locator('[data-lesson="caching"]').click();
    await check('Cache miss fills; repeated read hits',async()=>{await steps(5);assert.equal(await metric(1),'1');await steps(5);assert.equal(await metric(0),'50%');assert.equal(await metric(1),'1');assert.equal(await metric(2),'30.0 ms');});
    await check('Source writes produce stale copies; expiry refreshes',async()=>{
      await page.locator('#update-price').click();await steps(5);assert.equal(await metric(3),'1');assert.match(await page.locator('#step-description').innerText(),/Returned \$24/);
      await page.locator('#expire-cache').click();await steps(5);assert.equal(await metric(1),'2');assert.match(await page.locator('#step-description').innerText(),/Returned \$29/);
    });
    await check('TTL expires using simulated time',async()=>{
      await page.locator('#reset').click();await page.locator('#ttl').fill('2');await steps(15);assert.equal(await metric(1),'2');assert.equal(await metric(0),'33%');
    });
    await check('All quiz answers save completion across reload',async()=>{
      await page.locator('#tab-check').click();for(const [q,a] of [[0,1],[1,0],[2,2]])await page.locator(`[data-q="${q}"][data-answer="${a}"]`).click();
      assert.match(await page.locator('#quiz-result').innerText(),/Lesson complete/);await page.reload();assert.equal(await page.locator('#progress-count').innerText(),'1 / 3');
    });
    await page.locator('[data-lesson="url-shortener"]').click();
    await check('Create and atomically reject a duplicate alias',async()=>{
      await page.locator('#alias').fill('my-guide');await steps(5);assert.equal(await metric(0),'1');assert.match(await page.locator('#url-status').innerText(),/Created ev.local\/my-guide/);
      await steps(5);assert.equal(await metric(0),'1');assert.match(await page.locator('#url-status').innerText(),/409 Conflict/);
    });
    await check('Cold and cached redirects follow different paths',async()=>{
      await page.locator('#mode-resolve').click();await page.locator('#use-last').click();await steps(5);assert.equal(await metric(2),'1');assert.equal(await metric(3),'1');
      await steps(5);assert.equal(await metric(2),'1');assert.equal(await metric(1),'2');assert.match(await page.locator('#url-status').innerText(),/302 Found/);
      await page.locator('#cache-online').click();await steps(5);assert.equal(await metric(2),'2');
    });
    await check('Unknown codes and object prototype keys return 404',async()=>{
      for(const code of ['missing-code','constructor','toString']){await page.locator('#short-code').fill(code);await steps(5);assert.match(await page.locator('#url-status').innerText(),/404 Not Found/);}
      await page.locator('#use-last').click();assert.equal(await page.locator('#short-code').inputValue(),'my-guide');
    });
    await check('Input validation rejects unsupported URL schemes',async()=>{
      await page.locator('#mode-create').click();await page.locator('#long-url').fill('javascript:alert(1)');await steps(1);assert.match(await page.locator('#url-status').innerText(),/valid URL/);
      await page.locator('#long-url').fill('https://example.com/valid');await page.locator('#alias').fill('__proto__');await steps(5);assert.match(await page.locator('#url-status').innerText(),/Created ev.local\/__proto__/);
      await page.locator('#mode-resolve').click();await page.locator('#use-last').click();await steps(5);assert.match(await page.locator('#url-status').innerText(),/302 Found/);
    });
    await check('Capacity calculator applies source assumptions',async()=>{
      await page.locator('#tab-understand').click();assert.match(await page.locator('#capacity-results').innerText(),/347,222/);assert.match(await page.locator('#capacity-results').innerText(),/6,944/);
      await page.locator('#hit-rate').fill('0');assert.match(await page.locator('#capacity-results tr').nth(2).innerText(),/347,222/);
    });
    await check('Library contains all topics, filters, and valid source files',async()=>{
      await page.locator('#open-library').click();assert.equal(await page.locator('.library-row').count(),52);
      for(const href of await page.locator('.library-row a').evaluateAll(a=>a.map(x=>x.getAttribute('href'))))assert.ok(fs.existsSync(path.resolve(__dirname,'..',href.split('#')[0])));
      await page.locator('[data-filter="concept"]').click();assert.equal(await page.locator('.library-row').count(),36);
      await page.locator('[data-filter="problem"]').click();assert.equal(await page.locator('.library-row').count(),16);
      await page.locator('[data-filter="all"]').click();await page.locator('#library-search').fill('Caching');assert.equal(await page.locator('.library-row').count(),2);
      await page.locator('#library-search').fill('zzzz');assert.match(await page.locator('#library-results').innerText(),/No matching topics/);await page.keyboard.press('Escape');
    });
    await check('Keyboard tabs and reduced motion remain usable',async()=>{
      await page.locator('#tab-experiment').click();await page.keyboard.press('ArrowRight');assert.equal(await page.locator('#tab-understand').getAttribute('aria-selected'),'true');
      await page.locator('#motion-toggle').click();assert.equal(await page.locator('#motion-toggle').getAttribute('aria-pressed'),'true');await page.locator('#tab-experiment').click();await steps(1);
    });
    fs.mkdirSync(path.resolve(__dirname,'../artifacts'),{recursive:true});
    await page.locator('[data-lesson="load-balancing"]').click();await steps(3);await page.screenshot({path:path.resolve(__dirname,'../artifacts/desktop.png'),fullPage:true});
    await check('Desktop and mobile do not overflow horizontally',async()=>{
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.setViewportSize({width:390,height:844});
      for(const id of ['load-balancing','caching','url-shortener']){await page.locator(`[data-lesson="${id}"]`).click();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),id+' overflow');}
      await page.locator('[data-lesson="load-balancing"]').click();await page.screenshot({path:path.resolve(__dirname,'../artifacts/mobile.png'),fullPage:true});
    });
    assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);
    console.log(`\n${checks.length} checks passed; no browser errors or network requests.`);
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
