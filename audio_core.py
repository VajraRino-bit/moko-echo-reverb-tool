"""Local audio processing. All arrays are channel-first float32."""
import json
import math
import uuid
import shutil
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
from pedalboard import Delay, Reverb, LowpassFilter, BrickwallLimiter
from pedalboard.io import AudioFile

ROOT = Path(__file__).resolve().parent
VERSION = 'moko-echo-reverb-tool_v1.0'
KEYS = ('echo', 'interval', 'feedback', 'brightness', 'reverb', 'room', 'damping', 'predelay')
PRESETS = {
    '素のまま': (0, 250, 0, .7, 0, .3, .5, 0),
    '薄くホール': (.06, 180, .15, .65, .12, .55, .55, 15),
    'カラオケ風': (.18, 240, .30, .65, .20, .55, .50, 20),
    'ライブハウス': (.10, 120, .20, .60, .22, .40, .65, 10),
    '教会': (.10, 380, .35, .50, .40, .90, .45, 45),
    '深いエコー': (.40, 480, .60, .55, .15, .60, .60, 25),
    'コンサートホール': (.12, 280, .25, .70, .32, .80, .40, 30),
}

def peak_db(x):
    p = float(np.max(np.abs(x))) if x.size else 0
    return float(20*math.log10(p)) if p else None

def db_text(p):
    return '−∞' if p is None else f'{p:.6f}'

def load_audio(path):
    if not path:
        raise ValueError('音源ファイルを選んでください。')
    try:
        stream = AudioFile(str(path))
    except (ValueError, RuntimeError):
        # Windows Pedalboard builds do not decode AAC/M4A; use local FFmpeg.
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            raise ValueError('この形式は読み込めません。WAV/MP3/FLACに変換するか、FFmpegを導入してください。')
        (ROOT/'tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            converted = Path(tmp)/'decoded.wav'
            result = subprocess.run([ffmpeg,'-v','error','-nostdin','-i',str(path),
                '-map','0:a:0','-t','1800.01','-c:a','pcm_f32le',str(converted)],
                capture_output=True, timeout=180, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if result.returncode:
                raise ValueError('音源を読み込めません。ファイルの形式・破損を確認してください。')
            return load_audio(converted)
    with stream as f:
        if f.num_channels not in (1, 2):
            raise ValueError('モノラルまたはステレオ音源を選んでください。')
        if f.frames <= 0 or f.duration > 1800:
            raise ValueError('音源は0秒より長く、30分以内にしてください。')
        sr = int(f.samplerate)
        x = f.read(f.frames)
    if not np.isfinite(x).all():
        raise ValueError('音源に無効な数値が含まれています。')
    return np.ascontiguousarray(x, dtype=np.float32), sr

def parameters(values):
    if len(values) != 8 or not all(math.isfinite(float(v)) for v in values):
        raise ValueError('エフェクトの設定値が不正です。')
    limits = ((0,.8),(30,1000),(0,.85),(0,1),(0,.8),(0,1),(0,1),(0,150))
    for v, (lo, hi) in zip(values, limits):
        if not lo <= float(v) <= hi:
            raise ValueError('エフェクトの設定値が範囲外です。')
    return dict(zip(KEYS, map(float, values)))

def process_audio(x, sr, values):
    p = parameters(values)
    # Preserve a long tail; last 50 ms fade gently at the tail boundary.
    tail = 12 if p['echo'] or p['reverb'] else 0
    y = np.pad(x, ((0,0),(0,round(sr*tail))))
    if p['echo']:
        cutoff = min(1200 * (15 ** p['brightness']), sr*.45)
        wet = LowpassFilter(cutoff_frequency_hz=cutoff)(y, sr)
        wet = Delay(delay_seconds=p['interval']/1000, feedback=p['feedback'], mix=1)(wet, sr)
        y = y + p['echo']*wet
    if p['reverb']:
        wet = Reverb(room_size=p['room'], damping=p['damping'], wet_level=1,
                     dry_level=0, width=1, freeze_mode=0)(y, sr)
        shift = round(sr*p['predelay']/1000)
        if shift:
            wet = np.pad(wet, ((0,0),(shift,0)))[:, :y.shape[1]]
        y = y + p['reverb']*wet
    if not np.isfinite(y).all():
        raise ValueError('処理中に無効な数値を検出したため、書き出しを停止しました。')
    effect_peak = peak_db(y)
    # Pedalboard compensates plugin latency for this offline processing call.
    limiter = BrickwallLimiter(ceiling_db=-1.2, release_ms=100,
                              lookahead_ms=5, true_peak=True)
    y = limiter(y, sr)
    if tail:
        fade = round(sr*.05)
        y[:, -fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    before = peak_db(y)
    ceiling = 10**(-1/20) - 2**-22
    actual = float(np.max(np.abs(y)))
    reduction = max(0., 20*math.log10(actual/ceiling)) if actual else 0.
    if actual > ceiling:
        y *= ceiling/actual
    return y, dict(parameters=p, input_peak_db=peak_db(x), effect_peak_db=effect_peak,
                   limiter_output_peak_db=before, normalization_reduction_db=reduction,
                   input_seconds=x.shape[1]/sr, output_seconds=y.shape[1]/sr,
                   tail_seconds=tail, sample_rate=sr, channels=x.shape[0])

def export_audio(path, values, output_dir=None):
    x, sr = load_audio(path)
    y, info = process_audio(x, sr, values)
    folder = Path(output_dir) if output_dir else ROOT/'output'/uuid.uuid4().hex[:12]
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder/(Path(path).stem + '_echo-reverb.wav')
    if dest.exists():
        raise FileExistsError('同名ファイルがあるため、上書きを中止しました。')
    try:
        sf.write(dest, y.T, sr, subtype='PCM_24')
        z, saved_sr = sf.read(dest, always_2d=True, dtype='float64')
        saved_peak = peak_db(z)
        if ((saved_peak is not None and saved_peak > -1) or
            not np.isfinite(z).all() or saved_sr != sr or z.shape != y.T.shape):
            raise ValueError('保存後の安全検査に失敗しました。')
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    info.update(saved_peak_db=saved_peak, output_path=str(dest), subtype='PCM_24', version=VERSION)
    dest.with_suffix('.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(dest), info
