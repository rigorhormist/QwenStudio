using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

internal static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        if(args.SequenceEqual(new[]{"--check-resources"})){
            try{ResourceBundle.Unpack();Environment.ExitCode=0;}catch{Environment.ExitCode=1;}return;
        }
        var customData=Environment.GetEnvironmentVariable("QWEN_STUDIO_DATA");
        var instance=customData==null?"":Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(Encoding.UTF8.GetBytes(Path.GetFullPath(customData).ToUpperInvariant())))[..16];
        using var single = new Mutex(true, "Local\\QwenStudioWindowsDesktop"+instance, out bool first);
        if (!first) {
            foreach (var p in Process.GetProcessesByName("Qwen Studio"))
                if (p.Id != Environment.ProcessId && p.MainWindowHandle != IntPtr.Zero) { ShowWindow(p.MainWindowHandle, 9); SetForegroundWindow(p.MainWindowHandle); }
            return;
        }
        ApplicationConfiguration.Initialize();
        try{Application.Run(new StudioWindow());}
        catch(Exception error){var zh=System.Globalization.CultureInfo.CurrentUICulture.Name.StartsWith("zh");MessageBox.Show((zh?"无法展开应用资源。请检查磁盘空间和本地目录权限。\n\n":"Could not prepare application resources. Check free disk space and local folder permissions.\n\n")+error.Message,"Qwen Studio",MessageBoxButtons.OK,MessageBoxIcon.Error);}
    }
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int n);
}

internal sealed partial class StudioWindow : Form
{
    readonly WebView2 web = new() { Dock = DockStyle.Fill, DefaultBackgroundColor = Color.White };
    readonly StudioTitleBar titlebar;
    readonly string root;
    readonly string data;
    string? configurationError;
    static string DefaultData => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"QwenStudio");
    readonly string token = Guid.NewGuid().ToString("N") + Guid.NewGuid().ToString("N");
    Process? backend;
    string origin = "";
    bool shuttingDown;
    readonly object logLock = new();

    public StudioWindow()
    {
        root = FindRoot();
        data = Environment.GetEnvironmentVariable("QWEN_STUDIO_DATA") ?? LocalSetting("data") ?? DefaultData;
        try { Directory.CreateDirectory(data); } catch { /* The bootstrap page reports storage failures. */ }
        LoadLanguage();
        AutoScaleDimensions = new SizeF(96, 96);
        AutoScaleMode = AutoScaleMode.Dpi;
        Text = "Qwen Studio";
        Icon = Icon.ExtractAssociatedIcon(Environment.ProcessPath!);
        ClientSize = new Size(1220, 820);
        MinimumSize = new Size(860, 650);
        BackColor = Color.White;
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.Sizable;
        Padding = new Padding(4,0,4,4);
        DoubleBuffered = true;
        KeyPreview = true;
        titlebar = new StudioTitleBar(this, async () => await Script("window.studioAction?.('sidebar')"));
        titlebar.RefreshLanguage();
        Controls.Add(web); Controls.Add(titlebar);
        Resize += (_,_) => {
            var edge=(int)Math.Ceiling(4*DeviceDpi/96f);
            Padding=WindowState==FormWindowState.Maximized?Padding.Empty:new Padding(edge,0,edge,edge);
            titlebar.RefreshWindowState();
        };
        Activated += (_,_) => titlebar.SetActive(true);
        Deactivate += (_,_) => titlebar.SetActive(false);
        Shown += async (_,_) => await Initialize();
        FormClosing += OnStudioClosing;
    }

    string? LocalSetting(string key)
    {
        var launch=AppContext.BaseDirectory;var files=new[]{Path.Combine(launch,"settings.local.json"),Path.Combine(Directory.GetParent(launch.TrimEnd(Path.DirectorySeparatorChar))?.FullName??launch,"settings.local.json"),Path.Combine(root,"settings.local.json"),Path.Combine(DefaultData,"locations.json")}.Distinct();
        foreach(var file in files){
            if(!File.Exists(file))continue;
            try{
                using var settings=JsonDocument.Parse(File.ReadAllText(file,Encoding.UTF8));
                if(settings.RootElement.ValueKind!=JsonValueKind.Object)throw new FormatException("Expected a JSON object.");
                if(settings.RootElement.TryGetProperty(key,out var value)){
                    if(value.ValueKind!=JsonValueKind.String||string.IsNullOrWhiteSpace(value.GetString()))throw new FormatException("Expected a non-empty path: "+key);
                    return value.GetString();
                }
            }catch(Exception error){configurationError=file+"\n"+error.Message;return null;}
        }
        return null;
    }

    void RememberLocations()
    {
        // Shell overrides are temporary and must not change another installation's paths.
        if(new[]{"QWEN_STUDIO_DATA","QWEN_STUDIO_MODEL","QWEN_STUDIO_PYTHON"}.Any(key=>!string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable(key))))return;
        try{
            Directory.CreateDirectory(DefaultData);
            var model=LocalSetting("model")??Path.Combine(data,"models","Qwen-Image-2.1");
            var temporary=Path.Combine(DefaultData,"locations-"+Guid.NewGuid()+".tmp");
            File.WriteAllText(temporary,JsonSerializer.Serialize(new{data=Path.GetFullPath(data),model=Path.GetFullPath(model)}),new UTF8Encoding(false));
            File.Move(temporary,Path.Combine(DefaultData,"locations.json"),true);
        }catch(Exception error){Log("Could not remember storage locations: "+error.Message);}
    }

    static string FindRoot()
    {
        return ResourceBundle.Unpack();
    }

    internal void ToggleMaximize() => WindowState=WindowState==FormWindowState.Maximized?FormWindowState.Normal:FormWindowState.Maximized;
    async Task Script(string script) { if(web.CoreWebView2!=null) await web.ExecuteScriptAsync(script); }

    void Log(string line)
    {
        lock(logLock) { try { File.AppendAllText(Path.Combine(data,"desktop.log"),DateTime.Now.ToString("s")+" "+line+Environment.NewLine,Encoding.UTF8); } catch { } }
    }

    bool IsLocal(string value) => Uri.TryCreate(value,UriKind.Absolute,out var u)&&u.GetLeftPart(UriPartial.Authority)==origin;
    void Bridge(object? sender,CoreWebView2WebMessageReceivedEventArgs e)
    {
        var environmentPage=IsEnvironment(e.Source);
        if(!IsLocal(e.Source)&&!environmentPage)return;
        try {
            using var payload=JsonDocument.Parse(e.WebMessageAsJson);var p=payload.RootElement;var action=p.GetProperty("action").GetString();
            if(action=="languageChanged") {SaveLanguage(p.GetProperty("language").GetString()??"auto");return;}
            if(environmentPage){HandleEnvironmentAction(action,p);return;}
            if(action=="checkEnvironment"){ShowEnvironment(true);return;}
            if(action=="revealData")Process.Start(new ProcessStartInfo(data){UseShellExecute=true});
            if(action=="sidebarState")titlebar.SetSidebarCollapsed(p.GetProperty("collapsed").GetBoolean());
            if(action=="saveImage"){
                var name=p.GetProperty("name").GetString()??"";
                if(name!=Path.GetFileName(name)||!name.EndsWith(".png",StringComparison.OrdinalIgnoreCase))return;
                var source=Path.Combine(data,"images",name);if(!File.Exists(source))return;
                using var dialog=new SaveFileDialog {Title=T("保存图片"),Filter="PNG|*.png",FileName="Qwen-"+name[..Math.Min(8,name.Length)]+".png",OverwritePrompt=true};
                if(dialog.ShowDialog(this)==DialogResult.OK)File.Copy(source,dialog.FileName,true);
            }
        } catch(Exception error){Log(error.ToString());MessageBox.Show(this,error.Message,"Qwen Studio");}
    }

    async void OnStudioClosing(object? sender,FormClosingEventArgs e)
    {
        if(shuttingDown)return;
        e.Cancel=true;shuttingDown=true;
        Enabled=false;
        lifetime.Cancel();
        try{if(environmentProcess is {HasExited:false})environmentProcess.Kill(true);}catch(InvalidOperationException){}
        try {
            if(backend is {HasExited:false}){
                using var client=new HttpClient(new HttpClientHandler{UseProxy=false}){Timeout=TimeSpan.FromSeconds(3)};
                client.DefaultRequestHeaders.Add("X-Studio-Token",token);
                try{await client.PostAsync(origin+"/api/shutdown",new StringContent("{}",Encoding.UTF8,"application/json"));await backend.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(12));}catch{if(!backend.HasExited)backend.Kill(true);}
            }
        } finally {
            web.Dispose();BeginInvoke(Close);
        }
    }

    protected override bool ProcessCmdKey(ref Message msg,Keys keyData)
    {
        if(keyData==(Keys.Control|Keys.N)){_=Script("window.studioAction?.('new')");return true;}
        if(keyData==(Keys.Control|Keys.Oemcomma)){_=Script("window.studioAction?.('settings')");return true;}
        return base.ProcessCmdKey(ref msg,keyData);
    }
    protected override void WndProc(ref Message m)
    {
        // Retain the real resizable Windows frame, but paint its titlebar ourselves.
        // This preserves DWM shadows, rounded corners and taskbar-aware maximization.
        if(m.Msg==0x83 && m.WParam!=IntPtr.Zero){m.Result=IntPtr.Zero;return;}
        if(m.Msg==0x24){
            base.WndProc(ref m);
            var monitor=MonitorFromWindow(Handle,2);
            var info=new MonitorInfo{size=Marshal.SizeOf<MonitorInfo>()};
            if(GetMonitorInfo(monitor,ref info)){
                var size=Marshal.PtrToStructure<MinMaxInfo>(m.LParam);
                size.maxPosition=new Point(info.work.Left-info.monitor.Left,info.work.Top-info.monitor.Top);
                size.maxSize=new Point(info.work.Right-info.work.Left,info.work.Bottom-info.work.Top);
                Marshal.StructureToPtr(size,m.LParam,false);
            }
            return;
        }
        const int WM_NCHITTEST=0x84;
        if(m.Msg==WM_NCHITTEST&&WindowState==FormWindowState.Normal){
            var point=PointToClient(new Point((short)((long)m.LParam&0xffff),(short)(((long)m.LParam>>16)&0xffff)));
            int edge=(int)Math.Ceiling(6*DeviceDpi/96f);bool left=point.X<edge,right=point.X>=ClientSize.Width-edge,top=point.Y<edge,bottom=point.Y>=ClientSize.Height-edge;
            if(top||bottom||left||right){m.Result=(IntPtr)(top?(left?13:right?14:12):bottom?(left?16:right?17:15):left?10:11);return;}
        }
        if(m.Msg==WM_NCHITTEST){
            var point=PointToClient(new Point((short)((long)m.LParam&0xffff),(short)(((long)m.LParam>>16)&0xffff)));
            if(point.Y>=0 && point.Y<(int)Math.Round(48*DeviceDpi/96f)){m.Result=(IntPtr)2;return;}
        }
        base.WndProc(ref m);
    }
    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        if(OperatingSystem.IsWindowsVersionAtLeast(10,0,22000)){
            int rounded=2,border=0x00E7E7E7;
            DwmSetWindowAttribute(Handle,33,ref rounded,4);
            DwmSetWindowAttribute(Handle,34,ref border,4);
        }
    }
    [StructLayout(LayoutKind.Sequential)] struct NativeRect{public int Left,Top,Right,Bottom;}
    [StructLayout(LayoutKind.Sequential)] struct MonitorInfo{public int size;public NativeRect monitor,work;public uint flags;}
    [StructLayout(LayoutKind.Sequential)] struct MinMaxInfo{public Point reserved,maxSize,maxPosition,minTrackSize,maxTrackSize;}
    [DllImport("user32.dll")] static extern IntPtr MonitorFromWindow(IntPtr h,uint flags);
    [DllImport("user32.dll",CharSet=CharSet.Auto)] static extern bool GetMonitorInfo(IntPtr h,ref MonitorInfo info);
    [DllImport("dwmapi.dll")] static extern int DwmSetWindowAttribute(IntPtr h,int attribute,ref int value,int size);
}
