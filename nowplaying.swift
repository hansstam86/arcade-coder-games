// nowplaying — prints one line of now-playing info via the private MediaRemote
// framework, then exits. Format:
//   OK|<elapsed_sec>|<duration_sec>|<rate>|<title>|<artist>
//   NONE            (nothing playing / info unavailable)
// rate is the playback rate (1 = playing, 0 = paused). Reading this does not
// control playback and needs no permission.

import Foundation

typealias GetInfoFn = @convention(c) (DispatchQueue, @escaping ([String: Any]?) -> Void) -> Void

guard let b = CFBundleCreate(kCFAllocatorDefault,
        NSURL(fileURLWithPath: "/System/Library/PrivateFrameworks/MediaRemote.framework")),
      let p = CFBundleGetFunctionPointerForName(b, "MRMediaRemoteGetNowPlayingInfo" as CFString)
else { print("NONE"); exit(0) }

let getInfo = unsafeBitCast(p, to: GetInfoFn.self)

func clean(_ s: String) -> String {
    return s.replacingOccurrences(of: "|", with: " ")
            .replacingOccurrences(of: "\n", with: " ")
}

getInfo(DispatchQueue.main) { info in
    guard let info = info else { print("NONE"); exit(0) }
    let title = clean(info["kMRMediaRemoteNowPlayingInfoTitle"] as? String ?? "")
    let artist = clean(info["kMRMediaRemoteNowPlayingInfoArtist"] as? String ?? "")
    let el = info["kMRMediaRemoteNowPlayingInfoElapsedTime"] as? Double ?? -1
    let dur = info["kMRMediaRemoteNowPlayingInfoDuration"] as? Double ?? -1
    let rate = info["kMRMediaRemoteNowPlayingInfoPlaybackRate"] as? Double ?? 0
    if dur <= 0 && title.isEmpty { print("NONE"); exit(0) }
    print("OK|\(el)|\(dur)|\(rate)|\(title)|\(artist)")
    exit(0)
}
Timer.scheduledTimer(withTimeInterval: 2.5, repeats: false) { _ in print("NONE"); exit(0) }
RunLoop.main.run()
