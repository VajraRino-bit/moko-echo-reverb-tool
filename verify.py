import json
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
from audio_core import ROOT, PRESETS, export_audio, process_audio, peak_db

def main():
    folder = ROOT/'tests'
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT/'tests'/'input.wav'
    with sf.SoundFile(source) as f:
        sr = f.samplerate
        x = f.read(sr*30, dtype='float32', always_2d=True)
    clip = folder/'voice_30seconds.wav'
    sf.write(clip, x, sr, subtype='PCM_24')
    results = []
    for index, (name, values) in enumerate(PRESETS.items()):
        dest, info = export_audio(clip, values, folder/f'preset_{index}')
        assert info['saved_peak_db'] is None or info['saved_peak_db'] <= -1
        assert info['sample_rate'] == sr and info['channels'] == x.shape[1]
        info['preset'] = name
        results.append(info)
    # Stress both channels, over-range floating-point input, and extreme controls.
    for rate in (44100, 48000):
        t = np.arange(rate*2)/rate
        stress = np.stack([2.5*np.sin(2*np.pi*997*t), 2*np.sin(2*np.pi*2301*t)]).astype('float32')
        path = folder/f'overrange_{rate}.wav'
        sf.write(path, stress.T, rate, subtype='FLOAT')
        _, report = export_audio(path, (.8,30,.85,1,.8,1,0,150),folder/f'stress_{rate}')
        assert report['saved_peak_db'] <= -1
        assert report['channels'] == 2 and report['sample_rate'] == rate
        results.append(report)
    silent, _ = process_audio(np.zeros((1,48000),dtype='float32'),48000,PRESETS['教会'])
    assert np.isfinite(silent).all() and peak_db(silent) is None
    impulse = np.zeros((1,48000),dtype='float32'); impulse[0,1000]=.2
    dry, _ = process_audio(impulse,48000,PRESETS['素のまま'])
    assert dry.shape == impulse.shape and np.argmax(dry[0]) == 1000
    assert np.max(np.abs(dry-impulse)) < 1e-5
    try:
        process_audio(impulse,48000,(float('nan'),250,0,.5,0,.5,.5,0))
        raise AssertionError('invalid settings accepted')
    except ValueError:
        pass
    from app import build_ui
    demo = build_ui()
    assert demo is not None
    (folder/'verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    for r in results:
        print(r.get('preset','STRESS'),r['sample_rate'],r['channels'],r['output_seconds'],r['saved_peak_db'])
    print('ALL_CHECKS_PASSED')

if __name__ == '__main__':
    main()
