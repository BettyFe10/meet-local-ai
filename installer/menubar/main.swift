// Meet Local AI — icona nella barra dei menu per vedere e controllare il backend.
// Compilata sul Mac da installer/menubar.sh (i segnaposto __REPO__ e __PORT__ vengono sostituiti).
import AppKit

let repoPath = "__REPO__"
let backendPort = "__PORT__"

final class AppDelegate: NSObject, NSApplicationDelegate {
    var item: NSStatusItem!
    var running = false
    var busy = false
    var timer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        rebuild()
        check()
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in self?.check() }
    }

    // ---- stato ----
    func request(_ path: String) -> URLRequest {
        var r = URLRequest(url: URL(string: "http://127.0.0.1:\(backendPort)/api/v1\(path)")!)
        r.setValue("1", forHTTPHeaderField: "X-MeetLocalAI")
        r.timeoutInterval = 2
        r.cachePolicy = .reloadIgnoringLocalCacheData
        return r
    }

    func check() {
        URLSession.shared.dataTask(with: request("/health")) { [weak self] _, resp, _ in
            let ok = (resp as? HTTPURLResponse)?.statusCode == 200
            DispatchQueue.main.async {
                guard let s = self else { return }
                if s.running != ok { s.running = ok }
                s.rebuild()
            }
        }.resume()
    }

    func rebuild() {
        item.button?.title = busy ? "MLA ⏳" : (running ? "MLA 🟢" : "MLA ⚪️")
        item.button?.toolTip = running ? "Meet Local AI: backend acceso" : "Meet Local AI: backend spento"
        let menu = NSMenu()
        let state = NSMenuItem(title: busy ? "Attendere…" : (running ? "Backend acceso" : "Backend spento"), action: nil, keyEquivalent: "")
        state.isEnabled = false
        menu.addItem(state)
        menu.addItem(.separator())
        if !busy {
            if running {
                menu.addItem(entry("Spegni backend", #selector(stopBackend)))
            } else {
                menu.addItem(entry("Accendi backend", #selector(startBackend)))
            }
        }
        menu.addItem(entry("Apri cartella MeetLocalAI", #selector(openData)))
        menu.addItem(.separator())
        menu.addItem(entry("Chiudi questa icona", #selector(quit)))
        item.menu = menu
    }

    func entry(_ title: String, _ action: Selector) -> NSMenuItem {
        let m = NSMenuItem(title: title, action: action, keyEquivalent: "")
        m.target = self
        return m
    }

    // ---- azioni ----
    func runScript(_ name: String) {
        busy = true
        rebuild()
        DispatchQueue.global().async {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/bin/bash")
            p.arguments = ["\(repoPath)/\(name)"]
            p.standardOutput = FileHandle.nullDevice
            p.standardError = FileHandle.nullDevice
            do { try p.run(); p.waitUntilExit() } catch { }
            DispatchQueue.main.async {
                self.busy = false
                self.check()
            }
        }
    }

    @objc func startBackend() { runScript("start_backend.sh") }

    @objc func stopBackend() {
        // se sta registrando o elaborando, chiede conferma prima di spegnere
        URLSession.shared.dataTask(with: request("/status")) { data, _, _ in
            var working = false
            if let d = data, let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
                let rec = j["recording"], proc = j["processing"]
                let queue = (j["queue_length"] as? Int) ?? 0
                working = !(rec == nil || rec is NSNull) || !(proc == nil || proc is NSNull) || queue > 0
            }
            DispatchQueue.main.async {
                if working {
                    let a = NSAlert()
                    a.messageText = "Il backend sta lavorando"
                    a.informativeText = "C'è una registrazione o un'elaborazione in corso. Spegnendo ora la registrazione si interrompe; l'elaborazione riprenderà alla prossima accensione."
                    a.addButton(withTitle: "Lascia acceso")
                    a.addButton(withTitle: "Spegni comunque")
                    NSApp.activate(ignoringOtherApps: true)
                    if a.runModal() != .alertSecondButtonReturn { return }
                }
                self.runScript("stop_backend.sh")
            }
        }.resume()
    }

    @objc func openData() {
        let dir = (repoPath as NSString).deletingLastPathComponent
        NSWorkspace.shared.open(URL(fileURLWithPath: dir))
    }

    @objc func quit() { NSApp.terminate(nil) }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
