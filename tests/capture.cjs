// Capture the actual local UI without calling or mocking a hosted model.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const path=require('node:path');
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    await page.goto('http://127.0.0.1:8000/');await page.locator('.workshop-card').first().waitFor();
    await page.screenshot({path:path.resolve(__dirname,'../artifacts/learning-home.png')});
    await page.locator('#start-featured').click();await page.locator('[data-stage="1"]').click();
    await page.locator('[data-scenario="2"]').click();await page.locator('#send-burst').click();await page.locator('#invalidate-copy').click();await page.locator('#single-flight').check();await page.locator('#send-burst').click();
    await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.resolve(__dirname,'../artifacts/guided-lab.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.resolve(__dirname,'../artifacts/guided-mobile.png'),fullPage:true});
    console.log('Saved learning-home.png, guided-lab.png, guided-mobile.png. No hosted calls.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
