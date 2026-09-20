// Native macOS 15+ ScreenCaptureKit companion. Built by Cargo with Xcode 16+.
// CLI inputs are backend-owned JSON/files; it never accepts a shell command.
import Foundation
import AppKit
import ScreenCaptureKit
import AVFoundation
import CoreGraphics

struct Rect: Codable { let x: Int; let y: Int; let width: Int; let height: Int }
struct Request: Codable { let sourceId: String; let mode: String; let region: Rect?; let microphone: String?; let title: String }
struct Source: Codable { let id: String; let name: String; let kind: String; let x: Int; let y: Int; let width: Int; let height: Int }
struct Cursor: Codable { let time: Double; let x: Double; let y: Double; let click: Bool }
enum CaptureError: Error { case message(String) }

@available(macOS 15.0, *)
final class Recorder: NSObject, SCRecordingOutputDelegate, SCStreamDelegate {
    private let lock = NSLock()
    private var completed = false
    private var failure: String?
    func recordingOutputDidStartRecording(_ recordingOutput: SCRecordingOutput) {}
    func recordingOutputDidFinishRecording(_ recordingOutput: SCRecordingOutput) { lock.lock(); completed = true; lock.unlock() }
    func recordingOutput(_ recordingOutput: SCRecordingOutput, didFailWithError error: Error) { lock.lock(); failure = error.localizedDescription; completed = true; lock.unlock() }
    func stream(_ stream: SCStream, didStopWithError error: Error) { lock.lock(); failure = error.localizedDescription; completed = true; lock.unlock() }
    func state() -> (Bool, String?) { lock.lock(); defer { lock.unlock() }; return (completed, failure) }
}

@main
struct StudioCapture {
    static func json<T: Encodable>(_ value: T) throws { let data = try JSONEncoder().encode(value); FileHandle.standardOutput.write(data); FileHandle.standardOutput.write(Data([10])) }
    static func die(_ message: String) -> Never { FileHandle.standardError.write(Data((message + "\n").utf8)); exit(1) }

    @MainActor static func main() async {
        guard #available(macOS 15.0, *) else { die("ScreenCaptureKit recording requires macOS 15 or later.") }
        do {
            let args = CommandLine.arguments
            guard args.count >= 2 else { throw CaptureError.message("Expected sources, microphones, or record.") }
            if args[1] == "microphones" {
                let devices = AVCaptureDevice.DiscoverySession(deviceTypes: [.microphone, .external], mediaType: .audio, position: .unspecified).devices
                try json(devices.map { $0.uniqueID }); return
            }
            // Listing can request screen-recording authorization but does not start recording.
            let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
            if args[1] == "sources" {
                var sources = content.displays.enumerated().map { i, d in Source(id: "screen:\(d.displayID)", name: "Display \(i+1) · \(d.width)×\(d.height)", kind: "screen", x: Int(d.frame.minX), y: Int(d.frame.minY), width: d.width, height: d.height) }
                sources += content.windows.filter { $0.frame.width >= 16 && $0.frame.height >= 16 && $0.owningApplication?.processID != getppid() && !($0.title ?? "").isEmpty }.map { w in Source(id: "window:\(w.windowID)", name: "\(w.owningApplication?.applicationName ?? "App") · \(w.title ?? "Window")", kind: "window", x: Int(w.frame.minX), y: Int(w.frame.minY), width: Int(w.frame.width), height: Int(w.frame.height)) }
                try json(sources); return
            }
            guard args[1] == "record", args.count == 5 else { throw CaptureError.message("Invalid capture invocation.") }
            let request = try JSONDecoder().decode(Request.self, from: Data(contentsOf: URL(fileURLWithPath: args[2])))
            let config = SCStreamConfiguration()
            config.minimumFrameInterval = CMTime(value: 1, timescale: 30)
            config.showsCursor = true
            config.capturesAudio = false
            config.captureMicrophone = request.microphone != nil
            if let mic = request.microphone {
                guard await AVCaptureDevice.requestAccess(for: .audio) else { throw CaptureError.message("Microphone permission was denied. Enable it in System Settings, or select no microphone.") }
                config.microphoneCaptureDeviceID = mic
            }
            let filter: SCContentFilter
            var frame: CGRect
            if request.mode == "window" {
                guard let window = content.windows.first(where: { "window:\($0.windowID)" == request.sourceId }) else { throw CaptureError.message("Selected window disappeared.") }
                filter = SCContentFilter(desktopIndependentWindow: window)
                frame = window.frame
                config.width = Int(frame.width) / 2 * 2
                config.height = Int(frame.height) / 2 * 2
            } else {
                guard let display = content.displays.first(where: { "screen:\($0.displayID)" == request.sourceId }) else { throw CaptureError.message("Selected display disappeared.") }
                // Explicitly exclude the parent studio's windows, including the recording HUD.
                let excluded = content.applications.filter { $0.processID == getppid() }
                filter = SCContentFilter(display: display, excludingApplications: excluded, exceptingWindows: [])
                frame = display.frame
                config.width = display.width / 2 * 2
                config.height = display.height / 2 * 2
                if request.mode == "region", let r = request.region {
                    let sx = display.frame.width / Double(display.width)
                    let sy = display.frame.height / Double(display.height)
                    config.sourceRect = CGRect(x: Double(r.x)*sx, y: Double(r.y)*sy, width: Double(r.width)*sx, height: Double(r.height)*sy)
                    frame = CGRect(x: frame.minX + Double(r.x)*sx, y: frame.minY + Double(r.y)*sy, width: Double(r.width)*sx, height: Double(r.height)*sy)
                    config.width = r.width / 2 * 2; config.height = r.height / 2 * 2
                }
            }
            let recorder = Recorder()
            let stream = SCStream(filter: filter, configuration: config, delegate: recorder)
            let outputConfig = SCRecordingOutputConfiguration()
            outputConfig.outputURL = URL(fileURLWithPath: args[3])
            outputConfig.videoCodecType = .h264
            outputConfig.outputFileType = .mp4
            let output = SCRecordingOutput(configuration: outputConfig, delegate: recorder)
            try stream.addRecordingOutput(output)
            try await stream.startCapture()
            try Data("ready".utf8).write(to: URL(fileURLWithPath: args[3]).deletingLastPathComponent().appendingPathComponent("capture.ready"), options: .atomic)
            let started = Date()
            var samples: [Cursor] = []
            let stop = Task.detached { () -> Bool in _ = readLine(); return true }
            let stopFlag = StopFlag()
            Task { _ = await stop.value; stopFlag.set() }
            while !stopFlag.get() && !recorder.state().0 {
                if let point = CGEvent(source: nil)?.location {
                    let x = (point.x-frame.minX)/frame.width, y = (point.y-frame.minY)/frame.height
                    if x >= 0 && x <= 1 && y >= 0 && y <= 1 && samples.count < 864000 { samples.append(Cursor(time: Date().timeIntervalSince(started), x: x, y: y, click: NSEvent.pressedMouseButtons & 1 != 0)) }
                }
                try await Task.sleep(nanoseconds: 50_000_000)
            }
            try await stream.stopCapture()
            let deadline = Date().addingTimeInterval(10)
            while !recorder.state().0 && Date() < deadline { try await Task.sleep(nanoseconds: 50_000_000) }
            try JSONEncoder().encode(samples).write(to: URL(fileURLWithPath: args[4]), options: .atomic)
            if let error = recorder.state().1 { throw CaptureError.message(error) }
            if !recorder.state().0 { throw CaptureError.message("Recording finalization timed out; partial file preserved.") }
        } catch { die("Capture failed: \(error). Check Screen & System Audio Recording permission in System Settings.") }
    }
}

final class StopFlag: @unchecked Sendable {
    private let lock = NSLock(); private var stopped = false
    func set() { lock.lock(); stopped = true; lock.unlock() }
    func get() -> Bool { lock.lock(); defer { lock.unlock() }; return stopped }
}
