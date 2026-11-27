const API = (window.NEURAL_HUB_API || "").replace(/\/$/, "");
let mode = "login";
let gatewayKey = null;
const $ = id => document.getElementById(id);
const token = () => localStorage.getItem("nh_session");
function api(path, options={}) {
  return fetch(API + path, { ...options, headers: { "Content-Type":"application/json", ...(options.headers||{}), ...(token()?{Authorization:"Bearer "+token()}:{}) } });
}
function setMode(next) {
  mode=next; $("loginTab").classList.toggle("active",mode==="login"); $("registerTab").classList.toggle("active",mode==="register");
  $("formTitle").textContent=mode==="login"?"Welcome back":"Create your account";
  $("formSubtitle").textContent=mode==="login"?"Sign in to manage your API keys.":"Start managing your model access.";
  $("submitAuth").innerHTML=mode==="login"?'Sign in <span>→</span>':'Create account <span>→</span>';
  $("password").autocomplete=mode==="login"?"current-password":"new-password"; $("authMessage").textContent="";
}
$("loginTab").onclick=()=>setMode("login"); $("registerTab").onclick=()=>setMode("register");
$("authForm").onsubmit=async e=>{
  e.preventDefault(); $("authMessage").textContent="Connecting…";
  try{
    const r=await api("/auth/"+mode,{method:"POST",body:JSON.stringify({email:$("email").value,password:$("password").value})});
    const d=await r.json(); if(!r.ok) throw new Error(d.detail||"Request failed");
    localStorage.setItem("nh_session",d.access_token); await showDashboard();
  }catch(err){$("authMessage").textContent=err.message;}
};
async function showDashboard(){
  try{
    const r=await api("/auth/me"); if(!r.ok) throw new Error("Session expired");
    const me=await r.json(); $("userEmail").textContent=me.email;
    $("baseUrl").textContent=API;
    $("authView").classList.add("hidden"); $("appView").classList.remove("hidden");
    await loadKeys(); await loadModels();
  }catch(e){localStorage.removeItem("nh_session");$("appView").classList.add("hidden");$("authView").classList.remove("hidden");}
}
$("logoutBtn").onclick=()=>{localStorage.removeItem("nh_session");location.reload();};
async function loadKeys(){
  const r=await api("/keys"); const data=await r.json(); const list=$("keysList"); list.innerHTML="";
  if(!data.length){list.innerHTML='<p class="muted">No API keys yet.</p>';return;}
  data.forEach(k=>{const row=document.createElement("div");row.className="key-row";const info=document.createElement("div");const title=document.createElement("strong");title.textContent=k.name;const meta=document.createElement("small");meta.textContent=k.prefix+"••••  ·  "+(k.active?"active":"revoked");info.append(title,meta);const btn=document.createElement("button");btn.className="ghost";btn.textContent=k.active?"Revoke":"Revoked";btn.disabled=!k.active;btn.onclick=async()=>{await api("/keys/"+k.id,{method:"DELETE"});loadKeys();};row.append(info,btn);list.append(row);});
}
$("createKey").onclick=async()=>{
  $("createKey").disabled=true;
  try{const r=await api("/keys",{method:"POST",body:JSON.stringify({name:$("keyName").value||"Default"})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Could not create key");gatewayKey=d.api_key;$("newKeyValue").textContent=gatewayKey;$("newKeyBox").classList.remove("hidden");await loadKeys();}
  catch(e){alert(e.message)}finally{$("createKey").disabled=false;}
};
$("copyKey").onclick=async()=>{await navigator.clipboard.writeText(gatewayKey);$("copyKey").textContent="Copied";};
async function loadModels(){
  const box=$("modelList");box.innerHTML="";
  if(!gatewayKey){box.innerHTML='<span class="muted">Create a key to load available models.</span>';return;}
  try{const r=await fetch(API+"/v1/models",{headers:{Authorization:"Bearer "+gatewayKey}});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to load models");if(!d.data.length){box.innerHTML='<span class="muted">No configured models yet. Configure providers on Render.</span>';return;}d.data.forEach(m=>{const s=document.createElement("span");s.className="model-chip";s.textContent=m.id;box.append(s);});}
  catch(e){box.innerHTML='<span class="muted">'+e.message+'</span>';}
}
$("copyExample").onclick=async()=>{
 const sample=`curl ${API}/v1/chat/completions \\\\\n  -H "Authorization: Bearer YOUR_GATEWAY_KEY" \\\\\n  -H "Content-Type: application/json" \\\\\n  -d '{"model":"openai:gpt-4.1-mini","messages":[{"role":"user","content":"Hello"}]}'`;
 await navigator.clipboard.writeText(sample);$("copyExample").textContent="Copied";
};
if(!API||API.includes("YOUR-RENDER-SERVICE")){$("authMessage").textContent="Set your Render backend URL in frontend/config.js before using the site.";}
if(token())showDashboard();
