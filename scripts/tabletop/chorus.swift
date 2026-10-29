// Finds a song's chorus: the loud stretch it repeats most. Used by make_choruses.py.
//
//   chorus <audio file> [seconds]   ->  JSON: the best non-overlapping candidates, best first
//
// Every 0.25 s: a 12-bin chroma (pitch classes, 55 Hz - 2 kHz) and the loudness in dB.
// A window's repetition is how closely the music matches itself somewhere else in
// the song (the mean cosine along a diagonal of the chroma self-similarity matrix),
// taking its two best matches; a chorus usually comes back more than once. Its
// score is that repetition plus loudness, both as z-scores across the song. The
// first and last 10 s (intro, fade-out) are never candidates. A start is then
// snapped to the biggest jump in loudness within a second of it, where a phrase
// usually begins.
import AVFoundation
import Accelerate

let args = CommandLine.arguments
guard args.count >= 2 else { fputs("usage: chorus <audio> [seconds]\n", stderr); exit(2) }
let seconds = args.count > 2 ? Double(args[2])! : 10

let file = try AVAudioFile(forReading: URL(fileURLWithPath: args[1]))
let format = file.processingFormat
let rate = format.sampleRate
let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(file.length))!
try file.read(into: buffer)
let channels = Int(format.channelCount), count = Int(buffer.frameLength)
var samples = [Float](repeating: 0, count: count)
for c in 0..<channels {
    let p = buffer.floatChannelData![c]
    for i in 0..<count { samples[i] += p[i] / Float(channels) }
}

let hopSeconds = 0.25
let hop = Int(rate * hopSeconds)
let log2n = 13, size = 1 << log2n, half = size / 2
let fft = vDSP.FFT(log2n: vDSP_Length(log2n), radix: .radix2, ofType: DSPSplitComplex.self)!
let hann = vDSP.window(ofType: Float.self, usingSequence: .hanningDenormalized, count: size, isHalfWindow: false)
var pitchClass = [Int](repeating: -1, count: half)
for k in 1..<half {
    let f = Double(k) * rate / Double(size)
    if f >= 55 && f <= 2000 { pitchClass[k] = ((Int((69 + 12 * log2(f / 440)).rounded()) % 12) + 12) % 12 }
}

let frames = max(0, (count - size) / hop + 1)
var chroma = [[Float]](), loud = [Float]()
var re = [Float](repeating: 0, count: half), im = [Float](repeating: 0, count: half)
var mags = [Float](repeating: 0, count: half)
for f in 0..<frames {
    var seg = Array(samples[f * hop ..< f * hop + size])
    var meanSquare: Float = 0
    vDSP_measqv(seg, 1, &meanSquare, vDSP_Length(size))
    loud.append(10 * log10(meanSquare + 1e-10))
    vDSP.multiply(seg, hann, result: &seg)
    re.withUnsafeMutableBufferPointer { rp in
        im.withUnsafeMutableBufferPointer { ip in
            var split = DSPSplitComplex(realp: rp.baseAddress!, imagp: ip.baseAddress!)
            seg.withUnsafeBufferPointer { sp in
                sp.baseAddress!.withMemoryRebound(to: DSPComplex.self, capacity: half) {
                    vDSP_ctoz($0, 2, &split, 1, vDSP_Length(half))
                }
            }
            fft.forward(input: split, output: &split)
            vDSP_zvabs(&split, 1, &mags, 1, vDSP_Length(half))
        }
    }
    var c = [Float](repeating: 0, count: 12)
    for k in 1..<half where pitchClass[k] >= 0 { c[pitchClass[k]] += log(1 + mags[k]) }
    let mean = c.reduce(0, +) / 12
    c = c.map { $0 - mean }                       // the shape, not the overall level
    let norm = sqrt(c.reduce(0) { $0 + $1 * $1 })
    chroma.append(norm > 0 ? c.map { $0 / norm } : c)
}

let window = Int(seconds / hopSeconds)
let edge = Int(10 / hopSeconds)
guard frames > window + 2 * edge else { fputs("too short\n", stderr); exit(1) }

// Best two matches per start (partners at least a window apart).
var best = [[(score: Float, partner: Int)]](repeating: [], count: frames)
func offer(_ t: Int, _ score: Float, _ partner: Int) {
    var list = best[t]
    list.append((score, partner))
    list.sort { $0.score > $1.score }
    var kept = [(score: Float, partner: Int)]()
    for item in list where kept.allSatisfy({ abs($0.partner - item.partner) >= window }) {
        kept.append(item)
        if kept.count == 2 { break }
    }
    best[t] = kept
}
for lag in window..<frames - window {
    var prefix = [Float](repeating: 0, count: frames - lag + 1)
    for t in 0..<frames - lag {
        var dot: Float = 0
        vDSP_dotpr(chroma[t], 1, chroma[t + lag], 1, &dot, 12)
        prefix[t + 1] = prefix[t] + dot
    }
    for t in 0...(frames - lag - window) {
        let mean = (prefix[t + window] - prefix[t]) / Float(window)
        if best[t].count < 2 || mean > best[t].last!.score { offer(t, mean, t + lag) }
        let u = t + lag
        if best[u].count < 2 || mean > best[u].last!.score { offer(u, mean, t) }
    }
}

let starts = Array(edge...(frames - window - edge))
var loudPrefix = [Float](repeating: 0, count: frames + 1)
for i in 0..<frames { loudPrefix[i + 1] = loudPrefix[i] + loud[i] }
let rep = starts.map { t in best[t].reduce(0) { $0 + $1.score } / 2 }
let lvl = starts.map { t in (loudPrefix[t + window] - loudPrefix[t]) / Float(window) }
func z(_ v: [Float]) -> [Float] {
    let m = v.reduce(0, +) / Float(v.count)
    let sd = sqrt(v.reduce(0) { $0 + ($1 - m) * ($1 - m) } / Float(v.count))
    return v.map { sd > 0 ? ($0 - m) / sd : 0 }
}
let zr = z(rep), zl = z(lvl)
var ranked = starts.indices.map { (i: $0, score: zr[$0] + zl[$0]) }
ranked.sort { $0.score > $1.score }

var picks = [[String: Double]]()
for r in ranked {
    let t = starts[r.i]
    if picks.contains(where: { abs($0["frame"]! - Double(t)) < Double(window) }) { continue }
    var snap = t, jump: Float = -.infinity
    for s in max(1, t - 4)...min(frames - window - 1, t + 4) where loud[s] - loud[s - 1] > jump {
        jump = loud[s] - loud[s - 1]; snap = s
    }
    picks.append(["frame": Double(t), "start": Double(snap) * hopSeconds,
                  "repeat": Double(zr[r.i]), "loud": Double(zl[r.i]), "score": Double(r.score)])
    if picks.count == 5 { break }
}
let out = ["duration": Double(count) / rate, "candidates": picks.map { $0.filter { $0.key != "frame" } }] as [String: Any]
print(String(data: try JSONSerialization.data(withJSONObject: out, options: [.sortedKeys]), encoding: .utf8)!)
