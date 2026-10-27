/* UI interactions against the real server/runner. jsdom is not a layout engine. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {spawn, spawnSync} = require("node:child_process");
const {JSDOM, VirtualConsole} = require("jsdom");
const project = path.resolve(__dirname, "..");
const output = path.resolve(process.argv[2]);
const binaries = path.resolve(process.env.EXPERIMENT_CRAFT_TEST_BIN_DIR);
const python = process.env.EXPERIMENT_CRAFT_TEST_PYTHON || "python3";
fs.mkdirSync(output, {recursive:false});
const delay = ms => new Promise(resolve=>setTimeout(resolve,ms));
async function until(fn, description, timeout=30000) {
  const end=Date.now()+timeout;
  while(Date.now()<end) {const value=await fn();if(value)return value;await delay(40);}
  throw new Error("Timed out: "+description);
}
async function runCase(name, stop) {
  const directory=path.join(output,name);
  const child=spawn(python,["examples/dashboard/prepare.py","--bin-dir",binaries,"--output",directory,"--serve","--port","0"],{cwd:project,stdio:["ignore","pipe","pipe"]});
  let url, buffer="", stderr="", dom, closing=false;
  child.stdout.on("data",chunk=>{buffer+=chunk;let end;while((end=buffer.indexOf("\n"))>=0){const line=buffer.slice(0,end);buffer=buffer.slice(end+1);const v=JSON.parse(line);if(v.url)url=v.url;}});
  child.stderr.on("data",chunk=>{stderr+=chunk;});
  try {
    await until(()=>url|| (child.exitCode!==null?Promise.reject(new Error(stderr)):false),"server ready");
    const endpoint=new URL(url),token=new URLSearchParams(endpoint.hash.slice(1)).get("token");
    const get=async()=>{const r=await fetch(endpoint.origin+"/api/snapshot",{headers:{Authorization:"Bearer "+token}});assert.equal(r.status,200);return r.json();};
    const errors=[], downloads=[];
    const console=new VirtualConsole();console.on("jsdomError",error=>errors.push(error.message));
    dom=await JSDOM.fromURL(url,{runScripts:"dangerously",resources:"usable",pretendToBeVisual:true,virtualConsole:console,beforeParse(window){
      window.AbortController=AbortController;
      window.fetch=async(resource,init={})=>{
        if(closing)throw new Error("page is closing");
        const target=new URL(resource,window.location.href);assert.equal(target.origin,endpoint.origin);
        const headers={...init.headers};if(init.method==="POST")headers.Origin=endpoint.origin;
        return fetch(target,{...init,headers});
      };
      window.Blob=Blob;window.URL.createObjectURL=blob=>{downloads.push(blob);return "blob:test";};window.URL.revokeObjectURL=()=>{};
      window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
      window.HTMLDialogElement.prototype.close=function(value){this.returnValue=value;this.open=false;this.dispatchEvent(new window.Event("close"));};
      window.HTMLAnchorElement.prototype.click=function(){};
      // jsdom does not implement form method="dialog"; close the dialog with the
      // clicked button's value, as a browser does, so the real buttons are used.
      window.document.addEventListener("submit",event=>{if(event.target.method==="dialog"){event.preventDefault();event.target.closest("dialog").close(event.submitter?.value||"");}},true);
    }});
    const window=dom.window,document=window.document;
    await until(()=>document.querySelector("#connection").textContent.startsWith("Connected"),"first render");
    assert.equal(window.location.hash,"");assert.equal(window.sessionStorage.getItem("ec-token"),token);
    // A newly printed URL pasted into the open tab changes only the fragment.
    window.location.hash="#token=replaced";
    await until(()=>document.querySelector("#connection").textContent==="Disconnected","a replaced token is used");
    window.location.hash="#token="+token;
    await until(()=>document.querySelector("#connection").textContent.startsWith("Connected"),"a new token URL in the open tab");
    assert.equal(window.location.hash,"");assert.equal(window.sessionStorage.getItem("ec-token"),token);
    assert.equal(document.querySelectorAll(".node").length,7);
    assert.equal(document.querySelectorAll(".node.inactive").length,6);
    const button=action=>document.querySelector(`[data-action="${action}"]`);
    assert.equal(button("continue").textContent,"Start");button("continue").click();
    await until(async()=> (await get()).campaigns[0].steps.some(s=>s.issued),"native intent");
    if(stop) {
      button("stop").click();assert.equal(document.querySelector("#stop-dialog").open,true);
      assert.equal(document.querySelector("#stop-name").textContent,"Local solver tour");
      // Workspaces of one manifest share its name; the path tells them apart.
      assert.equal(document.querySelector("#stop-workspace").textContent,(await get()).campaigns[0].workspace);
      document.querySelector('#stop-dialog button[value="cancel"]').click();assert.equal(document.querySelector("#stop-dialog").open,false);
      assert.equal((await get()).campaigns[0].summary.stop_reason,null);
      button("stop").click();document.querySelector('#stop-dialog button[value="stop"]').click();
      await until(async()=> !(await get()).campaigns[0].operations.some(o=>o.running),"stop settles");
      await window.refresh();
      assert.ok(["stopped","incomplete"].includes((await get()).campaigns[0].summary.status));
      assert.equal(button("continue").disabled,true);
    } else {
      button("pause").click();
      await until(async()=>{const c=(await get()).campaigns[0];return c.maintenance.paused&&!c.operations.some(o=>o.running);},"pause settles");
      await window.refresh();
      assert.equal(button("continue").disabled,true);assert.equal(button("unpause").disabled,false);
      const fetchWorking=window.fetch;window.fetch=async()=>{throw new Error("connection test");};await window.refresh();
      assert.equal(document.querySelector("#connection").textContent,"Disconnected");
      assert.ok([...document.querySelectorAll("[data-action], [data-evidence]")].every(b=>b.disabled));
      window.fetch=fetchWorking;await window.refresh();
      window.fetch=async(resource,init)=>{
        const response=await fetchWorking(resource,init);
        if(resource!=="/api/snapshot")return response;
        const value=await response.json();value.monitor_error={code:"test_cache_failure",message:"test history unavailable"};
        return new Response(JSON.stringify(value),{status:200,headers:{"Content-Type":"application/json"}});
      };
      await window.refresh();assert.equal(button("unpause").disabled,true);assert.equal(button("stop").disabled,false);
      window.fetch=fetchWorking;await window.refresh();
      window.fetch=async(resource,init)=>{
        if(resource.startsWith("/api/history/"))throw new Error("history read test");
        return fetchWorking(resource,init);
      };
      await window.refresh();assert.equal(button("unpause").disabled,true);assert.equal(button("stop").disabled,false);
      window.fetch=fetchWorking;await window.refresh();
      button("unpause").focus();await window.refresh();assert.equal(document.activeElement.dataset.action,"unpause");
      document.querySelector("#detail details").open=true;
      button("unpause").click();await until(async()=>{const c=(await get()).campaigns[0];return !c.maintenance.paused&&!c.operations.some(o=>o.running);},"unpause");
      await window.refresh();
      assert.equal(document.querySelector("#detail details").open,true,"the details stay open when the panel changes");button("continue").click();
      await until(async()=> (await get()).campaigns[0].summary.status==="completed","complete real solver tour");
      await window.refresh();assert.equal(button("continue").disabled,true);
      const panel=document.querySelector("#detail details");await window.refresh();
      assert.equal(document.querySelector("#detail details"),panel,"an unchanged panel is not rebuilt");
      assert.ok(document.querySelectorAll(".chart .series").length>=4);
      document.querySelector("#download").click();assert.equal(downloads.length,1);
      const history=JSON.parse(await downloads[0].text());assert.equal(history.histories.length,1);
      assert.ok(history.histories[0].points.some(p=>p.counts.succeeded===10));
      assert.ok(history.histories[0].points.some(p=>p.unresolved_declared_slots===1));
      fs.writeFileSync(path.join(output,"history-export.json"),JSON.stringify(history,null,2)+"\n");
    }
    assert.deepEqual(errors,[]);
    const state=await get();
    const native=spawnSync(path.join(binaries,"optimization-run"),["--root",path.join(directory,"node"),"jobs","list"],{encoding:"utf8"});
    assert.equal(native.status,0,native.stderr);
    const jobs=JSON.parse(native.stdout);assert.equal(jobs.length,stop?1:10);
    fs.writeFileSync(path.join(output,name+"-snapshot.json"),JSON.stringify(state,null,2)+"\n");
    return {name,status:"passed",native_jobs:jobs.length,campaign_status:state.campaigns[0].summary.status,
            nodes_displayed:7,remote_nodes_enabled:0,js_errors:errors,visual_layout_tested:false};
  } finally {
    if(dom) {
      // A refresh from the page's own timer may still be in flight. Refuse new
      // requests and let it settle, so closing the window cannot fail it.
      closing=true;
      await until(()=>!dom.window.eval("refreshing"),"page requests settle",10000).catch(()=>{});
      dom.window.close();
    }
    child.kill("SIGINT");
    await until(()=>child.exitCode!==null||child.signalCode!==null,"server exit",35000);
    fs.writeFileSync(path.join(output,name+"-server.stderr"),stderr);
    const wal=path.join(directory,"campaign","campaign.sqlite3-wal");
    assert.ok(!fs.existsSync(wal)||fs.statSync(wal).size===0,"shutdown must finish WAL with no external clients");
    // An immutable read inspects the main database without loading/checkpointing
    // WAL itself. With no external clients the graceful shutdown must finish it.
    const inspect="import json,sqlite3,sys; from pathlib import Path; from experiment_craft.campaign import summary; db=sqlite3.connect(Path(sys.argv[1]).as_uri()+'?mode=ro&immutable=1',uri=True); print(json.dumps(summary(json.loads(db.execute('SELECT value FROM state').fetchone()[0])))); db.close()";
    const saved=spawnSync(python,["-c",inspect,path.join(directory,"campaign","campaign.sqlite3")],{cwd:project,encoding:"utf8"});
    assert.equal(saved.status,0,saved.stderr);
    const after=JSON.parse(saved.stdout);
    assert.equal(after.status,stop?"stopped":"completed","saved campaign state after server exit");
    const reopened=spawnSync(python,["-m","experiment_craft","status","--workspace",path.join(directory,"campaign")],{cwd:project,encoding:"utf8"});
    assert.equal(reopened.status,0,reopened.stderr);
    assert.equal(JSON.parse(reopened.stdout).status,after.status,"ordinary reopened client must agree with the main database");
    fs.writeFileSync(path.join(output,name+"-after-exit.json"),JSON.stringify(after,null,2)+"\n");
  }
}
(async()=>{
  const results=[];results.push(await runCase("complete",false));results.push(await runCase("stop",true));
  const value={status:"passed",environment:"jsdom DOM with real HTTP and native runner; no browser layout engine",results};
  fs.writeFileSync(path.join(output,"summary.json"),JSON.stringify(value,null,2)+"\n");console.log(JSON.stringify(value));
})().catch(error=>{console.error(error);process.exitCode=1;});
