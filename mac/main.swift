// biar-edit native window: a WKWebView around the local server, with a macOS title bar.
// Build: mac/build.sh  ->  biar-edit.app
import Cocoa
import WebKit

let root = (Bundle.main.object(forInfoDictionaryKey: "BiarRoot") as? String) ?? Bundle.main.bundleURL.deletingLastPathComponent().path + "/biar-edit"
let port = 8790

final class Delegate: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var server: Process?
    var route = ""          // e.g. "queue" from biaredit://queue (notification click)

    func applicationWillFinishLaunching(_ n: Notification) {
        NSAppleEventManager.shared().setEventHandler(self, andSelector: #selector(handleURL(_:reply:)),
                                                     forEventClass: AEEventClass(kInternetEventClass), andEventID: AEEventID(kAEGetURL))
    }

    @objc func handleURL(_ e: NSAppleEventDescriptor, reply: NSAppleEventDescriptor) {
        guard let s = e.paramDescriptor(forKeyword: keyDirectObject)?.stringValue, let u = URL(string: s) else { return }
        let r = (u.host ?? "") + u.path
        route = r.filter { $0.isLetter || $0.isNumber || $0 == "/" }
        if web != nil, web.url != nil {
            web.evaluateJavaScript("location.hash = '#/\(route)'", completionHandler: nil)
            window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
        }
    }

    func applicationDidFinishLaunching(_ n: Notification) {
        startServerIfNeeded(); startWatchdog()
        let cfg = WKWebViewConfiguration()
        cfg.preferences.setValue(true, forKey: "developerExtrasEnabled")
        cfg.mediaTypesRequiringUserActionForPlayback = []      // sounds play as soon as one is picked from a list
        web = WKWebView(frame: .zero, configuration: cfg)
        web.uiDelegate = self; web.navigationDelegate = self
        web.setValue(false, forKey: "drawsBackground")
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1440, height: 900),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                          backing: .buffered, defer: false)
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.title = "biar-edit"
        window.minSize = NSSize(width: 980, height: 640)
        window.setFrameAutosaveName("biar-edit-main")
        let fx = NSVisualEffectView(); fx.material = .sidebar; fx.blendingMode = .behindWindow; fx.state = .active
        window.contentView = fx
        web.frame = fx.bounds; web.autoresizingMask = [.width, .height]; fx.addSubview(web)
        window.center(); window.makeKeyAndOrderFront(nil)
        buildMenu()
        load(attempt: 0)
        NSApp.activate(ignoringOtherApps: true)
    }

    func load(attempt: Int) {
        var req = URLRequest(url: URL(string: "http://localhost:\(port)/?native=1" + (route.isEmpty ? "" : "#/" + route))!)
        req.timeoutInterval = 2
        URLSession.shared.dataTask(with: req) { _, resp, _ in
            DispatchQueue.main.async {
                if resp != nil { self.web.load(URLRequest(url: req.url!)) }
                else if attempt < 40 { DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { self.load(attempt: attempt + 1) } }
                else { self.web.loadHTMLString("<body style='font:15px -apple-system;padding:40px;color:#888'>Sunucu başlamadı. Terminalde <code>baslat.command</code> çalıştırıp tekrar dene.</body>", baseURL: nil) }
            }
        }.resume()
    }

    func portBusy() -> Bool {
        let probe = Process(); probe.launchPath = "/usr/sbin/lsof"; probe.arguments = ["-ti", "tcp:\(port)", "-sTCP:LISTEN"]
        let pipe = Pipe(); probe.standardOutput = pipe; try? probe.run(); probe.waitUntilExit()
        return !pipe.fileHandleForReading.readDataToEndOfFile().isEmpty
    }

    // If the server goes away at any point (another one that held the port quit, a crash), start ours and reload.
    func startWatchdog() {
        Timer.scheduledTimer(withTimeInterval: 4, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            if self.server?.isRunning == true || self.portBusy() { return }
            self.startServerIfNeeded()
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { self.web.reload() }
        }
    }

    func startServerIfNeeded() {
        if portBusy() { return }
        let p = Process()
        p.launchPath = root + "/.venv/bin/python"
        p.arguments = ["-I", root + "/biaredit/server.py", "\(port)"]
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = "/opt/homebrew/opt/ffmpeg-full/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        p.environment = env
        p.standardOutput = FileHandle(forWritingAtPath: "/dev/null"); p.standardError = FileHandle(forWritingAtPath: "/dev/null")
        try? p.run(); server = p
    }

    func applicationWillTerminate(_ n: Notification) { server?.terminate() }
    func applicationShouldTerminateAfterLastWindowClosed(_ s: NSApplication) -> Bool { true }

    // links that leave the app (OAuth logins, "aç" links) open in the default browser
    func webView(_ w: WKWebView, createWebViewWith c: WKWebViewConfiguration, for a: WKNavigationAction, windowFeatures f: WKWindowFeatures) -> WKWebView? {
        if let u = a.request.url { NSWorkspace.shared.open(u) }
        return nil
    }
    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler h: @escaping (WKNavigationActionPolicy) -> Void) {
        if let u = a.request.url, let host = u.host, !["localhost", "127.0.0.1"].contains(host), a.navigationType == .linkActivated {
            NSWorkspace.shared.open(u); h(.cancel); return
        }
        h(.allow)
    }
    func webView(_ w: WKWebView, runJavaScriptAlertPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo, completionHandler c: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = m; a.runModal(); c()
    }
    func webView(_ w: WKWebView, runJavaScriptConfirmPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo, completionHandler c: @escaping (Bool) -> Void) {
        let a = NSAlert(); a.messageText = m; a.addButton(withTitle: "Tamam"); a.addButton(withTitle: "Vazgeç")
        c(a.runModal() == .alertFirstButtonReturn)
    }
    func webView(_ w: WKWebView, runJavaScriptTextInputPanelWithPrompt p: String, defaultText d: String?, initiatedByFrame f: WKFrameInfo, completionHandler c: @escaping (String?) -> Void) {
        let a = NSAlert(); a.messageText = p; a.addButton(withTitle: "Tamam"); a.addButton(withTitle: "Vazgeç")
        let t = NSTextField(frame: NSRect(x: 0, y: 0, width: 320, height: 24)); t.stringValue = d ?? ""; a.accessoryView = t
        c(a.runModal() == .alertFirstButtonReturn ? t.stringValue : nil)
    }

    func buildMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem(); main.addItem(appItem)
        let app = NSMenu(); appItem.submenu = app
        app.addItem(withTitle: "biar-edit Hakkında", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        app.addItem(.separator())
        app.addItem(withTitle: "Yeniden yükle", action: #selector(reload), keyEquivalent: "r")
        app.addItem(.separator())
        app.addItem(withTitle: "biar-edit'ten çık", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let editItem = NSMenuItem(); main.addItem(editItem)
        let edit = NSMenu(title: "Düzen"); editItem.submenu = edit
        edit.addItem(withTitle: "Kes", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "Kopyala", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Yapıştır", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Tümünü seç", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        let winItem = NSMenuItem(); main.addItem(winItem)
        let win = NSMenu(title: "Pencere"); winItem.submenu = win
        win.addItem(withTitle: "Küçült", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        win.addItem(withTitle: "Kapat", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        NSApp.mainMenu = main
    }
    @objc func reload() { web.reload() }
}

let app = NSApplication.shared
let d = Delegate()
app.delegate = d
app.setActivationPolicy(.regular)
app.run()
