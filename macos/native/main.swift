import Cocoa
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler, NSToolbarDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var backend: Process?
    var backendPort: Int = 0
    var sidebarButton: NSButton!
    var environmentProcess: Process?
    var environmentCancelled = false
    var detectedPython: String?
    var requestedPython: String?
    var backendPython: String?
    var pythonCandidates: [[String:Any]] = []
    var dependencySource = "official"
    var dependencyDirectory:String {
        if let value=try? String(contentsOf:dataURL.appendingPathComponent("environment-directory.txt"),encoding:.utf8).trimmingCharacters(in:.whitespacesAndNewlines),value.hasPrefix("/"){return value}
        return dataURL.appendingPathComponent("runtime").path
    }
    func chooseEnvironmentDirectory(existing:Bool){
        guard !environmentBusy && !pythonLocked else{return}
        let panel=NSOpenPanel();panel.title=t(existing ? "选择已有 Python 环境":"选择依赖下载目录");panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.canCreateDirectories = !existing;panel.allowsMultipleSelection=false;panel.showsHiddenFiles=true
        panel.beginSheetModal(for:window){response in
            guard response == .OK,let folder=panel.url else{return}
            if !existing {
                do{try Data(folder.path.utf8).write(to:self.dataURL.appendingPathComponent("environment-directory.txt"),options:.atomic);self.sendEnvironmentChoices()}catch{self.sendEnvironment(["message":"目录设置无法保存，请检查权限。"])}
                return
            }
            var candidates:[String]=[]
            if let bytes=try? Data(contentsOf:folder.appendingPathComponent("runtime-path.json")),let object=(try? JSONSerialization.jsonObject(with:bytes)) as? [String:String],let path=object["python"]{candidates.append(path.hasPrefix("/") ? path:folder.appendingPathComponent(path).path)}
            candidates += ["bin/python3","bin/python",".venv/bin/python3","venv/bin/python3","runtime/bin/python3"].map{folder.appendingPathComponent($0).path}
            if !candidates.contains(where:{FileManager.default.isExecutableFile(atPath:$0)}){
                let children=(try? FileManager.default.contentsOfDirectory(at:folder,includingPropertiesForKeys:nil)) ?? []
                let managed=children.filter{$0.lastPathComponent.hasPrefix("env-")}.map{$0.appendingPathComponent("bin/python3").path}.filter{FileManager.default.isExecutableFile(atPath:$0)}
                if managed.count>1{self.sendEnvironment(["message":"找到多个环境，请选择具体的 env 子目录。"]);return}
                candidates += managed
            }
            guard let path=candidates.first(where:{FileManager.default.isExecutableFile(atPath:$0)}) else{self.sendEnvironment(["message":"目录中未找到 Python。请选择环境根目录，或直接选择解释器文件。"]);return}
            self.requestedPython=path;self.manualCheck=true;self.checkEnvironment()
        }
    }
    var pythonLocked: Bool { ProcessInfo.processInfo.environment["QWEN_STUDIO_PYTHON"] != nil }
    func sendEnvironmentChoices(){sendEnvironment(["pythonCandidates":pythonCandidates,"selectedPython":detectedPython ?? requestedPython ?? "","pythonLocked":pythonLocked,"dependencySource":dependencySource,"dependencyDirectory":dependencyDirectory,"canInstall":detectedPython != nil && !pythonLocked])}
    func saveDependencySource(_ source:String){guard ["official","tuna"].contains(source) else{return};dependencySource=source;do{try Data(source.utf8).write(to:dataURL.appendingPathComponent("environment-source.txt"),options:.atomic)}catch{logEnvironment(error.localizedDescription)}}
    var environmentBusy = false
    var environmentReady = false
    var environmentVisible = true
    var manualCheck = false
    var shuttingDown = false
    var checks: [String: [String: Any]] = [:]
    var language = "auto"
    lazy var translations = (try? JSONSerialization.jsonObject(with: Data(contentsOf: resources.appendingPathComponent("web/locales.json")))) as? [String: String] ?? [:]
    var resources: URL { Bundle.main.resourceURL! }
    var python: String {
        if let selected=detectedPython {return selected}
        if let override=ProcessInfo.processInfo.environment["QWEN_STUDIO_PYTHON"] {return override}
        let managed=dataURL.appendingPathComponent("runtime/bin/python3").path
        // Preserve working environments when updating the early bundled-runtime build.
        let candidates=[managed,resources.appendingPathComponent("runtime/bin/python3").path,Bundle.main.bundleURL.deletingLastPathComponent().appendingPathComponent(".venv/bin/python3").path]
        return candidates.first(where:{FileManager.default.isExecutableFile(atPath:$0)}) ?? managed
    }
    var environmentURL: URL { resources.appendingPathComponent("web/environment.html") }
    var english: Bool { language == "en" || (language == "auto" && !(Locale.preferredLanguages.first ?? "en").hasPrefix("zh")) }
    func t(_ text: String) -> String { english ? translations[text] ?? text : text }
    let dataURL = ProcessInfo.processInfo.environment["QWEN_STUDIO_DATA"].map { URL(fileURLWithPath: $0) } ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Qwen Studio")
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        if let iconURL = Bundle.main.url(forResource: "AppIcon", withExtension: "icns"),
           let icon = NSImage(contentsOf: iconURL) {
            NSApp.applicationIconImage = icon
        }
        language = (try? String(contentsOf: dataURL.appendingPathComponent("ui-language.txt"), encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)) ?? "auto"
        if let source=try? String(contentsOf:dataURL.appendingPathComponent("environment-source.txt"),encoding:.utf8).trimmingCharacters(in:.whitespacesAndNewlines),["official","tuna"].contains(source){dependencySource=source}
        buildMenu()
        let config = WKWebViewConfiguration()
        config.userContentController.add(self, name: "studio")
        web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = self; web.uiDelegate = self
        web.focusRingType = .none
        web.setValue(false, forKey: "drawsBackground")
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1220, height: 820), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.minSize = NSSize(width: 860, height: 650)
        window.title = "Qwen Studio"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.backgroundColor = .white
        let toolbar = NSToolbar(identifier: "StudioToolbar")
        toolbar.delegate = self
        toolbar.displayMode = .iconOnly
        toolbar.allowsUserCustomization = false
        window.titlebarSeparatorStyle = .none
        window.toolbar = toolbar
        window.toolbarStyle = .unifiedCompact
        window.contentView = web
        window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
        showEnvironment()
    }

    func buildMenu() {
        let menu = NSMenu(); let appItem = NSMenuItem(); menu.addItem(appItem)
        let app = NSMenu(); appItem.submenu = app
        app.addItem(withTitle:t("关于 Qwen Studio"), action: #selector(about), keyEquivalent: "")
        app.addItem(withTitle:t("设置…"), action: #selector(settings), keyEquivalent: ",")
        app.addItem(.separator()); app.addItem(withTitle:t("退出 Qwen Studio"), action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let fileItem=NSMenuItem();menu.addItem(fileItem);let file=NSMenu(title:t("文件"));fileItem.submenu=file
        file.addItem(withTitle:t("新会话"),action:#selector(newSession),keyEquivalent:"n")
        file.addItem(withTitle:t("关闭窗口"),action:#selector(NSWindow.performClose(_:)),keyEquivalent:"w")
        let editItem=NSMenuItem();menu.addItem(editItem);let edit=NSMenu(title:t("编辑"));editItem.submenu=edit
        for (title,action,key) in [("撤销","undo:","z"),("剪切","cut:","x"),("复制","copy:","c"),("粘贴","paste:","v"),("全选","selectAll:","a")] { edit.addItem(withTitle:t(title),action:Selector(action),keyEquivalent:key) }
        NSApp.mainMenu=menu
    }
    @objc func about() { let a=NSAlert();a.messageText="Qwen Studio";a.informativeText=t("本地图像与对话工作室")+"\nQwen-Image-2.1 / Diffusers / Ollama\n"+t("版本")+" 2.2.4";a.addButton(withTitle:t("确定"));a.runModal() }
    @objc func settings(){web.evaluateJavaScript("window.studioAction?.('settings')")}
    @objc func newSession(){web.evaluateJavaScript("window.studioAction?.('new')")}
    @objc func toggleSidebar(){web.evaluateJavaScript("window.studioAction?.('sidebar')")}
    func toolbarAllowedItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] { [NSToolbarItem.Identifier("StudioSidebar"), .flexibleSpace] }
    func toolbarDefaultItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] { [NSToolbarItem.Identifier("StudioSidebar"), .flexibleSpace] }
    func toolbar(_ toolbar: NSToolbar, itemForItemIdentifier identifier: NSToolbarItem.Identifier, willBeInsertedIntoToolbar flag: Bool) -> NSToolbarItem? {
        guard identifier.rawValue == "StudioSidebar" else { return nil }
        let item = NSToolbarItem(itemIdentifier: identifier)
        sidebarButton = NSButton(image: NSImage(systemSymbolName: "sidebar.left", accessibilityDescription: t("切换侧栏"))!, target: self, action: #selector(toggleSidebar))
        sidebarButton.bezelStyle = .texturedRounded
        sidebarButton.isBordered = false
        sidebarButton.focusRingType = .none
        sidebarButton.toolTip = t("收起侧栏")
        sidebarButton.setAccessibilityLabel(t("收起侧栏"))
        item.view = sidebarButton
        item.label = t("侧栏")
        return item
    }
    func sendEnvironment(_ value: [String: Any]) {
        guard environmentVisible && !shuttingDown, let data=try? JSONSerialization.data(withJSONObject:value), let json=String(data:data,encoding:.utf8) else{return}
        web.evaluateJavaScript("window.environmentUpdate?.(\(json))")
    }
    func showEnvironment(manual: Bool = false) {
        guard !shuttingDown else{return}
        manualCheck=manual;environmentVisible=true;environmentReady=false
        sidebarButton?.isEnabled=false
        web.loadFileURL(environmentURL,allowingReadAccessTo:resources.appendingPathComponent("web"))
    }
    func putCheck(_ item: [String: Any]) {
        guard let id=item["id"] as? String else{return}
        checks[id]=item;sendEnvironment(["item":item])
    }
    func check(_ id:String,_ title:String,_ passed:Bool,_ detail:String) {
        putCheck(["id":id,"title":title,"state":passed ? "pass":"fail","detail":detail,"required":true])
    }
    func logEnvironment(_ line:String) {
        let path=dataURL.appendingPathComponent("desktop.log")
        if !FileManager.default.fileExists(atPath:path.path){FileManager.default.createFile(atPath:path.path,contents:nil)}
        if let handle=try? FileHandle(forWritingTo:path){handle.seekToEndOfFile();handle.write(Data((line+"\n").utf8));try? handle.close()}
    }
    // Run Python and installers away from AppKit. A deadline also bounds broken runtimes.
    func run(_ executable:String,_ arguments:[String],timeout:Double,onLine:@escaping(String)->Void) -> Int32 {
        let process=Process();process.executableURL=URL(fileURLWithPath:executable);process.arguments=arguments
        process.currentDirectoryURL=resources
        var env=ProcessInfo.processInfo.environment;env["QWEN_STUDIO_DATA"]=dataURL.path;env["PYTHONUNBUFFERED"]="1";env["PYTHONUTF8"]="1";env["PYTHONDONTWRITEBYTECODE"]="1";env["PIP_NO_INPUT"]="1"
        process.environment=env
        let pipe=Pipe();process.standardOutput=pipe;process.standardError=pipe
        let cancelled=DispatchQueue.main.sync { self.environmentProcess=process;return self.environmentCancelled || self.shuttingDown }
        if cancelled{return -1}
        do{try process.run()}catch{onLine(error.localizedDescription);return -1}
        if DispatchQueue.main.sync(execute:{self.environmentCancelled || self.shuttingDown}){Self.stopTree(process)}
        let deadline=DispatchWorkItem { if process.isRunning { Self.stopTree(process) } }
        DispatchQueue.global().asyncAfter(deadline:.now()+timeout,execute:deadline)
        var pending=Data()
        while true {
            let chunk=pipe.fileHandleForReading.availableData;if chunk.isEmpty{break};pending.append(chunk)
            while let i=pending.firstIndex(of:10){let line=String(decoding:pending[..<i],as:UTF8.self);pending.removeSubrange(...i);onLine(line);DispatchQueue.main.async {self.logEnvironment(line)}}
        }
        if !pending.isEmpty {onLine(String(decoding:pending,as:UTF8.self))}
        process.waitUntilExit();deadline.cancel();return process.terminationStatus
    }
    static func stopTree(_ process:Process) {
        guard process.isRunning else{return}
        func stop(_ pid:Int32) {
            let p=Process();p.executableURL=URL(fileURLWithPath:"/usr/bin/pgrep");p.arguments=["-P",String(pid)];let pipe=Pipe();p.standardOutput=pipe;p.standardError=FileHandle.nullDevice
            if (try? p.run()) != nil {let data=pipe.fileHandleForReading.readDataToEndOfFile();p.waitUntilExit();for line in String(decoding:data,as:UTF8.self).split(separator:"\n"){if let child=Int32(line){stop(child)}}}
            kill(pid,SIGTERM)
        }
        stop(process.processIdentifier)
        DispatchQueue.global().asyncAfter(deadline:.now()+2) {if process.isRunning {kill(process.processIdentifier,SIGKILL)}}
    }
    func checkEnvironment() {
        guard !environmentBusy else{return}
        environmentBusy=true;environmentReady=false;environmentCancelled=false;detectedPython=nil;checks=[:]
        logEnvironment("Environment check started.")
        sendEnvironment(["reset":true,"busy":true,"ready":false,"canCancel":true,"message":"正在检测…","language":language,"platform":"macos"])
        check("system","系统与架构",ProcessInfo.processInfo.operatingSystemVersion.majorVersion>=14,"Apple Silicon / macOS \(ProcessInfo.processInfo.operatingSystemVersionString)")
        check("display","桌面显示组件",true,"WebKit")
        do {try FileManager.default.createDirectory(at:dataURL,withIntermediateDirectories:true);let test=dataURL.appendingPathComponent(".write-check-"+UUID().uuidString);try Data().write(to:test);try FileManager.default.removeItem(at:test);check("storage","本地存储",true,"可以保存会话与图片")}
        catch {check("storage","本地存储",false,"无法写入数据目录，请检查磁盘和权限。")}
        DispatchQueue.global().async { [weak self] in
            guard let self=self else{return};var complete=false;var candidates:[[String:Any]]=[]
            let requested=DispatchQueue.main.sync {ProcessInfo.processInfo.environment["QWEN_STUDIO_PYTHON"] ?? self.requestedPython}
            let discovery=self.run("/bin/zsh",[self.resources.appendingPathComponent("find-python.command").path,"all",requested ?? ""],timeout:180){line in
                if let bytes=line.data(using:.utf8),let candidate=(try? JSONSerialization.jsonObject(with:bytes)) as? [String:Any],let path=candidate["executable"] as? String {
                    if !candidates.contains(where:{$0["executable"] as? String == path}){candidates.append(candidate)}
                }else{DispatchQueue.main.async{self.sendEnvironment(["log":line])}}
            }
            let chosen=candidates.first {item in (item["compatible"] as? Bool == true) && (requested == nil || item["executable"] as? String == requested)}
            let found=chosen?["executable"] as? String
            DispatchQueue.main.sync{self.pythonCandidates=candidates;self.detectedPython=found;self.sendEnvironmentChoices()}
            guard discovery==0,let selected=found else{
                DispatchQueue.main.async{self.environmentProcess=nil;self.check("python","Python 运行环境",false,requested == nil ? "未找到可用的 Python。安装 Apple Silicon 版 Python 3.10–3.13 后重新检测。":"所选 Python 不可用或不兼容，请选择其他解释器。");self.finishChecks(false)};return
            }
            let code=self.run(self.python,["-X","utf8",self.resources.appendingPathComponent("backend/environment_probe.py").path,"--data",self.dataURL.path],timeout:180) {line in
                if let data=line.data(using:.utf8),let item=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any] {
                    if item["type"] as? String == "complete" {complete=true}
                    if item["type"] as? String == "check" {DispatchQueue.main.async {
                        var result=item
                        if item["id"] as? String == "python"{result["detail"]=(item["detail"] as? String ?? "")+"\n"+selected}
                        self.putCheck(result)
                    }}
                } else {DispatchQueue.main.async {self.sendEnvironment(["log":line])}}
            }
            DispatchQueue.main.async {self.environmentProcess=nil;self.finishChecks(code==0 && complete)}
        }
    }
    func finishChecks(_ complete:Bool) {
        environmentBusy=false
        environmentReady=complete && !checks.isEmpty && checks.values.filter {($0["required"] as? Bool) != false}.allSatisfy {$0["state"] as? String == "pass"}
        if environmentReady && ProcessInfo.processInfo.environment["QWEN_STUDIO_PYTHON"] == nil {
            do{let record=try JSONSerialization.data(withJSONObject:["python":python]);try record.write(to:dataURL.appendingPathComponent("runtime-path.json"),options:.atomic)}
            catch{logEnvironment("Could not remember the selected runtime: \(error.localizedDescription)")}
        }
        if !complete && checks["python"]?["state"] as? String != "fail" {check("probe","依赖检查",false,"依赖检查进程退出，请尝试修复环境。")}
        if !complete {for (id,item) in checks where item["state"] as? String == "checking" {var stopped=item;stopped["state"]="fail";stopped["detail"]=environmentCancelled ? "已停止":"检测超时，请重试或修复环境。";checks[id]=stopped;sendEnvironment(["item":stopped])}}
        logEnvironment("Environment check finished. Ready=\(environmentReady). Cancelled=\(environmentCancelled).")
        sendEnvironment(["busy":false,"ready":environmentReady,"message":environmentCancelled ? "已停止。原有环境保持不变。":""])
        if environmentReady && !manualCheck && FileManager.default.fileExists(atPath:dataURL.appendingPathComponent("environment-v1.ready").path) {openStudio()}
    }
    func installEnvironment() {
        if dependencyDirectory==dataURL.appendingPathComponent("runtime").path{try? FileManager.default.createDirectory(atPath:dependencyDirectory,withIntermediateDirectories:true)}
        guard !environmentBusy else{return}
        if environmentReady{sendEnvironment(["busy":false,"ready":true,"message":"环境正常，无需重新安装。"]);return}
        guard detectedPython != nil && !pythonLocked else{sendEnvironment(["message":"请先选择可用的 Python 解释器。"]);return}
        environmentBusy=true;environmentReady=false;environmentCancelled=false;manualCheck=true
        sendEnvironment(["busy":true,"ready":false,"canCancel":true,"message":"正在安装依赖…"])
        DispatchQueue.global().async { [weak self] in
            guard let self=self else{return}
            let code=self.run(self.python,["-X","utf8",self.resources.appendingPathComponent("backend/runtime_setup.py").path,"--root",self.resources.path,"--data",self.dataURL.path,"--python",self.python,"--source",self.dependencySource,"--directory",self.dependencyDirectory],timeout:7200) {line in
                if let bytes=line.data(using:.utf8),let progress=(try? JSONSerialization.jsonObject(with:bytes)) as? [String:Any],progress["type"] as? String == "install_progress" {DispatchQueue.main.async{self.sendEnvironment(["progress":progress])}}
                else{DispatchQueue.main.async{self.sendEnvironment(["log":line])}}
            }
            DispatchQueue.main.async {
                self.environmentProcess=nil;self.environmentBusy=false
                if code==0 {self.requestedPython=nil;self.checkEnvironment()} else {self.sendEnvironment(["busy":false,"ready":false,"message":self.environmentCancelled ? "已停止。原有环境保持不变。":"安装未完成，请查看详细日志后重试。"])}
            }
        }
    }
    func openStudio() {
        guard environmentReady && !environmentBusy else{return}
        if backend?.isRunning == true && backendPort>0 && backendPython == python {enterStudio();return}
        if let previous=backend,previous.isRunning {
            backend=nil;backendPort=0;environmentBusy=true
            DispatchQueue.global().async{Self.stopTree(previous);previous.waitUntilExit();DispatchQueue.main.async{self.environmentBusy=false;self.openStudio()}}
            return
        }
        environmentBusy=true;sendEnvironment(["busy":true,"canCancel":false,"message":"正在启动本地服务…"])
        let process=Process();process.executableURL=URL(fileURLWithPath:python);process.arguments=[resources.appendingPathComponent("backend/server.py").path];process.currentDirectoryURL=resources
        var env=ProcessInfo.processInfo.environment;env["PYTHONUNBUFFERED"]="1";env["QWEN_STUDIO_DATA"]=dataURL.path;env["PYTHONUTF8"]="1";env["PYTHONDONTWRITEBYTECODE"]="1";process.environment=env
        let output=Pipe();process.standardOutput=output
        let log=dataURL.appendingPathComponent("app.log");if !FileManager.default.fileExists(atPath:log.path){FileManager.default.createFile(atPath:log.path,contents:nil)}
        let handle=try? FileHandle(forWritingTo:log);handle?.seekToEndOfFile();process.standardError=handle
        backend=process;backendPython=python
        process.terminationHandler={ [weak self] _ in DispatchQueue.main.async {
            guard let self=self,!self.shuttingDown,self.backend === process else{return}
            self.backendPort=0;self.environmentBusy=false;self.environmentReady=false
            if !self.environmentVisible {self.showEnvironment(manual:true)} else {self.check("service","本地服务",false,"本地服务未能启动，请查看详细日志。");self.sendEnvironment(["busy":false,"ready":false,"message":"本地服务未能启动，请查看详细日志。"]) }
        }}
        do{try process.run()}catch{environmentBusy=false;environmentReady=false;check("service","本地服务",false,"本地服务未能启动，请查看详细日志。");sendEnvironment(["busy":false,"ready":false,"log":error.localizedDescription]);return}
        // Check readiness on the main queue instead of relying on cancellation of a
        // queued work item: a completed handshake must never terminate the server.
        DispatchQueue.main.asyncAfter(deadline:.now()+30) { [weak self] in
            guard let self=self,self.backend === process,self.backendPort==0,process.isRunning else{return}
            self.sendEnvironment(["log":"Local service startup timed out."])
            Self.stopTree(process)
        }
        DispatchQueue.global().async { [weak self] in
            var buffer=Data();var ready=false
            while true {
                let chunk=output.fileHandleForReading.availableData
                if chunk.isEmpty{break};buffer.append(chunk)
                while let newline=buffer.firstIndex(of:10) {
                    let line=Data(buffer[..<newline]);buffer.removeSubrange(...newline)
                    if !ready,let info=(try? JSONSerialization.jsonObject(with:line)) as? [String:Any],let port=info["port"] as? Int,(1...65535).contains(port) {
                        ready=true
                        DispatchQueue.main.async {guard let self=self,self.backend === process,process.isRunning else{return};self.backendPort=port;self.environmentBusy=false;self.enterStudio()}
                    } else if let message=String(data:line,encoding:.utf8),!message.isEmpty {
                        DispatchQueue.main.async {self?.sendEnvironment(["log":message])}
                    }
                }
            }
            if !ready {Self.stopTree(process)}
        }
    }
    func enterStudio() {
        try? Data("ready".utf8).write(to:dataURL.appendingPathComponent("environment-v1.ready"),options:.atomic)
        environmentVisible=false;sidebarButton?.isEnabled=true
        web.load(URLRequest(url:URL(string:"http://127.0.0.1:\(backendPort)/")!))
    }
    func saveLanguage(_ value:String) {
        guard ["auto","zh","en"].contains(value) else{return}
        do {try FileManager.default.createDirectory(at:dataURL,withIntermediateDirectories:true);try Data(value.utf8).write(to:dataURL.appendingPathComponent("ui-language.txt"),options:.atomic);language=value;buildMenu();sidebarButton?.toolTip=t("切换侧栏");sidebarButton?.setAccessibilityLabel(t("切换侧栏"))}
        catch {sendEnvironment(["message":"语言设置无法保存，请检查本地存储。"])}
    }
    func fail(_ text:String){let a=NSAlert();a.messageText="Qwen Studio";a.informativeText=t(text);a.addButton(withTitle:t("确定"));a.runModal()}
    func applicationShouldTerminateAfterLastWindowClosed(_ sender:NSApplication)->Bool {true}
    func applicationWillTerminate(_ notification:Notification){shuttingDown=true;if let p=environmentProcess{Self.stopTree(p)};if let p=backend{Self.stopTree(p)}}
    func webView(_ webView:WKWebView,decidePolicyFor action:WKNavigationAction,decisionHandler:@escaping(WKNavigationActionPolicy)->Void){
        guard let u=action.request.url else{decisionHandler(.cancel);return}
        if (u.host=="127.0.0.1" && u.port==backendPort) || u.standardizedFileURL == environmentURL.standardizedFileURL || u.scheme=="about" {decisionHandler(.allow)} else {if u.scheme=="https"{NSWorkspace.shared.open(u)};decisionHandler(.cancel)}
    }
    func webView(_ webView:WKWebView,runOpenPanelWith parameters:WKOpenPanelParameters,initiatedByFrame frame:WKFrameInfo,completionHandler:@escaping([URL]?)->Void){
        let panel=NSOpenPanel();panel.title=t("添加图片");panel.prompt=t("添加图片");panel.allowsMultipleSelection=true;panel.canChooseDirectories=false;panel.allowedContentTypes=[.png,.jpeg,.webP];panel.beginSheetModal(for:window){result in completionHandler(result == .OK ? panel.urls:nil)}
    }
    func webView(_ webView:WKWebView,runJavaScriptConfirmPanelWithMessage message:String,initiatedByFrame frame:WKFrameInfo,completionHandler:@escaping(Bool)->Void){let a=NSAlert();a.messageText=message;a.addButton(withTitle:t("确定"));a.addButton(withTitle:t("取消"));a.beginSheetModal(for:window){r in completionHandler(r == .alertFirstButtonReturn)}}
    func userContentController(_ controller:WKUserContentController,didReceive message:WKScriptMessage){
        guard message.frameInfo.isMainFrame,let url=message.frameInfo.request.url,let p=message.body as? [String:Any],let action=p["action"] as? String else{return}
        let isEnvironment=url.isFileURL && url.standardizedFileURL == environmentURL.standardizedFileURL
        let isMain=url.host=="127.0.0.1" && url.port==backendPort
        guard isEnvironment || isMain else{return}
        if action=="languageChanged",let value=p["language"] as? String {saveLanguage(value);return}
        if isEnvironment {
            if action=="environmentReady" {if environmentBusy{sendEnvironment(["busy":true,"ready":false,"canCancel":true,"language":language,"platform":"macos","message":"正在检测…"]);sendEnvironmentChoices();for item in checks.values{sendEnvironment(["item":item])}}else{checkEnvironment()}}
            if action=="environmentCancel" {environmentCancelled=true;manualCheck=true;sendEnvironment(["message":"正在停止…","canCancel":false]);if let process=environmentProcess{Self.stopTree(process)}}
            if action=="environmentDirectory"{chooseEnvironmentDirectory(existing:false)}
            if action=="environmentExisting"{chooseEnvironmentDirectory(existing:true)}
            if action=="environmentSource",!environmentBusy,let source=p["source"] as? String {saveDependencySource(source);sendEnvironmentChoices()}
            if action=="environmentPython",!environmentBusy,!pythonLocked,let selected=p["python"] as? String,pythonCandidates.contains(where:{$0["executable"] as? String == selected}){requestedPython=selected;manualCheck=true;checkEnvironment()}
            if action=="environmentBrowse",!environmentBusy,!pythonLocked {
                let panel=NSOpenPanel();panel.title=t("选择 Python 解释器");panel.canChooseDirectories=false;panel.allowsMultipleSelection=false;panel.resolvesAliases=false;panel.showsHiddenFiles=true
                panel.beginSheetModal(for:window){response in if response == .OK,let path=panel.url?.path{self.requestedPython=path;self.manualCheck=true;self.checkEnvironment()}}
            }
            if action=="environmentCheck" {manualCheck=true;checkEnvironment()}
            if action=="environmentInstall" {installEnvironment()}
            if action=="environmentOpen" {openStudio()}
            if action=="environmentHelp",let help=p["help"] as? String,let link=["python":"https://www.python.org/downloads/macos/","ollama":"https://ollama.com/download/mac","gpu":"https://support.apple.com/macos/update"][help],let destination=URL(string:link){NSWorkspace.shared.open(destination)}
            return
        }
        if action=="checkEnvironment" {showEnvironment(manual:true);return}
        if action=="chooseModelDirectory",let target=p["target"] as? String,let kind=p["kind"] as? String,["image","pe-t2i","pe-i2i"].contains(target),["download","existing"].contains(kind){
            let panel=NSOpenPanel();panel.title=t(kind=="existing" ? "选择已有模型目录":"选择模型下载目录");panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.canCreateDirectories=kind=="download";panel.allowsMultipleSelection=false;panel.showsHiddenFiles=true
            panel.beginSheetModal(for:window){response in
                let result:[String:Any] = ["target":target,"kind":kind,"folder":response == .OK ? (panel.url?.path as Any? ?? NSNull()):NSNull()]
                if let bytes=try? JSONSerialization.data(withJSONObject:result),let json=String(data:bytes,encoding:.utf8){self.web.evaluateJavaScript("window.studioDirectorySelected?.("+json+")",completionHandler:nil)}
            };return
        }
        if action=="revealData"{NSWorkspace.shared.open(dataURL)}
        if action=="sidebarState",let collapsed=p["collapsed"] as? Bool { sidebarButton.toolTip=t(collapsed ? "展开侧栏" : "收起侧栏");sidebarButton.setAccessibilityLabel(sidebarButton.toolTip) }
        if action=="saveImage",let name=p["name"] as? String,name==URL(fileURLWithPath:name).lastPathComponent {
            let source=dataURL.appendingPathComponent("images").appendingPathComponent(name)
            guard FileManager.default.fileExists(atPath:source.path) else{return}
            let panel=NSSavePanel();panel.title=t("保存图片");panel.prompt=t("保存图片");panel.allowedContentTypes=[.png];panel.nameFieldStringValue="Qwen-\(name.prefix(8)).png"
            panel.beginSheetModal(for:window){response in if response == .OK,let dest=panel.url {do { let data=try Data(contentsOf:source);try data.write(to:dest,options:.atomic) }catch{ self.fail(error.localizedDescription) }}}
        }
    }
}
let app=NSApplication.shared
let delegate=AppDelegate();app.delegate=delegate;app.run()
