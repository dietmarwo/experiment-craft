/* Rendered artifact/audit UI with real runner transfers and fixture-copying jobs.
   No scientific checker runs in this test; the retained real CAP reports have separate tests. */
"use strict";
const assert=require("node:assert/strict"), fs=require("node:fs"), path=require("node:path");
const {spawn,execFileSync}=require("node:child_process"), {chromium}=require("playwright");
const project=path.resolve(__dirname,".."), out=process.argv[2];
const bin=process.env.EXPERIMENT_CRAFT_TEST_BIN_DIR, python=process.env.EXPERIMENT_CRAFT_TEST_PYTHON||"python3";
if(!bin||!out||fs.existsSync(out))throw Error("Set the native bin directory and pass a new output directory");
fs.mkdirSync(out,{recursive:true});
const prepared=JSON.parse(execFileSync(python,["tests/prepare_result_dashboard.py","--runner",path.join(bin,"optimization-run"),"--output",path.join(out,"fixture")],{cwd:project}));
const args=["-m","experiment_craft","dashboard","--state-dir",path.join(out,"history"),"--port","0","--sample-seconds",".25"];
for(const c of prepared.cases)args.push("--workspace",c.workspace);
const server=spawn(python,args,{cwd:project,stdio:["ignore","pipe","pipe"]});
let stdout="",stderr="";server.stdout.on("data",d=>stdout+=d);server.stderr.on("data",d=>stderr+=d);
const checks=[],check=(name,ok,detail)=>{checks.push({name,passed:!!ok,...(ok?{}:{detail})});assert.ok(ok,name);};
const jobs=()=>JSON.parse(execFileSync(path.join(bin,"optimization-run"),["--root",prepared.node,"jobs","list"]));
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function download(page,button,name){const event=page.waitForEvent("download");await button.click();const file=await event;await file.saveAs(path.join(out,name));return fs.readFileSync(path.join(out,name));}
(async()=>{
  let browser;
  try {
    for(let n=0;n<300&&!stdout.includes("\n");n++)await delay(100);
    const url=JSON.parse(stdout.split("\n")[0]).url;browser=await chromium.launch(process.env.EXPERIMENT_CRAFT_TEST_CHROMIUM ? {
      executablePath:process.env.EXPERIMENT_CRAFT_TEST_CHROMIUM,
      args:JSON.parse(process.env.EXPERIMENT_CRAFT_TEST_CHROMIUM_ARGS||"[]")} : {});
    for(const viewport of [{width:390,height:844},{width:1366,height:900}]){
      const phone=viewport.width===390, label=phone?"phone":"desktop", context=await browser.newContext({viewport,isMobile:phone,hasTouch:phone}),page=await context.newPage(),errors=[];
      page.on("pageerror",e=>errors.push(String(e)));
      await page.goto(url);await page.waitForSelector('[data-evidence="load"]:enabled');
      check(label+": no artifact read starts automatically",await page.locator(".artifact-table").count()===0);
      async function select(index){await page.locator(`button[data-campaign="${prepared.cases[index].id}"]`).click();await page.locator('[data-evidence="load"]').click();await page.waitForSelector('.artifact-table tbody tr[data-output="acceptance"]');}
      const row=()=>page.locator('.artifact-table tr[data-step="accept"][data-output="acceptance"]');
      async function collect(){await row().getByRole("button",{name:"Collect",exact:true}).click();await page.waitForFunction(()=>document.querySelector('.artifact-table tr[data-output="acceptance"]')?.textContent.includes("retained"),null,{timeout:15000});}
      async function view(verdict){await row().getByRole("button",{name:"View audit",exact:true}).click();await page.waitForSelector(`[data-verdict="${verdict}"]`);}
      await select(0);check(label+": output metadata renders all fixture outputs",await page.locator('.artifact-table tbody tr').count()===6);
      check(label+": uncollected receipt cannot be downloaded",await row().getByRole("button",{name:"Download",exact:true}).isDisabled()===phone);
      if(phone)await collect();await view("reported_accepted");
      check(label+": acceptance shows all six arms and native completion",await page.locator('.audit-table tbody tr').count()===6 && (await page.locator('.audit-native').textContent()).includes('Native state: completed'));
      check(label+": campaign name is displayed",await page.locator('#evidence img').count()===0 && (await page.locator('#evidence').textContent()).includes('Accepted audit'));
      const expected=path.join(out,"cli-"+label);
      execFileSync(python,["-m","experiment_craft","verification-report","--workspace",prepared.cases[0].workspace,"--step","accept","--destination",expected],{cwd:project});
      for(const [format,name] of [["json","verification.json"],["md","verification.md"],["csv","observations.csv"]]){
        const data=await download(page,page.locator(`[data-evidence="report:${format}"]`),label+"-"+name);
        check(label+": "+format+" download equals CLI bytes",data.equals(fs.readFileSync(path.join(expected,name))));
      }
      const raw=await download(page,row().getByRole("button",{name:"Download",exact:true}),label+"-acceptance.bin");
      check(label+": raw download equals checked retained output",raw.equals(fs.readFileSync(path.join(prepared.cases[0].workspace,"results/accept/outputs/acceptance"))));
      await page.locator('#evidence summary').click();await page.locator('.audit-table').evaluate(e=>e.parentNode.scrollLeft=120);await page.waitForTimeout(4500);
      check(label+": audit details and table scroll survive refresh",await page.locator('#evidence details').evaluate(e=>e.open) && await page.locator('.audit-table').evaluate(e=>e.parentNode.scrollLeft)>= (phone?100:0));
      if(phone)check('phone: artifact rows keep names and controls within the viewport',await page.locator('.artifact-table').evaluate(e=>e.scrollWidth<=e.parentNode.clientWidth));
      check(label+": no horizontal page overflow",await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
      await page.screenshot({path:path.join(out,label+"-accepted.png"),fullPage:true});
      await select(1);if(phone)await collect();await view('reported_rejected');
      check(label+": rejected and censored arm stays visible",await page.locator('.audit-table tbody tr').count()===6 && (await page.locator('.audit-summary').textContent()).includes('1 right-censored') && (await page.locator('.audit-native').textContent()).includes('Exit code: 3'));
      await page.screenshot({path:path.join(out,label+"-rejected.png"),fullPage:true});
      await select(2);if(phone)await collect();await view('unconfirmed');
      check(label+": an accepted receipt with failed execution stays unconfirmed",(await page.locator('.audit-native').textContent()).includes('Application verdict: accepted') && (await page.locator('.audit-native').textContent()).includes('Exit code: 7'));
      await select(3);await view('unavailable');
      check(label+": pending evidence keeps counts unknown and collection disabled",(await page.locator('.audit-summary').textContent()).includes('unknown')&&await row().getByRole("button",{name:"Collect",exact:true}).isDisabled());
      check(label+": reading pending results launches no jobs",jobs().length===9);
      if(phone){
        await page.locator(`button[data-campaign="${prepared.cases[0].id}"]`).click();
        let release,entered;const gate=new Promise(r=>release=r),seen=new Promise(r=>entered=r);
        const target=`**/api/campaigns/${prepared.cases[0].id}/verification/accept/acceptance/json`;
        await page.route(target,async route=>{entered();await gate;await route.continue();});
        await row().getByRole('button',{name:'View audit',exact:true}).click();await seen;
        await page.locator(`button[data-campaign="${prepared.cases[3].id}"]`).click();release();
        await page.waitForResponse(response=>response.url().includes(`/api/campaigns/${prepared.cases[0].id}/verification/`));
        await page.waitForTimeout(100);await page.unroute(target);
        check('a late report stays with its original campaign',await page.locator('[data-verdict="unavailable"]').count()===1 && await page.locator('[data-verdict="reported_accepted"]').count()===0);
      }
      if(!phone){
        await select(0);const study=page.locator('.artifact-table tr[data-output="study"]');await study.getByRole('button',{name:'Collect',exact:true}).click();
        await page.waitForFunction(()=>document.querySelector('.artifact-table tr[data-output="study"]')?.textContent.includes('retained'));
        await study.getByRole('button',{name:'View audit',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#evidence .error-text')?.textContent.includes('unsupported_verification'));
        check('unsupported command output shows an error without a retained verdict',await page.locator('.audit-result').count()===0);
        const recovered=await page.evaluate(()=>{
          const c=snapshot.campaigns.find(c=>c.id===selected),state=evidenceState(c.id);
          state.pending={id:'superseded-test',after:-1};c.operations=[{id:'later',action:'collect',started_at:1,running:false}];
          renderEvidence(c);return state.pending===null && state.error.includes('another operation replaced it');
        });
        check('a superseded operation does not leave collection controls stuck',recovered);
        // A collection whose completion the page has not seen keeps the audit
        // controls disabled; a snapshot that no longer reports it, as after a
        // dashboard restart, releases them.
        await select(1);let reported="running";
        await page.route("**/api/snapshot",async route=>{
          const response=await route.fetch(),value=await response.json(),c=value.campaigns.find(x=>x.id===prepared.cases[1].id);
          c.operations=reported==="running"?c.operations.map(o=>o.action==="collect-artifact"?{...o,running:true,finished_at:null}:o):[];
          await route.fulfill({response,json:value});
        });
        await row().getByRole("button",{name:"Collect",exact:true}).click();
        await page.waitForFunction(()=>document.querySelector("#evidence").textContent.includes("Collecting the selected output"));await page.waitForTimeout(2500);
        check("a pending collection disables the audit view and its downloads",await row().getByRole("button",{name:"View audit",exact:true}).isDisabled());
        reported="restarted";
        await page.waitForFunction(()=>!document.querySelector("#evidence").textContent.includes("Collecting the selected output"),null,{timeout:8000});
        check("a collection the dashboard no longer reports releases the controls",await page.locator('[data-evidence="load"]').isEnabled()&&(await page.locator("#evidence .error-text").textContent()).includes("no longer reports"));
        await page.unroute("**/api/snapshot");
        await select(0);
        await view('reported_accepted');fs.writeFileSync(path.join(prepared.cases[0].workspace,'results/accept/outputs/acceptance'),'tampered');
        await row().getByRole('button',{name:'Download',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#evidence .error-text')?.textContent.includes('artifact_changed'));
        check('changed cached bytes refuse download and clear the displayed verdict',await page.locator('.audit-result').count()===0);
      }
      check(label+": no page script errors",errors.length===0,errors);await context.close();
    }
    check('all actions preserve the nine original jobs',jobs().length===9);
  } catch(e) { checks.push({name:'workflow completed',passed:false,detail:String(e)});throw e;
  } finally {
    if(browser)await browser.close();server.kill('SIGINT');
    if(server.exitCode===null)await new Promise(r=>server.on('exit',r));
    check('dashboard exits cleanly',server.exitCode===0,{stderr,stdout});
    fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({status:checks.every(c=>c.passed)?'passed':'failed',environment:'Chromium; emulated phone and desktop; fixture copying jobs, no proof execution',native_jobs:jobs().length,checks,stderr},null,2)+'\n');
  }
  console.log(JSON.stringify({status:'passed',checks:checks.length,native_jobs:jobs().length}));
})().catch(e=>{console.error(e);server.kill('SIGKILL');process.exitCode=1;});
