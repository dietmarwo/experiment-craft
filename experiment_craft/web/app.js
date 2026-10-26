/* No remote assets. All labels use textContent; no campaign data becomes markup. */
"use strict";
const $ = id => document.getElementById(id);
const tokenParam = new URLSearchParams(location.hash.slice(1)).get("token");
if (tokenParam) { sessionStorage.setItem("ec-token", tokenParam); history.replaceState(null, "", "/"); }
const token = sessionStorage.getItem("ec-token") || "";
let snapshot = null, selected = null, online = false, fresh = false, historyError = false, histories = new Map();
const finished = ["succeeded", "failed", "cancelled", "blocked", "budget_exhausted", "stopped"];
const color = {accepted:"#87dfb7", other:"#f0a472", uncertain:"#f1d179", pending:"#91a6bd"};
function el(tag, text, cls) { const e = document.createElement(tag); if(text !== undefined) e.textContent = text; if(cls) e.className = cls; return e; }
function replace(id, children) { $(id).replaceChildren(...children); }
function fmt(t) { return new Date(t*1000).toLocaleString(undefined,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",second:"2-digit"}); }
function count(c, keys) { return keys.reduce((n,k)=>n+(c[k]||0),0); }
function notice(message) { $("notice").hidden = !message; $("notice").textContent = message || ""; }
async function api(path, action=false) {
  const controller=new AbortController(), timeout=setTimeout(()=>controller.abort(),8000);
  try {
    const response = await fetch(path, {method:action?"POST":"GET", cache:"no-store", signal:controller.signal,
      headers:{Authorization:`Bearer ${token}`, ...(action?{"Content-Type":"application/json"}:{})},
      ...(action?{body:"{}"}:{})});
    const data = await response.json();
    if (!response.ok) throw new Error(`${data.error?.code || response.status}: ${data.error?.message || "Request failed"}`);
    return data;
  } finally {clearTimeout(timeout);}
}
function badge(text, cls="") { return el("span", text.replaceAll("_"," ").toUpperCase(), `badge ${cls}`); }
function svg(tag, attrs={}) { const e=document.createElementNS("http://www.w3.org/2000/svg",tag); for(const [k,v] of Object.entries(attrs)) e.setAttribute(k,String(v)); return e; }
function progress(counts) {
  const bar=el("div",undefined,"progress"), s=svg("svg",{viewBox:"0 0 100 6",preserveAspectRatio:"none",role:"img","aria-label":"Fraction of steps accepted and otherwise finished"});
  const total=Object.values(counts).reduce((a,b)=>a+b,0)||1;
  const accepted=100*counts.succeeded/total, done=100*count(counts,finished.filter(k=>k!=="succeeded"))/total;
  s.append(svg("rect",{x:0,y:0,width:accepted,height:6,fill:color.accepted}),svg("rect",{x:accepted,y:0,width:done,height:6,fill:color.other}));bar.append(s);return bar;
}
function render() {
  const focusAction=document.activeElement?.dataset?.action, focusCampaign=document.activeElement?.dataset?.campaign;
  const focusSummary=document.activeElement?.tagName==="SUMMARY";
  const campaigns=snapshot.campaigns, counts=Object.fromEntries(["succeeded","failed","unknown"].map(k=>[k,campaigns.reduce((n,c)=>n+c.counts[k],0)]));
  const total=campaigns.reduce((n,c)=>n+c.steps.length,0), stale=campaigns.some(c=>c.read_error);
  replace("totals",[["Attached experiments",campaigns.length,"Initialized workspaces"],["Accepted steps",`${counts.succeeded} / ${total}`,stale?"Includes retained stale state":"Passed declared acceptance"],["Failed steps",counts.failed,"Failures remain in the total"],["Uncertain steps",counts.unknown,"Require observation; never replay"]].map(([label,value,note])=>{const x=el("div",undefined,"stat");x.append(el("span",label),el("strong",value),el("small",note));return x;}));
  $("sample-time").textContent=fmt(snapshot.sampled_at);
  $("campaign-count").textContent=String(campaigns.length);
  if(!selected || !campaigns.some(c=>c.id===selected)) selected=campaigns[0]?.id;
  replace("campaigns",campaigns.map(c=>{const b=el("button",undefined,`campaign ${c.id===selected?"selected":""}`);b.dataset.campaign=c.id;b.setAttribute("aria-pressed",String(c.id===selected));b.append(el("span",c.name),el("small",`${c.maintenance.paused?"Dispatch paused":c.summary.status} · ${c.counts.succeeded}/${c.steps.length} accepted`));b.onclick=()=>{selected=c.id;render();};return b;}));
  renderDetail(campaigns.find(c=>c.id===selected));
  replace("nodes",snapshot.nodes.map(renderNode));
  if(focusSummary) document.querySelector("#detail summary")?.focus({preventScroll:true});
  else if(focusAction) document.querySelector(`[data-action="${focusAction}"]`)?.focus({preventScroll:true});
  else if(focusCampaign) document.querySelector(`[data-campaign="${focusCampaign}"]`)?.focus({preventScroll:true});
}
let detailKey=null;
function renderDetail(c) {
  if(!c) return;
  // An unchanged panel is left alone, so a selection, an open details block
  // and the step table's scroll position survive the two-second refresh.
  const key=JSON.stringify([c,snapshot.nodes.find(n=>n.campaign_ids.includes(c.id))?.name,online,fresh,!!snapshot.monitor_error,historyError]);
  const panel=$("detail");
  if(key===detailKey&&panel.dataset.campaign===c.id) return;
  const same=panel.dataset.campaign===c.id, wasOpen=same&&!!panel.querySelector("details")?.open;
  const scrollTop=same?panel.querySelector(".table-wrap")?.scrollTop||0:0;
  const title=el("div",undefined,"detail-title");title.append(el("h2",c.name),badge(c.maintenance.paused?"paused":c.summary.status,c.summary.status==="unknown"?"warn":""));
  const node=snapshot.nodes.find(n=>n.campaign_ids.includes(c.id));
  const meta=el("p",`${node?.name||c.node_id} · ${c.mode} · Deadline ${fmt(c.summary.deadline_at)}`,"detail-meta");
  const advance=c.operations.find(o=>o.running&&!["pause","stop"].includes(o.action));
  const control=c.operations.find(o=>o.running&&["pause","stop"].includes(o.action));
  const buttons=el("div",undefined,"actions");
  const allDone=c.steps.every(s=>finished.includes(s.status));
  const controlDisabled=!online||!!c.read_error;
  const disabled=controlDisabled||!!snapshot.monitor_error||!fresh||historyError;
  const choices=[
    ["continue",c.steps.some(s=>s.issued)?"Continue":"Start",disabled||!!advance||c.maintenance.paused||allDone],
    ["pause","Pause dispatch",controlDisabled||!!control||c.maintenance.paused||allDone],
    ["unpause","Reconcile & unpause",disabled||!!advance||!c.maintenance.paused],
    ["collect","Refresh native state",disabled||!!advance],
    ["stop","Stop",controlDisabled||!!control||allDone]
  ];
  for(const [action,label,off] of choices) { const b=el("button",label,action==="continue"?"":action==="stop"?"danger":"secondary");b.disabled=off;b.dataset.action=action;b.onclick=()=>action==="stop"?confirmStop(c):act(c.id,action);buttons.append(b); }
  const status=el("p",`${count(c.counts,finished)} / ${c.steps.length} steps finished · ${c.counts.succeeded} accepted · ${c.unresolved_declared_slots} declared slots in unresolved work`,"muted");
  const elements=[title,meta,buttons,el("p",c.maintenance.paused?"Dispatch is paused. Active work can finish; unpausing verifies existing handles before Start / Continue is available.":"Pause prevents new dispatch. Stop requests native cancellation. Neither action replays work.","muted"),progress(c.counts),status];
  if(c.read_error) elements.push(el("p",`Saved state unavailable — showing the last snapshot. ${c.read_error.message}`,"error-text"));
  for(const op of c.operations) if(op.running||op.error) elements.push(el("p",op.running?`${op.action}: in progress…`:`${op.action}: ${op.error.code} — ${op.error.message}`,op.error?"error-text":"detail-meta"));
  const wrap=el("div",undefined,"table-wrap"),table=el("table"),head=el("thead"),hr=el("tr");["STEP","SAVED STATE","SLOTS"].forEach(x=>hr.append(el("th",x)));head.append(hr);table.append(head);const body=el("tbody");
  for(const step of c.steps) { const tr=el("tr");tr.append(el("td",step.id),el("td",step.status.replaceAll("_"," ")),el("td",String(step.cpu_slots)));if(step.error) tr.title=`${step.error.code}: ${step.error.message}`;body.append(tr); }table.append(body);wrap.append(table);elements.push(wrap);
  const events=el("details");events.open=wasOpen;events.append(el("summary","Recent decisions & details"),el("pre",JSON.stringify({workspace:c.workspace,campaign_id:c.id,native_node_id:c.node_id,maintenance:c.maintenance,events:c.events,errors:c.steps.filter(s=>s.error)},null,2)));elements.push(events);replace("detail",elements);
  panel.dataset.campaign=c.id;wrap.scrollTop=scrollTop;detailKey=key;
}
function renderNode(n) {
  const active=n.campaign_ids.length>0, card=el("article",undefined,`node ${active?"":"inactive"}`),header=el("div",undefined,"node-header"),left=el("div");
  left.append(el("h3",n.name),el("p",`${n.transport.toUpperCase()} · ${n.declared_cpu_slots===null?"Capacity not recorded":`${n.declared_cpu_slots} configured slots`}`,"muted"));
  const state=!n.enabled?"disabled":n.availability==="read_unavailable"?"state unavailable":n.transport==="ssh"?"routing unavailable":active?"saved observations":"not observed";
  header.append(left,badge(state,active?"":"off"));card.append(header);
  if(!active){card.append(el("div",n.transport==="ssh"?"No remote campaign observations. This dashboard does not verify or control this inventory entry.":"No attached campaign. No runtime probe has been made.","chart-empty"));return card;}
  if(n.counts) { const nums=el("div",undefined,"node-counts");for(const [v,l] of [[n.counts.succeeded,"accepted"],[count(n.counts,finished),"finished"],[n.unresolved_declared_slots,"unresolved declared slots"]]) {const s=el("span");s.append(el("strong",String(v)),document.createTextNode(l));nums.append(s);}card.append(nums); }
  const h=histories.get(n.id);
  if(h?.points?.length) {card.append(chart(h.points,n.name));card.append(el("p",`${h.points.length} retained samples · Since ${fmt(h.points[0].at)} · Clock: your browser’s timezone`,"history-note"));}
  else card.append(el("div","Waiting for the first history sample…","chart-empty"));
  if(n.availability==="read_unavailable") card.append(el("p","Campaign read failed. Counts are unknown until a fresh snapshot succeeds.","error-text"));
  return card;
}
function chart(points,name) {
  const W=560,H=180,L=34,R=8,T=15,B=28;
  const out=svg("svg",{viewBox:`0 0 ${W} ${H}`,role:"img","aria-label":`${name}: sampled step counts over time`,class:"chart"});
  const valid=points.filter(p=>p.counts);const max=Math.max(1,...valid.map(p=>Object.values(p.counts).reduce((a,b)=>a+b,0)));
  const start=Math.min(...points.map(p=>p.at)),end=Math.max(start+1,...points.map(p=>p.at)),x=t=>L+(t-start)/(end-start)*(W-L-R),y=v=>H-B-v/max*(H-T-B);
  for(const f of [0,.5,1]){const yy=y(max*f);out.append(svg("line",{x1:L,x2:W-R,y1:yy,y2:yy,class:"gridline"}));const text=svg("text",{x:L-8,y:yy+3,"text-anchor":"end",class:"axis-label"});text.textContent=String(Math.round(max*f));out.append(text);}
  for(const [time,anchor] of [[start,"start"],[end,"end"]]) {const text=svg("text",{x:x(time),y:H-7,"text-anchor":anchor,class:"axis-label"});text.textContent=new Date(time*1000).toLocaleTimeString(undefined,{hour:"2-digit",minute:"2-digit",second:"2-digit"});out.append(text);}
  const series={accepted:c=>c.succeeded,other:c=>count(c,finished.filter(k=>k!=="succeeded")),uncertain:c=>c.unknown,pending:c=>c.pending};
  for(const [key,get] of Object.entries(series)) {
    let d="",prev=null;
    for(const p of points){if(!p.counts){prev=null;continue;}const xx=x(p.at),yy=y(get(p.counts));const gap=!prev||p.segment!==prev.segment||p.at-prev.at>Math.max(60,3*snapshot.sample_seconds)||p.at<prev.at;
      d+=gap?`M${xx},${yy}`:`H${xx}V${yy}`;prev=p;
    }
    out.append(svg("path",{d,stroke:color[key],class:"series"}));
    if(valid.length){const last=valid[valid.length-1];out.append(svg("circle",{cx:x(last.at),cy:y(get(last.counts)),r:3,fill:color[key]}));}
  }
  const title=svg("title");title.textContent="Step counts, not solver convergence or machine utilization. Other finished includes failed, cancelled, blocked, budget-exhausted and stopped steps.";out.append(title);return out;
}
async function act(id,action) {
  try {await api(`/api/campaigns/${id}/${action}`,true);notice("");await refresh();}
  catch(e){notice(e.message);}
}
function confirmStop(c){$("stop-name").textContent=c.name;const d=$("stop-dialog");d.onclose=()=>{if(d.returnValue==="stop")act(c.id,"stop");};d.showModal();}
let refreshing=false;
async function refresh(){
  if(refreshing)return;refreshing=true;
  try{
    snapshot=await api("/api/snapshot");
    online=true;
    const pairs=await Promise.allSettled(snapshot.nodes.filter(n=>n.campaign_ids.length).map(async n=>[n.id,await api(`/api/history/${n.id}`)]));
    const next=new Map();historyError=pairs.some(p=>p.status==="rejected");
    for(const p of pairs)if(p.status==="fulfilled")next.set(...p.value);
    histories=next;
    const stale=Date.now()/1000-snapshot.sampled_at>Math.max(10,snapshot.sample_seconds*3);
    fresh=!stale;
    $("connection").textContent=stale?"Snapshot is stale":"Connected · local dashboard";
    notice(snapshot.monitor_error?`History observer failed: ${snapshot.monitor_error.message}. Pause and Stop remain available.`:historyError?"Progress history is unavailable. Advancement is disabled; Pause and Stop remain available.":stale?"The observer has not produced a fresh snapshot. Advancement is disabled; Pause and Stop remain available.":"");
    render();
  }catch(e){online=false;$("connection").textContent="Disconnected";notice(e.message);if(snapshot)render();}
  finally{refreshing=false;}
}
$("download").onclick=()=>{const data={exported_at:new Date().toISOString(),histories:[...histories.values()]};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));const a=el("a");a.href=url;a.download="experiment-progress.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
refresh();setInterval(refresh,2000);
