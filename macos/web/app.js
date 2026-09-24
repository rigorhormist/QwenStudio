const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const paths={model:'M12 3 3 8v8l9 5 9-5V8zM3 8l9 5 9-5M12 13v8',brain:'M9 5a3 3 0 0 0-5 2 4 4 0 0 0-1 7 3 3 0 0 0 6 4M15 5a3 3 0 0 1 5 2 4 4 0 0 1 1 7 3 3 0 0 1-6 4M9 4v16M15 4v16M6 9h3m6 0h3M6 15h3m6 0h3',chevron:'M8 10l4 4 4-4',check:'M5 12l4 4L19 6',plus:'M12 5v14M5 12h14',panel:'M9 3v18M4 3h16v18H4z',search:'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',image:'M3 3h18v18H3zM3 16l5-5 5 5 4-4 4 4M8 7h.01',chat:'M4 4h16v13H9l-5 4z',sliders:'M4 7h7m4 0h5M4 17h3m4 0h9M11 4v6m-4 4v6',arrow:'M12 19V5m-6 6 6-6 6 6','arrow-right':'M4 12h16m-6-6 6 6-6 6',close:'M6 6l12 12M6 18 18 6',sun:'M12 3V1m0 22v-2M3 12H1m22 0h-2M5.6 5.6 4 4m16 16-1.6-1.6M5.6 18.4 4 20M20 4l-1.6 1.6M17 12a5 5 0 1 1-10 0 5 5 0 0 1 10 0',type:'M4 5h16M12 5v15M8 20h8M4 5v3m16-3v3',layers:'M12 3 2 8l10 5 10-5zM2 12l10 5 10-5M2 16l10 5 10-5',folder:'M3 6h7l2 3h9v11H3z',more:'M5 12h.01M12 12h.01M19 12h.01',download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',stop:'M6 6h12v12H6z'};
function icon(name){const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('viewBox','0 0 24 24');s.setAttribute('aria-hidden','true');const p=document.createElementNS(s.namespaceURI,'path');p.setAttribute('d',paths[name]||paths.image);s.append(p);return s}
function icons(root=document){root.querySelectorAll('[data-icon]').forEach(e=>{const i=icon(e.dataset.icon);if(e.tagName==='I')e.replaceWith(i);else e.replaceChildren(i)})}icons();
let mode='image',session=null,sessions=[],attachments=[],job=null,lastStatus=null,polling=false,selectedModel='gpt-oss:20b',thinking='medium',pageName='workspace',controlsSignature='',submitting=false,pendingJobs=[];
const token=$('meta[name=studio-token]').content;
async function api(path,body){const r=await fetch('/api/'+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Studio-Token':token,'X-Studio-Language':StudioI18n.locale()},body:body===undefined?undefined:JSON.stringify(body)});const data=await r.json();if(!r.ok){if(data.environment_error)openEnvironment();throw Error(data.error||'请求失败');}return data}
let toastTimer;function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,5000)}
function safe(fn){return (...args)=>Promise.resolve().then(()=>fn(...args)).catch(e=>toast(e.message))}
function native(action,payload={}){if(window.webkit?.messageHandlers?.studio){window.webkit.messageHandlers.studio.postMessage({action,...payload});return true}return false}
const reduceMotion=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
function motion(el,frames,duration=240){if(!el||reduceMotion())return;el.getAnimations().forEach(a=>a.cancel());return el.animate(frames,{duration,easing:'cubic-bezier(.16,1,.3,1)'});}
function showPage(name){
 closeCreation();closePickers();pageName=name;syncWelcome();
 for(const id of ['workspace','gallery','settings']){const el=$('#'+id);el.hidden=id!==name;}
 motion($('#'+name),[{opacity:.25,filter:'blur(3px)',transform:'translateY(7px)'},{opacity:1,filter:'blur(0px)',transform:'translateY(0)'}]);
 $$('.nav-item').forEach(b=>b.classList.toggle('selected',(name==='workspace'&&b.id==='new-session')||(name==='gallery'&&b.id==='gallery-button')||(name==='settings'&&b.id==='settings-button')));
}
function setMode(value){const changed=mode!==value;mode=value;if(changed)syncWelcome(true);$$('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));$('#prompt').placeholder=mode==='image'?'描述画面，或添加图片…':'输入消息…';$('#attach').hidden=false;$('#options-button').hidden=mode!=='image';$('#transparent-label').hidden=mode!=='image';$('#model-controls').hidden=mode!=='chat';closePickers();updateModelControls();motion($('#composer .composer-toolbar'),[{opacity:.4},{opacity:1}],160);updateSend()}
function thinkingOptions(){return lastStatus?.chat_capabilities?.[selectedModel]?.options||[]}
function updateModelControls(){
 $('#selected-model').setAttribute('translate',selectedModel?'no':'yes');$('#selected-model').textContent=selectedModel||'选择模型';
 const opts=thinkingOptions();if(!opts.some(o=>o.value===thinking))thinking=opts.some(o=>o.value==='medium')?'medium':opts[0]?.value??null;
 $('#selected-thinking').textContent=opts.find(o=>o.value===thinking)?.label||'默认';$('#thinking-picker-button').disabled=!opts.length;
 const signature=JSON.stringify([lastStatus?.chat_models,selectedModel,thinking,opts]);if(signature===controlsSignature)return;controlsSignature=signature;
 $('#model-options').replaceChildren(...(lastStatus?.chat_models||[]).map(name=>pickerOption(name,name===selectedModel,()=>{selectedModel=name;updateModelControls();closePickers()})));
 $('#thinking-options').replaceChildren(...opts.map(o=>pickerOption(o.label,o.value===thinking,()=>{thinking=o.value;updateModelControls();closePickers()})));
}
function pickerOption(label,selected,action){const b=document.createElement('button');b.type='button';b.className='picker-option';b.setAttribute('role','menuitemradio');b.setAttribute('aria-checked',String(selected));b.append(document.createTextNode(label));if(selected)b.append(icon('check'));b.onclick=action;return b}
function closePickers(){for(const id of ['model','thinking']){const p=$('#'+id+'-popover');if(!p)continue;$('#'+id+'-picker-button')?.setAttribute('aria-expanded','false');if(!p.hidden){const a=motion(p,[{opacity:1,transform:'scale(1)'},{opacity:0,transform:'scale(.97)'}],110);if(a)a.onfinish=()=>p.hidden=true;else p.hidden=true;}}}
function togglePicker(id){const p=$('#'+id+'-popover');const opening=p.hidden;closePickers();if(opening){p.hidden=false;motion(p,[{opacity:0,transform:'translateY(5px) scale(.96)',filter:'blur(2px)'},{opacity:1,transform:'translateY(0) scale(1)',filter:'blur(0px)'}],200);$('#'+id+'-picker-button').setAttribute('aria-expanded','true');p.querySelector('[aria-checked=true],button')?.focus()}}
$('#model-picker-button').onclick=()=>togglePicker('model');$('#thinking-picker-button').onclick=()=>togglePicker('thinking');
document.addEventListener('click',e=>{if(!e.target.closest('.model-pill'))closePickers()});
$$('.picker-popover').forEach(p=>p.addEventListener('keydown',e=>{const buttons=[...p.querySelectorAll('button')];let i=buttons.indexOf(document.activeElement);if(e.key==='Escape'){closePickers();$('#'+p.id.replace('-popover','-picker-button')).focus();e.preventDefault()}if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();i=e.key==='Home'?0:e.key==='End'?buttons.length-1:(i+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length;buttons[i]?.focus()}}));
$$('[data-mode]').forEach(b=>b.onclick=()=>setMode(b.dataset.mode));
function updateSend(){$('#send').disabled=!$('#prompt').value.trim()||submitting;const label=submitting?'正在发送':job?'加入队列':mode==='image'?'生成图片':'发送消息';$('#send').setAttribute('aria-label',label);$('#send').title=label}
function renderSessions(){const q=$('#search').value.toLowerCase();$('#sessions').replaceChildren();sessions.filter(s=>s.title.toLowerCase().includes(q)).forEach(s=>{const b=document.createElement('button');b.className='session'+(session?.id===s.id?' current':'');b.setAttribute('translate','no');b.textContent=s.title;b.title=s.title;b.onclick=safe(()=>loadSession(s.id));$('#sessions').append(b)});if(!$('#sessions').children.length){const e=document.createElement('div');e.className='history-empty';e.textContent=q?'没有找到匹配的会话':'暂无会话';$('#sessions').append(e)}}
async function refreshSessions(){sessions=await api('sessions');renderSessions()}
async function loadSession(id){session=await api('sessions/'+id);const lastMode=[...session.messages].reverse().find(m=>m.meta.mode)?.meta.mode;if(lastMode)setMode(lastMode);attachments=[];renderAttachments();showPage('workspace');renderSession();renderSessions()}
function reset(){session=null;attachments=[];$('#prompt').value='';renderAttachments();showPage('workspace');renderSession();renderSessions();$('#prompt').focus();updateSend()}
function imageElement(name){const img=document.createElement('img');img.src='/media/'+encodeURIComponent(name);img.alt='会话中的图片';img.className='result-image';img.loading='lazy';img.tabIndex=0;img.setAttribute('role','button');img.setAttribute('aria-label','查看大图');img.onclick=()=>openImage(name);img.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openImage(name)}};return img}
let viewingImage=null;
function openImage(name){viewingImage=name;$('#viewer-image').src='/media/'+encodeURIComponent(name);$('.viewer-canvas').classList.remove('zoomed');$('#viewer-zoom').textContent='原始尺寸';$('#image-viewer').showModal()}
function toggleImageZoom(){const zoomed=$('.viewer-canvas').classList.toggle('zoomed');$('#viewer-zoom').textContent=zoomed?'适应窗口':'原始尺寸'}
$('#viewer-image').onclick=$('#viewer-zoom').onclick=toggleImageZoom;
$('#viewer-save').onclick=()=>{if(viewingImage)native('saveImage',{name:viewingImage})};
function useImage(name){setMode('image');showPage('workspace');if(attachments.length>=10)return toast('最多添加 10 张参考图');if(!attachments.includes(name))attachments.push(name);renderAttachments();$('#prompt').placeholder='描述修改内容…';$('#prompt').focus()}
function imageButtons(name){const row=document.createElement('div');row.className='image-actions';const edit=document.createElement('button');edit.className='text-button';edit.append(icon('layers'),document.createTextNode('继续修改'));edit.onclick=()=>useImage(name);const save=document.createElement('button');save.className='text-button';save.append(icon('download'),document.createTextNode('保存图片'));save.onclick=()=>{if(!native('saveImage',{name})){const a=document.createElement('a');a.href='/media/'+name;a.download='Qwen-'+name;a.click()}};row.append(edit,save);return row}
let messagesFollowEnd=true,scrollEndFrame=null;
function scrollMessagesToEnd(){cancelAnimationFrame(scrollEndFrame);scrollEndFrame=requestAnimationFrame(()=>{const list=$('#messages');list.scrollTop=list.scrollHeight;messagesFollowEnd=true})}
$('#messages').addEventListener('scroll',()=>{const list=$('#messages');messagesFollowEnd=list.scrollHeight-list.scrollTop-list.clientHeight<48},{passive:true});
new ResizeObserver(()=>{if(messagesFollowEnd)scrollMessagesToEnd()}).observe($('#messages'));
function renderSession(){const before=$('#composer-area').getBoundingClientRect();const wasEmpty=$('#workspace').classList.contains('empty');const empty=!session?.messages.length;$('#workspace').classList.toggle('empty',empty);$('#welcome').hidden=!empty;syncWelcome();$('#thread-title').setAttribute('translate',session?'no':'yes');$('#thread-title').textContent=session?.title||'新会话';$('#session-menu').hidden=!session;const list=$('#messages');list.replaceChildren();(session?.messages||[]).forEach(m=>{const el=document.createElement('article');el.className='message '+m.role+(m.meta.error?' error':'');const role=document.createElement('div');role.className='role';if(m.role!=='user')role.setAttribute('translate','no');role.textContent=m.role==='user'?'你':m.meta.mode==='chat'?(m.meta.model||'Ollama'):'Qwen Studio';el.append(role);if(m.content){const c=document.createElement('div');c.className='content';if(m.role==='user'||(!m.meta.error&&!m.meta.cancelled&&!(m.meta.mode==='image'&&m.images.length)))c.setAttribute('translate','no');c.textContent=m.content;el.append(c)}if(m.images.length){const imgs=document.createElement('div');imgs.className='message-images';m.images.forEach(name=>{const figure=document.createElement('figure');figure.append(imageElement(name));if(m.role==='assistant')figure.append(imageButtons(name));imgs.append(figure)});el.append(imgs);if(m.role==='assistant'){const meta=document.createElement('div');meta.className='image-meta';meta.textContent=`${m.meta.width} × ${m.meta.height}　${m.meta.steps} 步　${m.meta.seconds} 秒`;el.append(meta);if(m.meta.effective_prompt)el.append(promptDetails(m.meta))}}list.append(el)});messagesFollowEnd=true;renderJob();renderTaskTray();scrollMessagesToEnd();if(wasEmpty!==empty&&pageName==='workspace'){const after=$('#composer-area').getBoundingClientRect();motion($('#composer-area'),[{transform:`translate(${before.left-after.left}px,${before.top-after.top}px)`},{transform:'translate(0,0)'}],420);motion(list,[{opacity:0},{opacity:1}],300)}}
let taskTrayOpen=false,taskTrayTimer=null,taskTrayFrame=null;
function setTaskTrayVisible(visible){
 if(visible===taskTrayOpen)return;
 taskTrayOpen=visible;clearTimeout(taskTrayTimer);cancelAnimationFrame(taskTrayFrame);
 const tray=$('#task-tray');tray.inert=!visible;
 if(visible){tray.hidden=false;taskTrayFrame=requestAnimationFrame(()=>{taskTrayFrame=requestAnimationFrame(()=>{if(taskTrayOpen)tray.classList.add('is-open')})})}
 else{if(tray.contains(document.activeElement))$('#prompt').focus({preventScroll:true});tray.classList.remove('is-open');taskTrayTimer=setTimeout(()=>{if(!taskTrayOpen)tray.hidden=true},reduceMotion()?100:280)}
}
function renderTaskTray(){
 const active=lastStatus?.active;
 const visible=!!active||pendingJobs.length>0;
 setTaskTrayVisible(visible);
 if(!visible)return;
 const running=$('#running-task');running.replaceChildren();
 if(active){const text=document.createElement('span');text.textContent=(active.session_id===session?.id?'':t('其他会话：'))+t(active.stage);const view=document.createElement('button');view.type='button';view.textContent='查看';view.onclick=safe(()=>loadSession(active.session_id));const stop=document.createElement('button');stop.type='button';stop.className='danger-button';stop.textContent='停止';stop.onclick=safe(async()=>{await api('cancel',{id:active.id});await refreshStatus()});running.append(text,view,stop)}
 $('#queued-tasks').replaceChildren(...pendingJobs.map((item,i)=>{const row=document.createElement('div');const text=document.createElement('button');text.type='button';text.textContent=`等待中 ${i+1}：${sessions.find(s=>s.id===item.session_id)?.title||'新会话'}`;text.onclick=safe(()=>loadSession(item.session_id));const cancel=document.createElement('button');cancel.type='button';cancel.className='danger-button';cancel.textContent='取消';cancel.onclick=safe(async()=>{await api('cancel',{id:item.id});await refreshStatus();if(session?.id===item.session_id){session=await api('sessions/'+session.id);renderSession()}});row.append(text,cancel);return row}));
}
function renderJob(){const follow=messagesFollowEnd;let el=$('#active-job');if(!job||job.session_id!==session?.id){el?.remove();return}if(el&&el.dataset.job!==job.id){el.remove();el=null}if(!el){el=document.createElement('article');el.dataset.job=job.id;el.id='active-job';el.className='message';const role=document.createElement('div');role.className='role';role.textContent=job.mode==='chat'?'Ollama':'Qwen-Image-2.1';const content=document.createElement('div');content.className='content';content.setAttribute('translate','no');const state=document.createElement('div');state.className='job-state';const stage=document.createElement('span');stage.className='stage';const progress=document.createElement('progress');progress.max=1;const stop=document.createElement('button');stop.className='text-button danger-button';stop.append(icon('stop'),document.createTextNode('停止'));stop.onclick=safe(async()=>{await api('cancel',{id:job.id});stop.disabled=true;stage.textContent='正在停止…'});state.append(stage,progress,stop);el.append(role,content);if(job.mode==='image'){const canvas=document.createElement('div');canvas.className='generation-canvas';canvas.style.aspectRatio=(job.width||1)+' / '+(job.height||1);canvas.style.setProperty('--preview-ratio',(job.width||1)/(job.height||1));const preview=document.createElement('img');preview.alt='低分辨率生成预览';preview.className='generation-preview';const caption=document.createElement('span');caption.className='generation-caption';caption.textContent='正在构图';canvas.append(preview,caption);el.append(canvas)}el.append(state);$('#messages').append(el)}el.querySelector('.content').textContent=job.text||'';el.querySelector('.stage').textContent=job.stage;const pr=el.querySelector('progress');if(job.progress==null)pr.removeAttribute('value');else pr.value=job.progress;pr.hidden=job.mode==='chat';const canvas=el.querySelector('.generation-canvas');if(canvas){canvas.style.aspectRatio=(job.width||1)+' / '+(job.height||1);canvas.style.setProperty('--preview-ratio',(job.width||1)/(job.height||1))}if(canvas&&job.preview&&canvas.dataset.step!==String(job.preview_step)){canvas.dataset.step=job.preview_step;const img=canvas.querySelector('img');img.onload=()=>{canvas.classList.add('has-preview');img.style.filter=`blur(${Math.max(0,5*(1-(job.progress||0)))}px)`};img.src='/media/'+encodeURIComponent(job.preview)+'?step='+job.preview_step;canvas.querySelector('.generation-caption').textContent='生成预览';}if(follow)scrollMessagesToEnd();}
async function pollJob(){if(!job||polling)return;polling=true;try{const latest=await api('jobs/'+job.id);job=latest;if(job.state!=='running'){const sid=job.session_id;if(job.state==='error')toast(job.error);else if(job.enhancement_warning)toast(job.enhancement_warning);const environmentError=job.environment_error;job=null;if(session?.id===sid){session=await api('sessions/'+sid);renderSession()}await refreshSessions();updateSend();await refreshStatus();if(environmentError)openEnvironment()}else renderJob()}catch(e){toast(e.message);job=null;updateSend()}finally{polling=false}}
$('#composer').onsubmit=safe(async e=>{
 e.preventDefault();if(submitting)return;
 const prompt=$('#prompt').value.trim();if(!prompt)return;
 if(mode==='chat'&&attachments.length)return toast('对话模式不处理参考图，请切换到图像模式或移除图片');
 if(mode==='image'&&!lastStatus?.model?.ready){showPage('settings');return toast('请先完成模型下载')}
 submitting=true;updateSend();
 try{
  const options=generationOptions();
  if(mode==='image'&&options.enhance){
   const target=attachments.length?'pe-i2i':'pe-t2i';
   if(!lastStatus?.enhancers?.[target]?.ready){
    const choice=await confirmOptionalEnhancer(target);
    if(choice==='download'){showPage('settings');downloadTarget=target;if(!lastStatus?.model.source)chooseDownloadSource();else await beginDownload(lastStatus.model.source);return}
    if(choice!=='continue')return;
    options.enhance=false;
   }
  }
  if(!session)session=await api('sessions',{});
  const sid=session.id,submittedText=$('#prompt').value;const [width,height]=$('#size').value.split(',').map(Number);
  const created=await api('generate',{session_id:sid,prompt,mode,images:attachments,width,height,...options,steps:Number($('#steps').value),seed:Number($('#seed').value),transparent:$('#transparent').checked,chat_model:selectedModel,think:thinking});
  if(session?.id===sid){if($('#prompt').value===submittedText)$('#prompt').value='';attachments=[];renderAttachments();session=await api('sessions/'+sid);renderSession()}
  if(created.state==='running')job=created;
  if(created.state==='queued')toast('已加入队列，前一个任务完成后自动发送');
  await refreshSessions();await refreshStatus();renderJob();
 }finally{submitting=false;updateSend()}
});
// Prevent the native submit before the async error boundary runs.
$('#composer').addEventListener('submit',e=>e.preventDefault());
$('#prompt').oninput=()=>{updateSend();syncWelcome()};$('#prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('#composer').requestSubmit()}};
$('#new-session').onclick=reset;$('#back').onclick=()=>{showPage('workspace')};
$('#search-button').onclick=()=>{$('#search').hidden=!$('#search').hidden;if(!$('#search').hidden)$('#search').focus()};$('#search').oninput=renderSessions;
function toggleSidebar(){const collapsed=$('#app').classList.toggle('sidebar-hidden');$('#sidebar').inert=collapsed;$('#expand').hidden=!collapsed;native('sidebarState',{collapsed});if(!window.webkit?.messageHandlers?.studio)(collapsed?$('#expand'):$('#collapse')).focus()}
$('#collapse').onclick=$('#expand').onclick=toggleSidebar;
if(window.webkit?.messageHandlers?.studio)document.documentElement.classList.add('native-shell');
$('#settings-button').onclick=$('#model-status').onclick=()=>{showPage('settings');refreshStatus().catch(e=>toast(e.message))};
$$('.close-dialog').forEach(b=>b.onclick=()=>b.closest('dialog').close());$$('dialog').forEach(d=>d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close()}}));
$('#close-settings').onclick=()=>showPage('workspace');$('#options-button').onclick=()=>{const d=$('#options');d.showModal();motion(d,[{opacity:0,transform:'translateY(8px) scale(.98)'},{opacity:1,transform:'translateY(0) scale(1)'}])};$('#apply-options').onclick=()=>{if(!$('#steps').checkValidity()||!$('#seed').checkValidity()||!$('#cfg').checkValidity())return toast('请检查步数和种子的取值范围');$('#options-label').textContent=$('#size').value.split(',').join(' × ');$('#options').close()};
$$('[data-prompt]').forEach(b=>b.onclick=()=>{setMode('image');$('#prompt').value=b.dataset.prompt;$('#transparent').checked=!!b.dataset.transparent;$('#prompt').focus();updateSend()});
function renderAttachments(){$('#attachments').replaceChildren();attachments.forEach((name,index)=>{const el=document.createElement('div');el.className='attachment';el.append(imageElement(name));const number=document.createElement('span');number.className='reference-number';number.setAttribute('translate','no');number.textContent='<image'+(index+1)+'>';el.append(number);const b=document.createElement('button');b.type='button';b.setAttribute('aria-label','移除参考图');b.append(icon('close'));b.onclick=()=>{attachments=attachments.filter(x=>x!==name);renderAttachments()};el.append(b);$('#attachments').append(el)})}
async function addFiles(files){setMode('image');for(const file of files){if(attachments.length>=10){toast('最多添加 10 张参考图');break}if(!file.type.startsWith('image/'))continue;if(file.size>20*1024*1024){toast('图片应小于 20 MB');continue}const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(file)});const result=await api('upload',{data});attachments.push(result.image);renderAttachments()}}
// Circular layout and staggered spring behavior ported from Ramotion/CircleMenu (MIT).
// iOS UIKit is adapted to a top-layer WebKit quarter-arc so it stays inside this desktop window.
let creationOpen=false,creationVersion=0;
const creationItems=[['image','添加图片',()=>$('#file-input').click()],['layers','图像模式',()=>setMode('image')],['chat','对话模式',()=>setMode('chat')],['sliders','图像参数',()=>$('#options-button').click()]];
creationItems.forEach(([symbol,label,action],index)=>{const b=document.createElement('button');b.className='circle-action';b.type='button';b.setAttribute('role','menuitem');b.setAttribute('aria-label',label);b.append(icon(symbol));const tip=document.createElement('span');tip.textContent=label;tip.className='circle-label';b.append(tip);const angle=index*Math.PI/6;b.dataset.x=Math.sin(angle)*118;b.dataset.y=-Math.cos(angle)*118;b.onclick=()=>{closeCreation();action()};$('#creation-menu').append(b)});
function closeCreation(){
 if(!creationOpen)return;creationOpen=false;const version=++creationVersion;$('#attach').setAttribute('aria-expanded','false');document.body.classList.remove('creation-open');
 const buttons=[...$('#creation-menu').children];const animations=buttons.map(b=>{b.getAnimations().forEach(a=>a.cancel());if(reduceMotion())return Promise.resolve();return b.animate([{transform:`translate(${b.dataset.x}px,${b.dataset.y}px) scale(1)`,opacity:1},{transform:'translate(0,0) scale(.3)',opacity:0}],{duration:200,easing:'ease-in',fill:'forwards'}).finished.catch(()=>{})});
 Promise.all(animations).then(()=>{if(version===creationVersion)$('#creation-menu').hidePopover()});
}
function openCreation(){
 if(creationOpen){closeCreation();return}closePickers();creationVersion++;creationOpen=true;const menu=$('#creation-menu'),r=$('#attach').getBoundingClientRect();menu.style.left=Math.min(innerWidth-230,Math.max(10,r.left+r.width/2-22))+'px';menu.style.top=Math.max(12,r.top+r.height/2-22-140)+'px';menu.showPopover();$('#attach').setAttribute('aria-expanded','true');document.body.classList.add('creation-open');
 [...menu.children].forEach((b,i)=>{b.getAnimations().forEach(a=>a.cancel());const end=`translate(${b.dataset.x}px,${b.dataset.y}px) scale(1)`;b.style.transform=end;if(!reduceMotion())b.animate([{transform:'translate(0,0) scale(.2)',opacity:0},{transform:end,opacity:1}],{duration:500,delay:i*35,easing:'cubic-bezier(.16,1.2,.3,1)',fill:'backwards'})});menu.firstElementChild.focus({preventScroll:true});
}
$('#attach').onclick=openCreation;
document.addEventListener('pointerdown',e=>{if(!e.target.closest('#creation-menu,#attach'))closeCreation()});
window.addEventListener('resize',closeCreation);
$('#creation-menu').onkeydown=e=>{const buttons=[...$('#creation-menu').children];if(e.key==='Escape'){closeCreation();$('#attach').focus({preventScroll:true});e.preventDefault()}if(['ArrowRight','ArrowDown','ArrowLeft','ArrowUp','Home','End'].includes(e.key)){let i=buttons.indexOf(document.activeElement);i=e.key==='Home'?0:e.key==='End'?buttons.length-1:(i+(['ArrowRight','ArrowDown'].includes(e.key)?1:-1)+buttons.length)%buttons.length;buttons[i].focus({preventScroll:true});e.preventDefault()}};
$('#file-input').onchange=safe(async e=>{await addFiles(e.target.files);e.target.value=''});
$('#composer').ondragover=e=>{e.preventDefault();document.body.classList.add('drop-active')};$('#composer').ondragleave=()=>document.body.classList.remove('drop-active');$('#composer').ondrop=e=>{e.preventDefault();document.body.classList.remove('drop-active');const files=[...e.dataTransfer.files];safe(()=>addFiles(files))()};
$('#prompt').addEventListener('paste',e=>{const files=[...e.clipboardData.files];if(files.length&&!e.clipboardData.getData('text/plain').trim()){e.preventDefault();safe(()=>addFiles(files))()}});
$('#gallery-button').onclick=safe(async()=>{const images=await api('gallery');showPage('gallery');$('#gallery-grid').replaceChildren();for(const item of images){const el=document.createElement('div');el.className='gallery-item';el.append(imageElement(item.image),imageButtons(item.image));$('#gallery-grid').append(el)}if(!images.length){const p=document.createElement('p');p.className='gallery-empty';p.textContent='暂无图片';$('#gallery-grid').append(p)}});
$('#session-menu').onclick=()=>{$('#rename-input').value=session.title;$('#session-options').showModal()};$('#rename-session').onclick=safe(async()=>{await api('session/rename',{id:session.id,title:$('#rename-input').value});$('#session-options').close();await loadSession(session.id);await refreshSessions()});
$('#delete-session').onclick=safe(async()=>{if(!confirm(t('确定删除这个会话及其聊天记录？')))return;await api('session/delete',{id:session.id});$('#session-options').close();reset();await refreshSessions()});
let downloadTarget='image';
let downloadStarting=false,sourceSaving=false,sourceOptionsSignature='';
function renderDownloadSources(model){
 const select=$('#download-source'),signature=JSON.stringify(model.sources||[]);
 if(signature!==sourceOptionsSignature){sourceOptionsSignature=signature;select.replaceChildren(new Option('首次下载时选择',''),...(model.sources||[]).map(s=>new Option(s.label,s.id)))}
 if(!sourceSaving)select.value=model.source||'';
 select.options[0].disabled=!!model.source;
 select.disabled=anyDownloadRunning()||downloadStarting||sourceSaving;
 $('#download-source-note').textContent=model.downloading?'下载进行中，完成或中断后可更改下载源。':model.ready?'更改下载源不会重新下载已完成的模型。':'更换来源会保留已下载的分段，完成后校验文件。';
}
function chooseDownloadSource(){
 const d=$('#download-source-dialog');$('#source-choice-error').hidden=true;$('#confirm-download').disabled=true;
 $('#download-source-options').replaceChildren(...(lastStatus?.model.sources||[]).map(source=>{const label=document.createElement('label');label.className='source-choice';const input=document.createElement('input');input.type='radio';input.name='model-source';input.value=source.id;input.required=true;input.onchange=()=>$('#confirm-download').disabled=false;const text=document.createElement('span');const name=document.createElement('strong');name.textContent=source.label;const note=document.createElement('small');note.textContent=source.description;text.append(name,note);label.append(input,text);return label}));
 d.showModal();motion(d,[{opacity:0,transform:'scale(.97)'},{opacity:1,transform:'scale(1)'}],220);
}
async function beginDownload(source){
 if(downloadStarting)return;
 downloadStarting=true;$('#download').disabled=true;$('#confirm-download').disabled=true;$('#download-source').disabled=true;
 try{await api('model/download',{source,target:downloadTarget});$('#download-source-dialog').close();await refreshStatus()}
 finally{downloadStarting=false;$('#download').disabled=!!(lastStatus?.model.ready||lastStatus?.model.downloading);$('#confirm-download').disabled=!$('#download-source-options input:checked');$('#download-source').disabled=anyDownloadRunning()}
}
$('#download').onclick=safe(async()=>{if(lastStatus?.model.downloading){await api('model/download/cancel',{target:'image'});await refreshStatus();return}downloadTarget='image';if(!lastStatus?.model.source){chooseDownloadSource();return}await beginDownload(lastStatus.model.source)});
$('#download-source').onchange=safe(async e=>{const source=e.target.value;if(!source)return;sourceSaving=true;e.target.disabled=true;try{await api('preferences',{download_source:source});lastStatus.model.source=source}finally{sourceSaving=false;renderDownloadSources(lastStatus.model)}});
$('#download-source-form').onsubmit=async e=>{e.preventDefault();const source=$('#download-source-options input:checked')?.value;if(!source)return;try{await beginDownload(source)}catch(error){$('#source-choice-error').textContent=error.message;$('#source-choice-error').hidden=false}};
$('#reveal-data').onclick=()=>{if(!native('revealData'))toast(lastStatus?.data||'请从桌面应用打开')};
async function refreshStatus(){lastStatus=await api('status');renderEnhancerDownloads();const m=lastStatus.model;renderDownloadSources(m);const ratio=m.bytes/m.total;const label=m.ready?'图像模型已就绪':m.verifying?'正在校验模型':m.bytes>0?`模型下载 ${Math.floor(ratio*100)}%`:'图像模型待下载';$('#model-status span:last-child').textContent=label;$('#model-status .status-dot').classList.toggle('amber',!m.ready);$('#download-info').textContent=m.ready?'已就绪':`${(m.bytes/1e9).toFixed(1)} / ${(m.total/1e9).toFixed(1)} GB`;$('#model-path').textContent=m.path;$('#download-progress').value=ratio;const speed=m.speed||0;$('#download-speed').textContent=m.ready?'下载完成':m.verifying?'正在校验文件':speed>0?`${speed>=1e6?(speed/1e6).toFixed(1)+' MB/s':(speed/1e3).toFixed(0)+' KB/s'}`:m.downloading?'正在测量速度…':m.bytes>0?'下载已暂停':'等待开始下载';const eta=m.eta;$('#download-eta').textContent=m.ready?'可以开始创作':m.verifying?'即将完成':eta?`预计剩余 ${eta>=3600?Math.floor(eta/3600)+' 小时 ':''}${Math.ceil((eta%3600)/60)} 分钟`:'剩余时间待估算';$('#download').disabled=m.ready||downloadStarting;$('#download').classList.toggle('stop-download',m.downloading);$('#download').textContent=m.ready?'已下载':m.downloading?'停止下载':m.bytes>0?'继续下载':'下载模型';$('#download-error').hidden=!m.error;$('#download-error').textContent=m.error;$('#ollama-state').textContent=lastStatus.ollama?'已连接':'未连接，请启动 Ollama';$('#data-path').textContent=lastStatus.data;const names=lastStatus.chat_models;if(!names.includes(selectedModel))selectedModel=names.includes('gpt-oss:20b')?'gpt-oss:20b':names[0]||'';updateModelControls();pendingJobs=lastStatus.pending||[];if(lastStatus.active?.state==='running'&&!job){job=lastStatus.active;renderJob()}renderTaskTray();updateSend();renderStorageLocations()}
document.addEventListener('keydown',e=>{if(document.querySelector('dialog[open]'))return;if((e.metaKey||e.ctrlKey)&&e.key==='n'){e.preventDefault();reset()}if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();$('#search').hidden=false;$('#search').focus()}});
window.studioAction=action=>{if(action==='new')reset();if(action==='settings')showPage('settings');if(action==='sidebar')toggleSidebar()};
const welcomeCopy={
 zh:{image:['今天，想创作些什么？','把脑海里的画面，变成作品。','从一个想法，开始一幅画。','让灵感，在这里成形。','换个视角，试试新的可能。','下一幅作品，由你开启。'],chat:['今天，想聊点什么？','把问题带来，一起想清楚。','从一个念头，聊到更多可能。','让我们把灵感再往前推一步。','一个好想法，值得聊下去。']},
 en:{image:['What will you create today?',"Let’s bring an idea to life.",'Your next image starts here.','Make a little room for imagination.','Give your ideas a new perspective.',"Let’s make something worth keeping."],chat:['What’s on your mind today?',"Let’s think it through together.",'Every idea starts a conversation.','Where shall we take this idea?',"Let’s explore the possibilities."]}
};
let welcomeLanguage=StudioI18n.choice,welcomeCycle=true,welcomeIndex=0,welcomeKey='',welcomeTimer=null,welcomeVersion=0;
$('#welcome-language').value=welcomeLanguage;$('#welcome-cycle').checked=welcomeCycle;
function welcomeLocale(){return StudioI18n.locale()}
function welcomeAvailable(){return pageName==='workspace'&&!session?.messages.length&&!document.hidden}
function stopWelcome(){clearTimeout(welcomeTimer);welcomeTimer=null;welcomeVersion++;$('#welcome-line').getAnimations({subtree:true}).forEach(a=>a.cancel())}
function scheduleWelcome(){clearTimeout(welcomeTimer);if(welcomeAvailable()&&welcomeCycle&&!reduceMotion()&&!$('#prompt').value.trim())welcomeTimer=setTimeout(rotateWelcome,24000)}
function paintWelcome(animate=true){
 const locale=welcomeLocale(),text=welcomeCopy[locale][mode][welcomeIndex%welcomeCopy[locale][mode].length],line=$('#welcome-line');
 line.replaceChildren();line.lang=locale;line.setAttribute('aria-label',text);
 const units=locale==='zh'?[...text]:text.split(/(\s+)/);
 units.forEach((unit,i)=>{const span=document.createElement('span');span.textContent=unit;span.setAttribute('aria-hidden','true');span.className='welcome-unit';span.dataset.tone=['#bd507c','#9959be','#5c71c6','#367f9f','#428774','#91803c','#b16c39'][i%7];line.append(span);if(animate&&!reduceMotion())span.animate([{opacity:0,color:span.dataset.tone,filter:'blur(6px)',transform:'translateY(12px)',textShadow:'0 2px 12px '+span.dataset.tone},{offset:.28,opacity:1,color:span.dataset.tone,filter:'blur(0px)',transform:'translateY(0)',textShadow:'0 1px 7px '+span.dataset.tone+'44'},{offset:.62,opacity:1,color:span.dataset.tone,filter:'blur(0px)',transform:'translateY(0)',textShadow:'0 0 0 transparent'},{opacity:1,color:'#505050',filter:'blur(0px)',transform:'translateY(0)',textShadow:'0 0 0 transparent'}],{duration:2400,delay:i*Math.min(48,550/units.length),easing:'linear',fill:'backwards'})});
}
async function rotateWelcome(){
 if(!welcomeAvailable()||$('#prompt').value.trim())return;
 const version=++welcomeVersion,units=[...$('#welcome-line').children];
 await Promise.all(units.map((el,i)=>el.animate([{opacity:1,filter:'blur(0px)',transform:'translateY(0)'},{opacity:0,color:el.dataset.tone,filter:'blur(4px)',transform:'translateY(-7px)'}],{duration:220,delay:i*Math.min(12,150/units.length),easing:'ease-in',fill:'forwards'}).finished.catch(()=>{})));
 if(version!==welcomeVersion)return;
 welcomeIndex++;paintWelcome();scheduleWelcome();
}
function syncWelcome(reset=false){
 if(typeof welcomeLanguage==='undefined')return;
 const key=welcomeLocale()+':'+mode;
 if(key!==welcomeKey||reset){stopWelcome();welcomeKey=key;welcomeIndex=0;paintWelcome(welcomeAvailable());}
 if(!welcomeAvailable()||$('#prompt').value.trim()){stopWelcome();return;}
 if(!welcomeTimer)scheduleWelcome();
}
$('#welcome-language').onchange=safe(async e=>{const choice=e.target.value;await api('preferences',{interface_language:choice});welcomeLanguage=choice;StudioI18n.setLanguage(choice);native('languageChanged',{language:choice});syncWelcome(true)});
$('#welcome-cycle').onchange=safe(async e=>{welcomeCycle=e.target.checked;stopWelcome();paintWelcome(false);scheduleWelcome();await api('preferences',{welcome_cycle:welcomeCycle})});
document.addEventListener('visibilitychange',()=>syncWelcome());matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',()=>{stopWelcome();paintWelcome(false);scheduleWelcome()});
async function restorePreferences(){const p=await api('preferences');welcomeLanguage=p.interface_language;StudioI18n.setLanguage(welcomeLanguage);welcomeCycle=p.welcome_cycle;$('#welcome-language').value=welcomeLanguage;$('#welcome-cycle').checked=welcomeCycle;syncWelcome(true)}
document.addEventListener('DOMContentLoaded',()=>{Promise.all([restorePreferences(),refreshSessions(),refreshStatus()]).then(restoreDraft).catch(e=>toast('连接失败：'+e.message));setInterval(()=>refreshStatus().catch(()=>{}),2000);setInterval(pollJob,800);setMode('image');updateSend()},{once:true});

// Native checks navigate to the bundled bootstrap. Keep the unfinished prompt on
// the existing loopback origin so a manual check does not discard the draft.
function openEnvironment(){
 if(lastStatus?.active||pendingJobs.length)return toast('环境修复前，请先停止正在执行和排队的任务。');
 if(anyDownloadRunning())return toast('请先停止任务和下载，再更改目录。');
 sessionStorage.setItem('studio-environment-draft',JSON.stringify({sessionId:session?.id,prompt:$('#prompt').value,attachments,mode}));
 if(!native('checkEnvironment'))toast('请从桌面应用打开');
}
async function restoreDraft(){
 const raw=sessionStorage.getItem('studio-environment-draft');if(!raw)return;
 sessionStorage.removeItem('studio-environment-draft');
 try{const saved=JSON.parse(raw);if(saved.sessionId)await loadSession(saved.sessionId);setMode(saved.mode==='chat'?'chat':'image');$('#prompt').value=saved.prompt||'';attachments=Array.isArray(saved.attachments)?saved.attachments:[];renderAttachments();updateSend()}catch{}
}
$('#environment-check').onclick=openEnvironment;
if(window.STUDIO_PLATFORM==='windows'||navigator.userAgent.includes('Windows')){
 document.querySelectorAll('kbd').forEach(e=>e.textContent=e.textContent.replace('⌘','Ctrl'));
 document.querySelector('.composer-foot span').textContent='Ctrl ↵';
 document.querySelector('#reveal-data').lastChild.textContent='在文件资源管理器中打开';
}
window.addEventListener('studio-language',()=>{if(typeof welcomeLanguage!=='undefined'){welcomeLanguage=StudioI18n.choice;syncWelcome(true)}});
