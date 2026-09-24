/* Image controls share one contract with both desktop backends. */
function generationOptions(){return {enhance:$('#enhance').checked,ratio_mode:$('#ratio-mode').value,exact_text:$('#exact-text').value,negative_prompt:$('#negative-prompt').value,cfg:Number($('#cfg').value),count:Number($('#image-count').value)}}
function anyDownloadRunning(){return !!(lastStatus?.storage?.operation?.busy||lastStatus?.model.downloading||Object.values(lastStatus?.enhancers||{}).some(m=>m.downloading))}
function renderEnhancerDownloads(){
 const container=$('#enhancer-downloads');
 for(const [target,title] of [['pe-t2i','生图增强模型'],['pe-i2i','改图增强模型']]){
  let row=container.querySelector('[data-target="'+target+'"]');
  if(!row){
   row=document.createElement('div');row.className='enhancer-row';row.dataset.target=target;
   const heading=document.createElement('strong');heading.textContent=title;
   const detail=document.createElement('p');detail.className='muted small';
   const progress=document.createElement('progress');progress.max=1;
   const button=document.createElement('button');button.className='text-button';button.type='button';
   button.onclick=safe(async()=>{if(lastStatus?.enhancers?.[target]?.downloading){await api('model/download/cancel',{target});await refreshStatus();return}downloadTarget=target;if(!lastStatus?.model.source){chooseDownloadSource();return}await beginDownload(lastStatus.model.source)});
   const error=document.createElement('p');error.className='error-text';row.append(heading,detail,progress,button,error);
   const path=document.createElement('p');path.className='path model-directory-path';path.setAttribute('translate','no');row.append(path);
   row.append(modelDirectoryActions(target));container.append(row);
  }
  const model=lastStatus?.enhancers?.[target];if(!model)continue;
  row.querySelector('.model-directory-path').textContent=model.path||'';
  const detail=row.querySelector('.muted');detail.textContent=model.ready?'已就绪':`${(model.bytes/1e9).toFixed(1)} / ${(model.total/1e9).toFixed(1)} GB`+(model.downloading?'　'+(model.speed>0?(model.speed/1e6).toFixed(1)+' MB/s':t('正在测量速度…')):'');
  row.querySelector('progress').value=model.total?model.bytes/model.total:0;
  const button=row.querySelector('button');button.disabled=model.ready||downloadStarting||lastStatus?.storage?.operation?.busy;button.classList.toggle('stop-download',model.downloading);button.textContent=model.ready?'已下载':model.downloading?'停止下载':model.bytes?'继续下载':'下载模型';
  row.querySelector('.error-text').textContent=model.error||'';row.querySelector('.error-text').hidden=!model.error;
 }
}
function promptDetails(meta){
 const details=document.createElement('details');details.className='prompt-details';
 const summary=document.createElement('summary');summary.textContent='生成详情';details.append(summary);
 if(meta.enhancement_warning){const note=document.createElement('p');note.className='muted small';note.textContent=meta.enhancement_warning;details.append(note)}
 for(const [label,value] of [['原始提示词',meta.original_prompt],['增强提示词',meta.enhanced_prompt],['实际提示词',meta.effective_prompt],['随机种子',(meta.seeds||[meta.seed]).join(', ')]]){
  if(value===undefined||value===null)continue;
  const heading=document.createElement('p');heading.className='muted small';heading.textContent=label;
  const body=document.createElement('p');body.className='prompt-value';body.setAttribute('translate','no');body.textContent=String(value);details.append(heading,body);
 }
 return details;
}
$('#size').addEventListener('change',()=>{$('#ratio-mode').value='fixed'});
$('#enhance').addEventListener('change',()=>{if(!$('#enhance').checked&&$('#ratio-mode').value==='auto')$('#ratio-mode').value='fixed'});
$('#negative-prompt').addEventListener('input',()=>{if(!$('#negative-prompt').value.trim())$('#cfg').value=1;else if(Number($('#cfg').value)<=1)$('#cfg').value=2});
$('#text-preset').onclick=()=>{$('#size').value='2048,2048';$('#steps').value=40;$('#ratio-mode').value='auto';$('#enhance').checked=true;$('#options-label').textContent='2048 × 2048';$('#exact-text').focus();toast('已选择 2K 和 40 步，请填写图中文字')};

// The reminder owns focus until the user chooses. No prompt is cleared on dismissal.
const dismissedEnhancerReminders=new Set();
async function confirmOptionalEnhancer(target){
 if(dismissedEnhancerReminders.has(target))return 'continue';
 const dialog=$('#enhancer-reminder');dialog.returnValue='cancel';
 $('#enhancer-reminder-copy').textContent=target==='pe-i2i'?'尚未下载改图增强模型。可以直接使用当前提示词改图。':'尚未下载生图增强模型。可以直接使用当前提示词生图。';
 $('#enhancer-reminder-hide').checked=false;
 return new Promise(resolve=>{
  $('#enhancer-reminder-continue').onclick=()=>dialog.close('continue');
  $('#enhancer-reminder-download').onclick=()=>dialog.close('download');
  dialog.addEventListener('close',()=>{
   if(dialog.returnValue==='continue'&&$('#enhancer-reminder-hide').checked)dismissedEnhancerReminders.add(target);
   if(dialog.returnValue==='cancel')$('#prompt').focus();
   resolve(dialog.returnValue);
  },{once:true});
  StudioI18n.render();dialog.showModal();
  motion(dialog,[{opacity:0,transform:'translateY(8px) scale(.98)'},{opacity:1,transform:'none'}]);
 });
}
