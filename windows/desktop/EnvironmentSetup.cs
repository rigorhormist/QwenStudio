using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;

internal sealed partial class StudioWindow
{
    readonly CancellationTokenSource lifetime=new();
    readonly Dictionary<string,CheckItem> checks=new();
    Dictionary<string,string> translations=new();
    Process? environmentProcess;
    CancellationTokenSource? environmentOperation;
    bool environmentVisible=true,environmentBusy,environmentReady,manualCheck;
    string language="auto";
    Panel? fallback;
    const string EnvironmentOrigin="https://studio.local";
    string? detectedPython;
    string Python => detectedPython ?? Environment.GetEnvironmentVariable("QWEN_STUDIO_PYTHON") ?? Path.Combine(root,".venv","Scripts","python.exe");
    bool English => language=="en" || (language=="auto"&&!CultureInfo.CurrentUICulture.Name.StartsWith("zh",StringComparison.OrdinalIgnoreCase));
    internal string T(string text) => English?translations.GetValueOrDefault(text,text):text;
    record CheckItem(string id,string title,string state,string detail,bool required=true,string? diagnostic=null);

    void LoadLanguage()
    {
        try {translations=JsonSerializer.Deserialize<Dictionary<string,string>>(File.ReadAllText(Path.Combine(root,"web","locales.json")))??new();}catch{}
        try {var value=File.ReadAllText(Path.Combine(data,"ui-language.txt")).Trim();if(new[]{"auto","zh","en"}.Contains(value))language=value;}catch{}
    }
    void SaveLanguage(string value)
    {
        if(!new[]{"auto","zh","en"}.Contains(value))return;
        try {Directory.CreateDirectory(data);File.WriteAllText(Path.Combine(data,"ui-language.txt"),value,new UTF8Encoding(false));language=value;titlebar.RefreshLanguage();}
        catch(Exception error){Log(error.ToString());_ = SendEnvironment(new {message="语言设置无法保存，请检查本地存储。"});}
    }
    bool IsEnvironment(string url)=>Uri.TryCreate(url,UriKind.Absolute,out var uri)&&uri.GetLeftPart(UriPartial.Authority)==EnvironmentOrigin&&uri.AbsolutePath=="/environment.html";
    Task SendEnvironment(object value)=>environmentVisible&&!shuttingDown?Script("window.environmentUpdate?.("+JsonSerializer.Serialize(value)+")"):Task.CompletedTask;
    async Task Initialize()
    {
        try {
            var environment=await CoreWebView2Environment.CreateAsync(null,Path.Combine(data,"WebView2"));
            await web.EnsureCoreWebView2Async(environment);
            web.CoreWebView2.Settings.AreDefaultContextMenusEnabled=false;
            web.CoreWebView2.Settings.IsStatusBarEnabled=false;
            web.CoreWebView2.Settings.AreBrowserAcceleratorKeysEnabled=false;
            web.CoreWebView2.Settings.IsZoomControlEnabled=false;
            web.CoreWebView2.SetVirtualHostNameToFolderMapping("studio.local",Path.Combine(root,"web"),CoreWebView2HostResourceAccessKind.DenyCors);
            await web.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync("if(location.origin === 'https://studio.local' || location.hostname === '127.0.0.1'){window.webkit={messageHandlers:{studio:{postMessage:p=>window.chrome.webview.postMessage(p)}}};window.STUDIO_PLATFORM='windows';}");
            web.CoreWebView2.WebMessageReceived+=Bridge;
            web.CoreWebView2.NavigationStarting+=(_,e)=>{if(e.Uri!="about:blank"&&!IsLocal(e.Uri)&&!IsEnvironment(e.Uri)){e.Cancel=true;OpenExternal(e.Uri);}};
            web.CoreWebView2.NewWindowRequested+=(_,e)=>{e.Handled=true;OpenExternal(e.Uri);};
            if(fallback!=null){Controls.Remove(fallback);fallback.Dispose();fallback=null;}
            web.Visible=true;ShowEnvironment();
        } catch(Exception error) {Log(error.ToString());ShowFallback(error.Message);}
    }
    static void OpenExternal(string value)
    {
        if(Uri.TryCreate(value,UriKind.Absolute,out var uri)&&uri.Scheme=="https")Process.Start(new ProcessStartInfo(value){UseShellExecute=true});
    }
    // WebView2 is itself a dependency. This screen must not depend on it or Python.
    void ShowFallback(string diagnostic)
    {
        web.Visible=false;
        if(fallback!=null){Controls.Remove(fallback);fallback.Dispose();}
        fallback=new Panel{Dock=DockStyle.Fill,Padding=new Padding(48),AutoScroll=true,BackColor=Color.White};
        var stack=new FlowLayoutPanel{Dock=DockStyle.Fill,FlowDirection=FlowDirection.TopDown,WrapContents=false,AutoScroll=true};
        var title=new Label{Text=T("环境检测"),AutoSize=true,Font=new Font("Segoe UI",25),Margin=new Padding(0,20,0,24)};
        var choice=new ComboBox{DropDownStyle=ComboBoxStyle.DropDownList,Width=210,Margin=new Padding(0,0,0,24)};
        choice.Items.AddRange([T("跟随系统"),"简体中文","English"]);choice.SelectedIndex=Array.IndexOf(new[]{"auto","zh","en"},language);
        choice.SelectedIndexChanged+=(_,_)=>{SaveLanguage(new[]{"auto","zh","en"}[choice.SelectedIndex]);ShowFallback(diagnostic);};
        stack.Controls.Add(title);stack.Controls.Add(choice);
        stack.Controls.Add(new Label{Text=T("桌面显示组件无法启动。请检查 WebView2 和数据目录权限后重新检测。"),AutoSize=true,MaximumSize=new Size(680,0),Margin=new Padding(0,0,0,22)});
        Button Button(string text,Action action){var b=new Button{Text=T(text),AutoSize=true,FlatStyle=FlatStyle.Flat,BackColor=Color.FromArgb(243,243,243),Padding=new Padding(12,8,12,8),Margin=new Padding(0,0,0,12)};b.FlatAppearance.BorderSize=0;b.Click+=(_,_)=>action();return b;}
        stack.Controls.Add(Button("下载 WebView2",()=>OpenExternal("https://developer.microsoft.com/microsoft-edge/webview2/")));
        stack.Controls.Add(Button("重新检测",()=>_ = Initialize()));
        stack.Controls.Add(new Label{Text=T("诊断详情"),AutoSize=true,Margin=new Padding(0,20,0,6)});
        stack.Controls.Add(new TextBox{Text=diagnostic,ReadOnly=true,Multiline=true,Width=650,Height=160,ScrollBars=ScrollBars.Vertical,BorderStyle=BorderStyle.None,BackColor=Color.White});
        fallback.Controls.Add(stack);Controls.Add(fallback);fallback.BringToFront();titlebar.BringToFront();
    }
    void ShowEnvironment(bool manual=false)
    {
        if(shuttingDown)return;manualCheck=manual;environmentVisible=true;environmentReady=false;
        web.Source=new Uri(EnvironmentOrigin+"/environment.html");
    }
    async void HandleEnvironmentAction(string? action,JsonElement payload)
    {
        try {
            if(action=="environmentReady"){
                if(environmentBusy){
                    await SendEnvironment(new{reset=true,busy=true,ready=false,language,platform="windows"});
                    foreach(var check in checks.Values.ToArray())await SendEnvironment(new{item=check});
                }else await CheckEnvironment();
            }
            if(action=="environmentCheck"){manualCheck=true;await CheckEnvironment();}
            if(action=="environmentInstall")await InstallEnvironment();
            if(action=="environmentCancel")environmentOperation?.Cancel();
            if(action=="environmentOpen")await OpenStudio();
            if(action=="environmentHelp"){
                var help=payload.GetProperty("help").GetString();
                var links=new Dictionary<string,string>{{"python","https://www.python.org/downloads/windows/"},{"webview","https://developer.microsoft.com/microsoft-edge/webview2/"},{"gpu","https://www.nvidia.com/Download/index.aspx"},{"ollama","https://ollama.com/download/windows"}};
                if(help!=null&&links.TryGetValue(help,out var link))OpenExternal(link);
            }
        }catch(Exception error){Log(error.ToString());environmentBusy=false;environmentReady=false;await SendEnvironment(new{busy=false,ready=false,message="依赖检查进程退出，请尝试修复环境。",log=error.Message});}
    }
    async Task Put(CheckItem item){checks[item.id]=item;await SendEnvironment(new{item});}
    async Task<int> Run(string command,IEnumerable<string> arguments,int timeout,Action<string> line)
    {
        var start=new ProcessStartInfo(command){WorkingDirectory=root,UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8};
        foreach(var arg in arguments)start.ArgumentList.Add(arg);
        start.Environment["QWEN_STUDIO_DATA"]=data;start.Environment["PYTHONUTF8"]="1";start.Environment["PYTHONUNBUFFERED"]="1";start.Environment["PIP_NO_INPUT"]="1";
        using var process=new Process{StartInfo=start};environmentProcess=process;
        try{
            process.Start();using var deadline=CancellationTokenSource.CreateLinkedTokenSource(lifetime.Token,environmentOperation?.Token??CancellationToken.None);deadline.CancelAfter(TimeSpan.FromSeconds(timeout));
            async Task Read(StreamReader reader){while(await reader.ReadLineAsync(deadline.Token) is string value){Log(value);line(value);}}
            try{await Task.WhenAll(Read(process.StandardOutput),Read(process.StandardError),process.WaitForExitAsync(deadline.Token));}
            catch(OperationCanceledException){
                if(!process.HasExited){process.Kill(true);await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(8));}
                line(T(environmentOperation?.IsCancellationRequested==true?"已停止。原有环境保持不变。":"检测超时，请重试或修复环境。"));return -1;
            }
            return process.ExitCode;
        }finally{environmentProcess=null;}
    }
    async Task<bool> FindPython()
    {
        detectedPython=null;
        await Put(new("python","Python 运行环境","checking","正在查找已安装的 Python…"));
        JsonElement result=default;
        var code=await Run("powershell.exe",["-NoProfile","-ExecutionPolicy","Bypass","-File",Path.Combine(root,"find-python.ps1"),"-AsJson"],90,line=>{
            try{using var document=JsonDocument.Parse(line);if(document.RootElement.TryGetProperty("found",out _))result=document.RootElement.Clone();}
            catch{_ = SendEnvironment(new{log=line});}
        });
        if(code==0&&result.ValueKind==JsonValueKind.Object&&result.GetProperty("found").GetBoolean()){
            detectedPython=result.GetProperty("python").GetProperty("executable").GetString();
            if(!string.IsNullOrWhiteSpace(detectedPython)&&File.Exists(detectedPython))return true;
        }
        var incompatible=result.ValueKind==JsonValueKind.Object&&result.TryGetProperty("rejected",out var rejected)&&rejected.GetArrayLength()>0;
        var detail=incompatible?"已找到 Python，但版本或架构不兼容。需要 64 位 Python 3.10–3.13。":
            !string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("QWEN_STUDIO_PYTHON"))?"指定的 Python 环境不可用，请检查 QWEN_STUDIO_PYTHON。":
            code!=0?"Python 查找未能完成，请查看详细日志。":"未找到可用的 Python。安装 64 位 Python 3.10–3.13 后重新检测。";
        await Put(new("python","Python 运行环境","fail",detail,diagnostic:result.ValueKind==JsonValueKind.Object?result.GetRawText():null));
        return false;
    }
    async Task CheckEnvironment()
    {
        if(environmentBusy)return;environmentBusy=true;environmentReady=false;checks.Clear();
        environmentOperation?.Dispose();environmentOperation=new();
        var elapsed=Stopwatch.StartNew();Log("Environment check started. Runtime: "+Python);
        await SendEnvironment(new{reset=true,busy=true,ready=false,canCancel=true,message="正在检测…",language,platform="windows"});
        configurationError=null;
        var configuredData=Environment.GetEnvironmentVariable("QWEN_STUDIO_DATA")??LocalSetting("data")??DefaultData;
        if(!string.Equals(Path.GetFullPath(configuredData),Path.GetFullPath(data),StringComparison.OrdinalIgnoreCase))configurationError=T("存储位置已更改，请重启应用。");
        // Read both keys before admission; malformed local settings must not look like an empty library.
        _ = LocalSetting("model");
        if(configurationError!=null)await Put(new("configuration","存储位置设置","fail","无法读取存储位置设置，请检查配置文件。",diagnostic:configurationError));
        var supported=Environment.Is64BitProcess&&RuntimeInformation.OSArchitecture==Architecture.X64&&OperatingSystem.IsWindowsVersionAtLeast(10);
        await Put(new("system","系统与架构",supported?"pass":"fail",supported?RuntimeInformation.OSDescription:"需要 64 位 Windows 10 或更新版本。"));
        await Put(new("display","桌面显示组件","pass","Microsoft Edge WebView2"));
        try{Directory.CreateDirectory(data);var test=Path.Combine(data,".write-check-"+Guid.NewGuid());File.WriteAllText(test,"studio");File.Delete(test);await Put(new("storage","本地存储","pass","可以保存会话与图片"));}
        catch{await Put(new("storage","本地存储","fail","无法写入数据目录，请检查磁盘和权限。"));}
        var complete=false;var exit=-1;
        if(await FindPython()) {
            exit=await Run(Python,["-X","utf8",Path.Combine(root,"backend","environment_probe.py"),"--data",data],180,line=>{
                try{
                    using var json=JsonDocument.Parse(line);var item=json.RootElement;
                    if(item.GetProperty("type").GetString()=="complete")complete=true;
                    else if(item.GetProperty("type").GetString()=="check"){
                        var check=JsonSerializer.Deserialize<CheckItem>(line)!;if(check.id=="python")check=check with {detail=check.detail+"\n"+Python};checks[check.id]=check;_ = SendEnvironment(new{item=check});
                    }
                }catch{_ = SendEnvironment(new{log=line});}
            });
        }
        environmentBusy=false;environmentReady=exit==0&&complete&&checks.Count>0&&checks.Values.Where(i=>i.required).All(i=>i.state=="pass");
        if(environmentReady&&string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("QWEN_STUDIO_PYTHON"))){
            try{
                RememberLocations();
                var temporary=Path.Combine(data,"runtime-path-"+Guid.NewGuid()+".tmp");
                File.WriteAllText(temporary,JsonSerializer.Serialize(new{python=Python}),new UTF8Encoding(false));
                File.Move(temporary,Path.Combine(data,"runtime-path.json"),true);
            }catch(Exception error){Log("Could not remember the selected runtime: "+error.Message);}
        }
        var cancelled=environmentOperation.IsCancellationRequested;
        if(!complete){
            foreach(var check in checks.Values.Where(c=>c.state=="checking").ToArray())await Put(check with{state="fail",detail=cancelled?"已停止":"检测超时，请重试或修复环境。"});
        }
        if(!complete&&(!checks.TryGetValue("python",out var python)||python.state!="fail"))await Put(new("probe","依赖检查","fail","依赖检查进程退出，请尝试修复环境。"));
        Log($"Environment check finished in {elapsed.Elapsed.TotalSeconds:F1}s. Ready={environmentReady}; cancelled={cancelled}.");
        await SendEnvironment(new{busy=false,ready=environmentReady,message=cancelled?"已停止。原有环境保持不变。":""});
        if(environmentReady&&!manualCheck&&File.Exists(Path.Combine(data,"environment-v1.ready")))await OpenStudio();
    }
    async Task InstallEnvironment()
    {
        if(environmentBusy)return;
        if(environmentReady){await SendEnvironment(new{busy=false,ready=true,message="环境正常，无需重新安装。"});return;}
        environmentBusy=true;environmentReady=false;manualCheck=true;
        environmentOperation?.Dispose();environmentOperation=new();
        await SendEnvironment(new{busy=true,ready=false,canCancel=true,message="正在安装依赖…"});
        var script="[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); & '"+Path.Combine(root,"setup.ps1").Replace("'","''")+"'";
        if(!string.IsNullOrWhiteSpace(detectedPython))script+=" -Python '"+detectedPython.Replace("'","''")+"'";
        var encoded=Convert.ToBase64String(Encoding.Unicode.GetBytes(script));
        Log("Dependency repair started. Existing runtime will be preserved.");
        var code=await Run("powershell.exe",["-NoProfile","-ExecutionPolicy","Bypass","-EncodedCommand",encoded],7200,line=>{_ = SendEnvironment(new{log=line});});
        environmentBusy=false;
        if(code==0)await CheckEnvironment();else await SendEnvironment(new{busy=false,ready=false,message=environmentOperation.IsCancellationRequested?"已停止。原有环境保持不变。":"安装未完成，请查看详细日志后重试。"});
    }
    async Task OpenStudio()
    {
        if(!environmentReady||environmentBusy)return;
        if(backend is {HasExited:false}&&origin!=""){EnterStudio();return;}
        environmentBusy=true;await SendEnvironment(new{busy=true,canCancel=false,message="正在启动本地服务…"});
        try{
            var start=new ProcessStartInfo(Python){WorkingDirectory=root,UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8};
            foreach(var argument in new[]{"-X","utf8",Path.Combine(root,"backend","server.py")})start.ArgumentList.Add(argument);
            var model=Environment.GetEnvironmentVariable("QWEN_STUDIO_MODEL")??LocalSetting("model");if(!string.IsNullOrWhiteSpace(model))start.Environment["QWEN_STUDIO_MODEL"]=model;
            start.Environment["PYTHONUTF8"]="1";start.Environment["PYTHONUNBUFFERED"]="1";start.Environment["QWEN_STUDIO_DATA"]=data;start.Environment["QWEN_STUDIO_TOKEN"]=token;start.Environment["NO_PROXY"]="127.0.0.1,localhost";
            var process=new Process{StartInfo=start,EnableRaisingEvents=true};backend=process;
            process.ErrorDataReceived+=(_,e)=>{if(e.Data!=null)Log(e.Data);};
            process.Exited+=(_,_)=>{if(!shuttingDown&&IsHandleCreated)BeginInvoke(async ()=>{if(backend!=process)return;environmentBusy=false;environmentReady=false;origin="";if(!environmentVisible)ShowEnvironment(true);else{await Put(new("service","本地服务","fail","本地服务未能启动，请查看详细日志。"));await SendEnvironment(new{busy=false,ready=false,message="本地服务未能启动，请查看详细日志。"});}});};
            process.Start();process.BeginErrorReadLine();
            var line=await process.StandardOutput.ReadLineAsync(lifetime.Token).AsTask().WaitAsync(TimeSpan.FromSeconds(30));
            if(line==null)throw new Exception(T("本地服务未能启动，请查看详细日志。"));
            using(var info=JsonDocument.Parse(line)){origin="http://127.0.0.1:"+info.RootElement.GetProperty("port").GetInt32();}
            _ = Task.Run(async()=>{while(await process.StandardOutput.ReadLineAsync() is string output)Log(output);});
            File.WriteAllText(Path.Combine(data,"desktop-runtime.json"),JsonSerializer.Serialize(new{url=origin,pid=process.Id,desktop_pid=Environment.ProcessId}),Encoding.UTF8);
            environmentBusy=false;EnterStudio();
        }catch(Exception error){Log(error.ToString());if(backend is {HasExited:false})backend.Kill(true);environmentBusy=false;environmentReady=false;await SendEnvironment(new{busy=false,ready=false,message="本地服务未能启动，请查看详细日志。",log=error.Message});}
    }
    void EnterStudio()
    {
        File.WriteAllText(Path.Combine(data,"environment-v1.ready"),"ready");environmentVisible=false;web.Source=new Uri(origin);
    }
}
