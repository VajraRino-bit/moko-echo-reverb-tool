import json
from pathlib import Path
import numpy as np
import soundfile as sf
from pedalboard import Pedalboard, Delay, Reverb, Limiter

ROOT = Path(__file__).resolve().parent
def peak(x):
    p = float(np.max(np.abs(x)))
    return 20*np.log10(p) if p else None

def main():
    sr = 48000
    x = np.zeros((1, sr*5), dtype=np.float32)
    x[0, :sr*3] = .8*np.sin(2*np.pi*440*np.arange(sr*3)/sr)
    out = ROOT/'tests'
    out.mkdir(exist_ok=True)
    sf.write(out/'probe_input.wav', x.T, sr, subtype='PCM_24')
    y = Pedalboard([Delay(delay_seconds=.25, feedback=.3, mix=.25),
                    Reverb(room_size=.6, wet_level=.3, dry_level=1),
                    Limiter(threshold_db=-1, release_ms=100)])(x, sr)
    before_save = peak(y)
    ceiling = 10**(-1/20)-2**-22
    p = np.max(np.abs(y))
    reduction = float(max(0., 20*np.log10(p/ceiling))) if p else 0.
    if p > ceiling:
        y *= ceiling/p
    sf.write(out/'probe_output.wav', y.T, sr, subtype='PCM_24')
    z, actual_sr = sf.read(out/'probe_output.wav', always_2d=True)
    result = dict(input_peak_db=peak(x), processed_peak_db=before_save,
                  saved_peak_db=peak(z), input_seconds=x.shape[1]/sr,
                  saved_seconds=len(z)/actual_sr, sample_rate=actual_sr,
                  channels=z.shape[1], normalization_reduction_db=reduction)
    assert result['saved_peak_db'] <= -1
    assert len(z) == sr*5 and z.shape[1] == 1 and actual_sr == sr
    (out/'probe.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
if __name__ == '__main__':
    main()
