#!/usr/bin/env python3
"""In-band DTMF frames over a simulated line: generate -> codec (ffmpeg) -> noise -> Goertzel decoder -> frame check.

Note: written for the v0.2 frame layout (OFFER without version-specific domain continuation).
Frame lengths are comparable to v0.3. Requires numpy and ffmpeg with libgsm and libopus.
Usage: python3 simulate_inband.py [trials]
"""
import numpy as np, subprocess, random, sys, os, tempfile

SR = 8000
LOW = [697, 770, 852, 941]; HIGH = [1209, 1336, 1477, 1633]
KEYS = {'1':(0,0),'2':(0,1),'3':(0,2),'4':(1,0),'5':(1,1),'6':(1,2),'7':(2,0),'8':(2,1),'9':(2,2),'*':(3,0),'0':(3,1),'#':(3,2)}
REV = {v:k for k,v in KEYS.items()}

def cc(s): return '%02d' % (98 - (int(s) * 100 % 97))
def frame(body): return '*' + body + cc(body) + '#'

DOMCODE = {**{chr(97+i): '%02d' % (i+1) for i in range(26)}, **{str(i): str(30+i) for i in range(10)}, '-': '40', '.': '41'}
def offer(dom=None):
    S = '%04d' % random.randrange(10000); B = '%06d' % random.randrange(10**6)
    d = '' if dom is None else ''.join(DOMCODE[c] for c in dom)
    L = '00' if dom is None else '%02d' % len(dom)
    return frame('11' + '01' + S + B + L + d)
def hello(): return frame('1001' + '%06d' % random.randrange(10**6))

def synth(seq, on, off, level=0.25):
    out = [np.zeros(int(SR*0.3))]
    for ch in seq:
        r, c = KEYS[ch]; t = np.arange(int(SR*on)) / SR
        tone = level * (np.sin(2*np.pi*LOW[r]*t) + np.sin(2*np.pi*HIGH[c]*t)) / 2
        out += [tone, np.zeros(int(SR*off))]
    out.append(np.zeros(int(SR*0.3)))
    return np.concatenate(out)

CODECS = {
    'g711':   (['-c:a', 'pcm_mulaw', '-f', 'wav'], 'wav'),
    'gsm':    (['-c:a', 'libgsm', '-f', 'gsm'], 'gsm'),
    'g726_16k': (['-c:a', 'adpcm_g726', '-b:a', '16k', '-f', 'wav'], 'wav'),
    'opus_12k': (['-c:a', 'libopus', '-b:a', '12k', '-f', 'ogg'], 'ogg'),
    'opus_6k':  (['-c:a', 'libopus', '-b:a', '6k', '-f', 'ogg'], 'ogg'),
}

def through_codec(x, codec, tmp):
    enc, ext = CODECS[codec]
    raw = os.path.join(tmp, 'in.raw'); mid = os.path.join(tmp, 'mid.' + ext); outp = os.path.join(tmp, 'out.raw')
    (np.clip(x, -1, 1) * 32767).astype('<i2').tofile(raw)
    q = ['-hide_banner', '-loglevel', 'error', '-y']
    subprocess.run(['ffmpeg', *q, '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', raw, '-ar', str(SR) if 'opus' not in codec else '48000', *enc, mid], check=True)
    subprocess.run(['ffmpeg', *q, '-i', mid, '-fflags', '+genpts', '-f', 's16le', '-ar', str(SR), '-ac', '1', outp], check=True)
    return np.fromfile(outp, '<i2').astype(float) / 32767

FREQS = LOW + HIGH[:3]
def detect(x, win=0.02, hop=0.01):
    n, h = int(SR*win), int(SR*hop)
    t = np.arange(n) / SR
    E = np.array([np.exp(-2j*np.pi*f*t) for f in FREQS]) * np.hanning(n)
    starts = range(0, len(x)-n, h)
    B = np.stack([x[i:i+n] for i in starts])
    P = np.abs(B @ E.T)**2                      # block x frequency
    tot = np.sum(B**2, axis=1) * n / 2 * 0.375 + 1e-12   # Hann-corrected total energy scale
    li = np.argmax(P[:, :4], axis=1); hj = np.argmax(P[:, 4:], axis=1)
    pl = P[np.arange(len(P)), li]; ph = P[np.arange(len(P)), 4+hj]
    # second strongest tone in each group must be at least 6 dB weaker
    P2l = np.sort(P[:, :4], axis=1)[:, -2]; P2h = np.sort(P[:, 4:], axis=1)[:, -2]
    level = pl + ph
    ref = np.percentile(level, 95)
    ok = (level > 0.05*ref) & (pl > 4*P2l) & (ph > 4*P2h) & (pl/ph > 0.16) & (pl/ph < 6.3) & ((pl+ph) > 0.5*tot)
    syms = [REV.get((int(a), int(b))) if k else None for a, b, k in zip(li, hj, ok)]
    out, cur, run, gap = [], None, 0, 99
    for s in syms + [None, None, None]:
        if s is None:
            gap += 1
            if gap >= 2 and cur is not None:
                if run >= 3: out.append(cur)
                cur, run = None, 0
        else:
            if cur is None or (s != cur):
                if cur is not None and run >= 3: out.append(cur)
                cur, run = s, 1
            else: run += 1
            gap = 0
    return ''.join(out)

def valid(f):
    if len(f) < 4 or f[0] != '*' or f[-1] != '#': return False
    d = f[1:-1]
    return d.isdigit() and int(d) % 97 == 1

def run(trials, codec, rate, snr_db, kind):
    on, off = {5: (0.1, 0.1), 7: (0.07, 0.07)}[rate]
    good = 0
    with tempfile.TemporaryDirectory() as tmp:
        for _ in range(trials):
            f = hello() if kind == 'hello' else offer(None if kind == 'offer0' else 'fogaszat-muster.ch')
            x = synth(f, on, off)
            sig_p = np.mean(x[x != 0]**2)
            x = x + np.random.normal(0, np.sqrt(sig_p / 10**(snr_db/10)), len(x))
            y = through_codec(x, codec, tmp)
            got = detect(y)
            good += (got == f)
    return good

if __name__ == '__main__':
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    random.seed(1); np.random.seed(1)
    print('codec      rate  SNR  HELLO  OFFER0  OFFER18   (error-free / %d)' % trials)
    for codec in CODECS:
        for rate in (5, 7):
            for snr in (30, 15):
                r = [run(trials, codec, rate, snr, k) for k in ('hello', 'offer0', 'offer18')]
                print(f'{codec:10} {rate}/s  {snr:2}dB  ' + '  '.join(f'{v:5}' for v in r), flush=True)
