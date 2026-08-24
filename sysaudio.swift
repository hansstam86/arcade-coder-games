// sysaudio — stream the Mac's system audio to stdout as raw Float32 mono PCM.
//
// Uses ScreenCaptureKit (no loopback driver needed). Requires the Screen
// Recording permission for the responsible app (the ArcadeMinesweeper bundle).
//
//   swiftc -O sysaudio.swift -o sysaudio_helper
//   ./sysaudio_helper            # 48kHz Float32 mono on stdout, logs on stderr

import AVFoundation
import CoreMedia
import Foundation
import ScreenCaptureKit

func elog(_ s: String) {
    FileHandle.standardError.write((s + "\n").data(using: .utf8)!)
}

extension CMSampleBuffer {
    var asPCMBuffer: AVAudioPCMBuffer? {
        try? self.withAudioBufferList { abl, _ -> AVAudioPCMBuffer? in
            guard let desc = self.formatDescription?.audioStreamBasicDescription else { return nil }
            guard let format = AVAudioFormat(standardFormatWithSampleRate: desc.mSampleRate,
                                             channels: desc.mChannelsPerFrame) else { return nil }
            return AVAudioPCMBuffer(pcmFormat: format, bufferListNoCopy: abl.unsafePointer)
        }
    }
}

final class Output: NSObject, SCStreamOutput, SCStreamDelegate {
    let out = FileHandle.standardOutput

    func stream(_ stream: SCStream, didOutputSampleBuffer sb: CMSampleBuffer,
                of type: SCStreamOutputType) {
        guard type == .audio, sb.isValid, let pcm = sb.asPCMBuffer,
              let ch = pcm.floatChannelData else { return }
        let n = Int(pcm.frameLength)
        if n == 0 { return }
        if pcm.format.channelCount >= 2 {
            var mono = [Float](repeating: 0, count: n)
            let l = ch[0], r = ch[1]
            for i in 0..<n { mono[i] = (l[i] + r[i]) * 0.5 }
            mono.withUnsafeBytes { out.write(Data($0)) }
        } else {
            out.write(Data(bytes: ch[0], count: n * 4))
        }
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        elog("stream stopped: \(error.localizedDescription)")
        exit(3)
    }
}

let output = Output()
var streamRef: SCStream?

Task {
    do {
        let content = try await SCShareableContent.excludingDesktopWindows(
            false, onScreenWindowsOnly: false)
        guard let display = content.displays.first else {
            elog("no display found"); exit(2)
        }
        let filter = SCContentFilter(display: display, excludingWindows: [])
        let cfg = SCStreamConfiguration()
        cfg.capturesAudio = true
        cfg.excludesCurrentProcessAudio = true
        cfg.sampleRate = 48000
        cfg.channelCount = 2
        cfg.width = 2
        cfg.height = 2
        cfg.minimumFrameInterval = CMTime(value: 1, timescale: 2)
        let stream = SCStream(filter: filter, configuration: cfg, delegate: output)
        try stream.addStreamOutput(output, type: .audio,
                                   sampleHandlerQueue: DispatchQueue(label: "audio"))
        try await stream.startCapture()
        streamRef = stream
        elog("capturing system audio @48000 Hz")
    } catch {
        elog("failed to start: \(error.localizedDescription)")
        elog("hint: grant Screen Recording to the app in System Settings > Privacy & Security")
        exit(2)
    }
}

dispatchMain()
