// screencap — stream a tiny downsampled image of the Mac screen to stdout.
//
// Uses ScreenCaptureKit; the system scales the whole display down to OUT×OUT,
// so each pixel is the average colour of a screen region — perfect for
// ambilight. Emits raw RGB bytes, OUT*OUT*3 per frame. Requires the Screen
// Recording permission for the responsible app (the ArcadeMinesweeper bundle).
//
//   swiftc -O screencap.swift -o bin/screencap   (needs -framework ScreenCaptureKit)

import CoreMedia
import CoreVideo
import Foundation
import ScreenCaptureKit

let OUT = 24

func elog(_ s: String) {
    FileHandle.standardError.write((s + "\n").data(using: .utf8)!)
}

final class Output: NSObject, SCStreamOutput, SCStreamDelegate {
    let out = FileHandle.standardOutput

    func stream(_ stream: SCStream, didOutputSampleBuffer sb: CMSampleBuffer,
                of type: SCStreamOutputType) {
        guard type == .screen, sb.isValid,
              let px = CMSampleBufferGetImageBuffer(sb) else { return }
        CVPixelBufferLockBaseAddress(px, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(px, .readOnly) }
        let w = CVPixelBufferGetWidth(px), h = CVPixelBufferGetHeight(px)
        let bpr = CVPixelBufferGetBytesPerRow(px)
        guard let base = CVPixelBufferGetBaseAddress(px) else { return }
        let p = base.assumingMemoryBound(to: UInt8.self)
        var buf = [UInt8](); buf.reserveCapacity(w * h * 3)
        for y in 0..<h {
            let row = y * bpr
            for x in 0..<w {
                let i = row + x * 4                 // BGRA
                buf.append(p[i + 2]); buf.append(p[i + 1]); buf.append(p[i])
            }
        }
        out.write(Data(buf))
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        elog("stream stopped: \(error.localizedDescription)"); exit(3)
    }
}

let output = Output()
var streamRef: SCStream?

Task {
    do {
        let content = try await SCShareableContent.excludingDesktopWindows(
            false, onScreenWindowsOnly: false)
        guard let display = content.displays.first else { elog("no display"); exit(2) }
        let filter = SCContentFilter(display: display, excludingWindows: [])
        let cfg = SCStreamConfiguration()
        cfg.width = OUT
        cfg.height = OUT
        cfg.showsCursor = false
        cfg.pixelFormat = kCVPixelFormatType_32BGRA
        cfg.minimumFrameInterval = CMTime(value: 1, timescale: 12)
        cfg.queueDepth = 3
        let stream = SCStream(filter: filter, configuration: cfg, delegate: output)
        try stream.addStreamOutput(output, type: .screen,
                                   sampleHandlerQueue: DispatchQueue(label: "screen"))
        try await stream.startCapture()
        streamRef = stream
        elog("capturing screen @\(OUT)x\(OUT)")
    } catch {
        elog("failed to start: \(error.localizedDescription)")
        elog("hint: grant Screen Recording to the app in System Settings > Privacy & Security")
        exit(2)
    }
}

dispatchMain()
