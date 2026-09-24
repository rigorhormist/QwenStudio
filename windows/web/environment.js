(() => {
 const $=s=>document.querySelector(s),items=new Map();let state={busy:true,ready:false,language:'auto'},lastLog='';
 const native=(action,extra={})=>window.webkit?.messageHandlers?.studio?.postMessage({action,...extra});
 const expected=[['system','系统与架构'],['display','桌面显示组件'],['storage','本地存储'],['python','Python 运行环境'],...['torch','torchvision','transformers','diffusers','accelerate','Pillow','psutil','filelock','safetensors','Hugging Face Hub','numpy','tokenizers'].map(name=>['package:'+({'Pillow':'PIL','Hugging Face Hub':'huggingface_hub'}[name]||name),name]),['dependencies','依赖完整性'],['pipeline','图像推理接口'],['enhancer','提示词增强接口'],['gpu','GPU 加速'],['curl','模型下载工具'],['ollama','Ollama 对话']];

 let choicesKey='',installStarted=0;
 const stages={checking:'检查当前环境',prepare:'准备独立环境',gpu:'配置 GPU 依赖',installer:'更新下载组件',packages:'解析与安装依赖',download:'正在下载依赖',validate:'检测新环境',complete:'依赖安装完成'};
 const bytes=value=>{if(value>=1e9)return(value/1e9).toFixed(2)+' GB';if(value>=1e6)return(value/1e6).toFixed(1)+' MB';if(value>=1e3)return(value/1e3).toFixed(0)+' KB';return Math.round(value)+' B'};
 function renderChoices(){
  const candidates=state.pythonCandidates||[],select=$('#python-select'),key=JSON.stringify([candidates,state.selectedPython,StudioI18n.locale()]);
  if(key!==choicesKey){choicesKey=key;select.replaceChildren();
   for(const item of candidates){const option=document.createElement('option');option.value=item.executable;option.disabled=!item.compatible;option.textContent='Python '+item.version+' — '+t(item.virtual?'虚拟环境':'系统环境')+(item.compatible?'':' ('+t('不兼容')+')')+' — '+item.executable;select.append(option)}
   if(!candidates.length||state.selectedPython&&!candidates.some(item=>item.executable===state.selectedPython)){const option=document.createElement('option');option.value=state.selectedPython||'';option.textContent=state.selectedPython||t('未找到可用的 Python');option.disabled=true;select.prepend(option)}
   select.value=state.selectedPython||'';
  }
  select.disabled=state.busy||state.pythonLocked||!candidates.length;
  $('#python-browse').disabled=state.busy||state.pythonLocked;
  $('#python-existing').disabled=state.busy||state.pythonLocked;
  $('#dependency-directory-browse').disabled=state.busy||state.pythonLocked;
  $('#dependency-directory').textContent=state.dependencyDirectory||'';
  $('#python-path').textContent=state.selectedPython||'';$('#python-path').hidden=!state.selectedPython;
  $('#python-locked').hidden=!state.pythonLocked;
  $('#cuda-choice').hidden=state.platform!=='windows';$('#cuda-version').value=state.cudaVersion||'cu130';$('#cuda-version').disabled=state.busy;
  $('#dependency-source').value=state.dependencySource||'official';$('#dependency-source').disabled=state.busy;
 }
 function renderProgress(){
  const item=state.progress;$('#installation').hidden=!item;if(!item)return;
  $('#install-stage').textContent=stages[item.stage]||'正在安装依赖…';
  const bar=$('#install-progress'),total=Number(item.total)||0,done=Number(item.downloaded)||0;
  if(item.stage==='complete'){bar.max=1;bar.value=1}else if(item.stage==='download'&&total>0){bar.max=total;bar.value=Math.min(done,total)}else bar.removeAttribute('value');
  $('#install-file').textContent=item.file||'';
  $('#install-bytes').textContent=item.stage==='download'&&done>0?bytes(done)+(total>0?' / '+bytes(total)+'  ('+Math.min(100,Math.floor(done/total*100))+'%)':'')+(item.speed>0?'  '+bytes(item.speed)+'/s':''):'';
 }
 function pending(action,extra={}){state.busy=true;state.ready=false;render();native(action,extra)}
 $('#python-select').onchange=()=>{state.selectedPython=$('#python-select').value;pending('environmentPython',{python:state.selectedPython})};
 $('#python-browse').onclick=()=>native('environmentBrowse');
 $('#python-existing').onclick=()=>native('environmentExisting');
 $('#dependency-directory-browse').onclick=()=>native('environmentDirectory');
 $('#dependency-source').onchange=()=>{state.dependencySource=$('#dependency-source').value;native('environmentSource',{source:state.dependencySource,cuda:$('#cuda-version').value})};
 $('#cuda-version').onchange=()=>{state.cudaVersion=$('#cuda-version').value;native('environmentSource',{source:state.dependencySource||'official',cuda:state.cudaVersion})};
 setInterval(()=>{if(installStarted&&state.busy&&state.progress){const seconds=Math.floor((Date.now()-installStarted)/1000);$('#install-time').textContent=Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')}},1000);

 function row(item){
  let el=document.getElementById('check-'+item.id);if(!el){el=document.createElement('div');el.id='check-'+item.id;el.innerHTML='<span class="check-indicator" aria-hidden="true"></span><div class="check-copy"><div class="check-title"><span></span><small class="optional-label"></small></div><div class="check-detail"></div></div>';$('#check-list').append(el)}
  el.className='check-row '+item.state;
  el.querySelector('.check-indicator').textContent=item.state==='pass'?'🎉':item.state==='fail'?'!':item.state==='checking'?'':'–';
  el.querySelector('.check-title span').textContent=item.title;
  el.querySelector('small').textContent=item.required===false?'可选':'';
  el.querySelector('.check-detail').textContent=item.detail||'尚未检测';
  const status={pass:'通过',fail:'需要处理',checking:'正在检测…',waiting:'尚未检测',optional:'可选'}[item.state]||'尚未检测';
  el.setAttribute('aria-label',t(item.title)+': '+t(status));
 }
 function render(){
  for(const item of items.values())row(item);
  $('#language').value=state.language;
  $('#continue').disabled=state.busy||!state.ready;
  $('#recheck').disabled=state.busy;$('#install').disabled=state.busy||state.ready||!state.canInstall;
  $('#cancel').hidden=!state.busy||state.canCancel===false;
  $('#summary').textContent=state.message||(state.busy?'正在检测…':state.ready?'必需项目已通过，可以开始使用。':'部分必需项目尚未通过，请按提示处理后重新检测。');
  $('#webview-help').hidden=state.platform!=='windows';$('#gpu-help').hidden=state.platform==='macos';
  renderChoices();renderProgress();StudioI18n.render();
 }
 window.environmentUpdate=next=>{
  if(next.reset){state.progress=null;installStarted=0;$('#install-time').textContent='';items.clear();for(const [id,title] of expected)items.set(id,{id,title,state:'waiting',required:!['ollama','enhancer'].includes(id)})}
  if(next.item){items.set(next.item.id,next.item);if(next.item.diagnostic)next.log=(next.log||'')+'\n'+next.item.title+': '+next.item.diagnostic;}
  if(next.log){lastLog=(lastLog+'\n'+next.log).slice(-48000);$('#log').textContent=lastLog;$('#log').scrollTop=$('#log').scrollHeight}
  if(next.progress&&!state.progress)installStarted=Date.now();
  state={...state,...next};if(StudioI18n.choice!==state.language)StudioI18n.setLanguage(state.language);
  render();
 };
 $('#language').onchange=()=>{state.language=$('#language').value;StudioI18n.setLanguage(state.language);native('languageChanged',{language:state.language});render()};
 $('#recheck').onclick=()=>pending('environmentCheck');$('#install').onclick=()=>{state.progress={stage:'checking'};installStarted=Date.now();$('#install-time').textContent='0:00';pending('environmentInstall');$('#installation').scrollIntoView({block:'nearest'})};$('#cancel').onclick=()=>native('environmentCancel');$('#continue').onclick=()=>{if(!state.busy&&state.ready)native('environmentOpen')};
 document.querySelectorAll('[data-help]').forEach(b=>b.onclick=()=>native('environmentHelp',{help:b.dataset.help}));
 window.environmentUpdate({reset:true,language:StudioI18n.choice});native('environmentReady');
})();
