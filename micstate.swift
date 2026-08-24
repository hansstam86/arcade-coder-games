// micstate — prints "1" if ANY audio input device is running in some process
// (mic in use / you're on a call), else "0". Scans every device that has input
// streams, so it works even when a virtual device (Teams/Krisp/etc.) is the
// default. Reading device state does not capture audio -> no mic permission.

import CoreAudio

func propertyData<T>(_ obj: AudioObjectID, _ sel: AudioObjectPropertySelector,
                     _ scope: AudioObjectPropertyScope, _ def: T) -> T {
    var addr = AudioObjectPropertyAddress(
        mSelector: sel, mScope: scope, mElement: kAudioObjectPropertyElementMain)
    var value = def
    var size = UInt32(MemoryLayout<T>.size)
    let st = AudioObjectGetPropertyData(obj, &addr, 0, nil, &size, &value)
    return st == noErr ? value : def
}

func allDevices() -> [AudioDeviceID] {
    var addr = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyDevices,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain)
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(
            AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size) == noErr
    else { return [] }
    let count = Int(size) / MemoryLayout<AudioDeviceID>.size
    var ids = [AudioDeviceID](repeating: 0, count: count)
    guard AudioObjectGetPropertyData(
            AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &ids) == noErr
    else { return [] }
    return ids
}

func hasInputStreams(_ dev: AudioDeviceID) -> Bool {
    var addr = AudioObjectPropertyAddress(
        mSelector: kAudioDevicePropertyStreams,
        mScope: kAudioObjectPropertyScopeInput,
        mElement: kAudioObjectPropertyElementMain)
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(dev, &addr, 0, nil, &size) == noErr
    else { return false }
    return size > 0
}

func isRunning(_ dev: AudioDeviceID) -> Bool {
    return propertyData(dev, kAudioDevicePropertyDeviceIsRunningSomewhere,
                        kAudioObjectPropertyScopeGlobal, UInt32(0)) != 0
}

let live = allDevices().contains { hasInputStreams($0) && isRunning($0) }
print(live ? "1" : "0")
