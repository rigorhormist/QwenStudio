/* Native folder selection never sends path text through HTML. */
let directoryChoosing=false;
function directoryBusy(){return !!(directoryChoosing||lastStatus?.active||lastStatus?.pending?.length||anyDownloadRunning()||downloadStarting)}
function modelDirectoryActions(target){
 const group=document.createElement('div');group.className='directory-actions';group.dataset.modelDirectory=target;
 for(const [kind,label] of [['download','选择下载目录'],['existing','使用已有模型']]){
  const button=document.createElement('button');button.className='text-button';button.dataset.directoryKind=kind;button.textContent=label;group.append(button);
 }
 return group;
}
document.addEventListener('click',event=>{
 const button=event.target.closest('[data-directory-kind]');if(!button)return;
 if(directoryBusy()){toast('请先停止任务和下载，再更改目录。');return}
 directoryChoosing=true;renderStorageLocations();
 if(!native('chooseModelDirectory',{target:button.closest('[data-model-directory]').dataset.modelDirectory,kind:button.dataset.directoryKind})){
  directoryChoosing=false;renderStorageLocations();toast('请在桌面应用中选择目录。');
 }
});
window.studioDirectorySelected=async selection=>{
 try{
  if(selection.folder){await api('model/location',selection);await refreshStatus();if(selection.kind==='download')toast('下载目录已保存。原有文件不会移动。')}
 }catch(error){toast(error.message)}finally{directoryChoosing=false;renderStorageLocations()}
};
$('#storage-cancel').onclick=safe(async()=>{await api('model/location/cancel',{});await refreshStatus()});
function renderStorageLocations(){
 const storage=lastStatus?.storage;if(!storage)return;
 const busy=directoryBusy();
 document.querySelectorAll('[data-model-directory]').forEach(group=>{
  const locked=group.dataset.modelDirectory==='image'&&storage.imageLocked;
  group.querySelectorAll('button').forEach(button=>{button.disabled=busy||locked;button.title=locked?t('模型目录已由 QWEN_STUDIO_MODEL 指定，请移除该环境变量后再更改。'):''});
 });
 const operation=storage.operation||{},box=$('#storage-operation');
 const anchor=document.querySelector('[data-model-directory="'+(operation.target||'image')+'"]');
 if(anchor&&box.previousElementSibling!==anchor)anchor.after(box);
 box.hidden=!operation.state&&!storage.error;
 const message=operation.state==='verifying'?'正在检查已有模型，请等待检查完成。':operation.state==='complete'?'检查通过，已使用该模型目录。':operation.state==='selected'?'下载目录已保存。原有文件不会移动。':operation.error||storage.error||'';
 $('#storage-message').textContent=message;$('#storage-operation-path').textContent=operation.path||'';
 $('#storage-cancel').hidden=!operation.busy;
 $('#storage-progress').hidden=!operation.busy;$('#storage-progress-label').hidden=!operation.busy;
 $('#storage-progress').value=operation.total?operation.bytes/operation.total:0;
 $('#storage-progress-label').textContent=operation.total?`${(operation.bytes/1e9).toFixed(2)} / ${(operation.total/1e9).toFixed(2)} GB`:'';
 if(operation.busy)$('#download').disabled=true;
 StudioI18n.render();
}
