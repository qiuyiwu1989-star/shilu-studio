'use strict';
let token = '', current = null, dirty = false, busy = false, modelReady = false;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const notify = text => { $('notice').textContent = text; };
async function api(path, body, raw=false) {
  const res = await fetch(path, {method:body ? 'POST':'GET', headers:{'Content-Type':'application/json','X-Shilu-Token':token},body:body?JSON.stringify(body):undefined});
  if (!res.ok) { const error = await res.json(); throw new Error(error.error || '操作失败'); }
  return raw ? res : res.json();
}
async function run(fn) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('button,input,textarea').forEach(b => b.disabled = true);
  try { await fn(); } catch(e) { notify(e.message); }
  finally { busy = false; document.querySelectorAll('button,input,textarea').forEach(b => b.disabled = false); }
}
function leave() { return !dirty || confirm('当前有未保存的修改，确定离开吗？'); }
function requireSaved() { if (dirty) throw new Error('请先保存修改，再进行此操作。'); }
function fields(c={}) {
  return '<div class="grid">' + [['title','实录标题'],['author','讲者'],['occasion','场合'],['date','日期'],['audience','受众'],['scope_note','取材范围'],['anonymize_note','脱敏要求']].map(([k,label]) => `<label>${label}<input id="c-${k}" value="${esc(c[k] || '')}"></label>`).join('')+'</div>';
}
function config() { return Object.fromEntries(['title','author','occasion','date','audience','scope_note','anonymize_note'].map(k => [k,$('c-'+k).value])); }
async function list() {
  const data = await api('/api/projects');
  $('list').innerHTML = data.items.map(p => `<button class="item ${p.id===current?.id?'active':''}" data-id="${p.id}"><strong>${esc(p.config.title)}</strong><span class="quiet">${esc(p.config.author)} · ${p.review?'已复核':'待整理 / 复核'}</span></button>`).join('');
  $('list').querySelectorAll('button').forEach(b => b.onclick = () => { if(leave()) run(()=>load(b.dataset.id)); });
}
function intake() {
  current=null; dirty=false;
  $('work').innerHTML='<div class="step">01 / 收集现场</div><h1>从一场分享开始。</h1><p class="intro quiet">导入逐字稿，整理章节，对照原文复核，再导出可以独立阅读的实录。保留原意，也保留每一节的出处。</p><div class="card">'+fields({date:new Date().toLocaleDateString('sv-SE')})+'<label>逐字稿文件（TXT / Markdown）<input type="file" id="source-file" accept=".txt,.md"></label><label>逐字稿全文 · 空行区分原稿段落<textarea class="transcript" id="transcript" placeholder="粘贴现场转写，保留已有的说话人与时间码。"></textarea></label><button class="primary" id="create">创建实录</button></div>';
  $('work').oninput=()=>dirty=true;
  $('source-file').onchange=async e=>{if(e.target.files[0]){$('transcript').value=await e.target.files[0].text();dirty=true;}};
  $('create').onclick=()=>run(async()=>{const r=await api('/api/projects',{config:config(),transcript:$('transcript').value});dirty=false;await load(r.project.id);notify('原稿已保存。选择原文分段，或使用已配置的 AI 整理。');});
}
async function load(id) {const r=await api('/api/projects/'+id); current=r.project;dirty=false;render(r.scan);await list();}
function render(scan) {
  const p=current, sections=p.human.length?p.human:(p.engine?.sections||[]);
  $('work').innerHTML=`<div class="step">02 / 整理与复核</div><h1>${esc(p.config.title)}</h1><span class="tag">${p.review?'当前正文已复核':p.human.length?'人工正文已保存':'待整理'}</span> <span class="quiet">版本 ${p.revision} · 本机保存</span>
  <details class="card"><summary>场次信息与整理要求</summary>${fields(p.config)}</details>
  <div class="actions"><button id="verbatim">按原文分段</button><button id="generate">AI 整理初稿</button><span class="quiet">${modelReady?'AI 将把本稿发送至你配置的模型服务':'AI 尚未配置 · 原文分段可离线使用'}</span></div>
  ${p.engine?`<p class="quiet">初稿来源：${p.engine.mode==='live'?'AI 整理 · '+esc(p.engine.model):'原文分段（未调用 AI）'}。${p.human.length?'重新生成的初稿单独保存。':''}</p><button id="adopt">将初稿载入编辑区</button>`:''}
  <div class="card"><h2>逐节整理</h2><p class="quiet">每节可以展开原稿核对。来源编号只能证明引用位置，内容忠实度需要你判断。</p><div id="sections"></div><button id="add">＋ 添加章节</button><div class="actions"><button class="primary" id="save">保存人工正文</button><button id="preview">预览已保存正文</button></div></div>
  <div class="card"><h2>检查提示</h2><div id="scan"></div><details><summary>全部原稿 · ${p.sources.length} 段</summary>${p.sources.map(s=>`<div class="source"><b>${s.id}</b>\n${esc(s.text)}</div>`).join('')}</details></div>
  <div class="card review"><h2>人工复核与交付</h2><label>复核人<input id="reviewer" value="${esc(p.review?.by||'')}"></label><label><input id="confirm-review" type="checkbox">我已逐节核对原意、事实与脱敏，确认当前正文可以交付。</label><div class="actions"><button id="review">确认当前版本</button><button class="primary" id="export">导出文章包</button><button id="backup">导出迁移包</button></div><p class="quiet">文章包：HTML、Markdown、公开 JSON。迁移包含原稿与历史，仅用于私人备份或迁移。导出不会自动上线。</p><p class="quiet">已导出文章包 ${p.exports.length} 次</p></div><div id="preview-area"></div>`;
  renderSections(sections);
  $('scan').textContent=scan ? `${scan.chars} 字 · ${scan.sections} 节 · ${scan.flags.length} 处疑点\n`+scan.flags.map(f=>f.kind+'：'+f.text).join('；')+'\n'+scan.note : '';
  $('work').oninput=e=>{if(!['reviewer','confirm-review'].includes(e.target.id)){dirty=true;notify('有未保存的修改');}};
  for(const [id,mode] of [['verbatim','verbatim'],['generate','live']]) $(id).onclick=()=>run(async()=>{requireSaved();notify(mode==='live'?'AI 整理中，请稍候…':'按原文分段中…');await api(`/api/projects/${p.id}/generate`,{revision:p.revision,mode});await load(p.id);notify('初稿已保存，人工正文保持原样。');});
  if($('adopt')) $('adopt').onclick=()=>{if(!leave())return;if(p.human.length&&!confirm('用 AI / 原文初稿替换编辑区？保存后旧正文仍可从迁移包历史中找回。'))return;renderSections(p.engine.sections);dirty=true;notify('初稿已载入编辑区，尚未保存为人工正文。');};
  $('add').onclick=()=>{const s=collect();s.push({title:'',body:'',source_ids:[]});renderSections(s);dirty=true;};
  $('save').onclick=()=>run(async()=>{await api(`/api/projects/${p.id}/save`,{revision:p.revision,config:config(),sections:collect()});await load(p.id);notify('人工正文已保存，请复核当前版本。');});
  $('review').onclick=()=>run(async()=>{requireSaved();await api(`/api/projects/${p.id}/review`,{revision:p.revision,reviewer:$('reviewer').value,confirmed:$('confirm-review').checked});await load(p.id);notify('当前版本已复核，可以导出文章包。');});
  $('export').onclick=()=>run(async()=>{requireSaved();const r=await api(`/api/projects/${p.id}/export`,{revision:p.revision},true);download(await r.blob(),'shilu-article.zip');await load(p.id);notify('文章包已生成并触发下载；尚未发布到网站。');});
  $('backup').onclick=()=>run(async()=>{requireSaved();const r=await api(`/api/projects/${p.id}/backup`,{revision:p.revision},true);download(await r.blob(),'shilu-project.json');notify('迁移包下载已触发，包含私人原稿，请妥善保存。');});
  $('preview').onclick=()=>run(async()=>{requireSaved();if(!p.human.length)throw new Error('请先保存人工正文');const r=await api(`/api/projects/${p.id}/preview`,{revision:p.revision},true);const f=document.createElement('iframe');f.title='实录正文预览';f.setAttribute('sandbox','');f.srcdoc=await r.text();$('preview-area').replaceChildren(f);f.scrollIntoView({behavior:'smooth'});});
}
function renderSections(sections) {
  $('sections').innerHTML=sections.map((s,i)=>`<div class="section"><label>章节 ${i+1}<input class="title" value="${esc(s.title)}"></label><label>正文<textarea class="body">${esc(s.body)}</textarea></label><label>来源编号（逗号分隔，如 s1,s2）<input class="refs" value="${esc(s.source_ids.join(','))}"></label><details><summary>对照原稿</summary>${current.sources.filter(x=>s.source_ids.includes(x.id)).map(x=>`<div class="source"><b>${x.id}</b>\n${esc(x.text)}</div>`).join('')}</details><button class="remove">移除此节</button></div>`).join('');
  $('sections').querySelectorAll('.remove').forEach(b=>b.onclick=()=>{b.closest('.section').remove();dirty=true;notify('章节已从编辑区移除，保存后生效。');});
}
function collect(){return Array.from($('sections').querySelectorAll('.section')).map(el=>({title:el.querySelector('.title').value,body:el.querySelector('.body').value,source_ids:el.querySelector('.refs').value.split(/[,，\s]+/).filter(Boolean)}));}
function download(blob,name){const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
$('new').onclick=()=>{if(!busy&&leave()){intake();run(list);notify('');}};
$('import').onchange=e=>run(async()=>{if(!leave())return;const file=e.target.files[0];if(!file)return;const r=await api('/api/import',{project:JSON.parse(await file.text())});await load(r.project.id);notify('已导入为新稿件；原稿与人工正文保留，需要重新复核。');});
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
run(async()=>{const s=await api('/api/session');token=s.token;modelReady=s.model_ready;intake();await list();});
