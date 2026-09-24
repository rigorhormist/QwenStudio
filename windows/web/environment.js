(() => {
 const $=s=>document.querySelector(s),items=new Map();let state={busy:true,ready:false,language:'auto'},lastLog='';
 const native=(action,extra={})=>window.webkit?.messageHandlers?.studio?.postMessage({action,...extra});
 const expected=[['system','系统与架构'],['display','桌面显示组件'],['storage','本地存储'],['python','Python 运行环境'],...['torch','torchvision','transformers','diffusers','accelerate','Pillow','psutil','filelock','safetensors','Hugging Face Hub','numpy','tokenizers'].map(name=>['package:'+({'Pillow':'PIL','Hugging Face Hub':'huggingface_hub'}[name]||name),name]),['dependencies','依赖完整性'],['pipeline','图像推理接口'],['enhancer','提示词增强接口'],['gpu','GPU 加速'],['curl','模型下载工具'],['ollama','Ollama 对话']];
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
  $('#recheck').disabled=state.busy;$('#install').disabled=state.busy||state.ready;
  $('#cancel').hidden=!state.busy||state.canCancel===false;
  $('#summary').textContent=state.message||(state.busy?'正在检测…':state.ready?'必需项目已通过，可以开始使用。':'部分必需项目尚未通过，请按提示处理后重新检测。');
  $('#webview-help').hidden=state.platform!=='windows';$('#gpu-help').hidden=state.platform==='macos';
  StudioI18n.render();
 }
 window.environmentUpdate=next=>{
  if(next.reset){items.clear();for(const [id,title] of expected)items.set(id,{id,title,state:'waiting',required:!['ollama','enhancer'].includes(id)})}
  if(next.item){items.set(next.item.id,next.item);if(next.item.diagnostic)next.log=(next.log||'')+'\n'+next.item.title+': '+next.item.diagnostic;}
  if(next.log){lastLog=(lastLog+'\n'+next.log).slice(-48000);$('#log').textContent=lastLog;$('#log').scrollTop=$('#log').scrollHeight}
  state={...state,...next};if(StudioI18n.choice!==state.language)StudioI18n.setLanguage(state.language);
  render();
 };
 $('#language').onchange=()=>{state.language=$('#language').value;StudioI18n.setLanguage(state.language);native('languageChanged',{language:state.language});render()};
 $('#recheck').onclick=()=>native('environmentCheck');$('#install').onclick=()=>native('environmentInstall');$('#cancel').onclick=()=>native('environmentCancel');$('#continue').onclick=()=>{if(!state.busy&&state.ready)native('environmentOpen')};
 document.querySelectorAll('[data-help]').forEach(b=>b.onclick=()=>native('environmentHelp',{help:b.dataset.help}));
 window.environmentUpdate({reset:true,language:StudioI18n.choice});native('environmentReady');
})();
