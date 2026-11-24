import os
from pathlib import Path
ROOT = Path(__file__).resolve().parent
os.environ['GRADIO_ANALYTICS_ENABLED'] = 'False'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['GRADIO_TEMP_DIR'] = str(ROOT/'tmp'/'gradio')
import gradio as gr
from audio_core import PRESETS, export_audio, load_audio, peak_db, db_text, VERSION

def inspect(path):
    if not path:
        return '', None, None, None, ''
    try:
        x, sr = load_audio(path)
        return (f'元のピーク：{db_text(peak_db(x))} dBFS ｜ 長さ：{x.shape[1]/sr:.3f}秒 ｜ '
                f'{sr:,} Hz / {x.shape[0]} ch', path, None, None, '')
    except Exception as e:
        raise gr.Error(str(e))

def run(path, *values):
    try:
        dest, info = export_audio(path, values)
        msg = (f'書き出し完了：ピーク {db_text(info["saved_peak_db"])} dBFS\n'
               f'最終ピーク調整による音量低下：{info["normalization_reduction_db"]:.4f} dB '
               '（リミッターによる瞬間的な抑制は別）\n'
               f'{info["sample_rate"]:,} Hz / {info["channels"]} ch / 24bit PCM WAV\n'
               f'長さ {info["output_seconds"]:.3f}秒（余韻 {info["tail_seconds"]}秒を含む）\n'
               f'保存先：{dest}')
        return dest, dest, msg
    except Exception as e:
        raise gr.Error(str(e))

def build_ui():
    with gr.Blocks(title='モコのエコー＆リバーブ', analytics_enabled=False) as demo:
        gr.Markdown('# モコのエコー＆リバーブ\n音源を選び、響きを調整してWAVに保存できます。処理はこのPC内で行います。')
        file = gr.File(label='音源ファイル（WAV / MP3 / FLAC / M4A など）', type='filepath')
        meta = gr.Textbox(label='元の音源', interactive=False)
        preset = gr.Dropdown(list(PRESETS), value='薄くホール', label='プリセット')
        v = PRESETS['薄くホール']
        with gr.Row():
            with gr.Column():
                gr.Markdown('### エコー')
                a = gr.Slider(0,.8,value=v[0],step=.01,label='量')
                b = gr.Slider(30,1000,value=v[1],step=1,label='間隔（ms）')
                c = gr.Slider(0,.85,value=v[2],step=.01,label='繰り返し')
                d = gr.Slider(0,1,value=v[3],step=.01,label='明るさ')
            with gr.Column():
                gr.Markdown('### リバーブ')
                e = gr.Slider(0,.8,value=v[4],step=.01,label='量')
                f = gr.Slider(0,1,value=v[5],step=.01,label='部屋の広さ')
                g = gr.Slider(0,1,value=v[6],step=.01,label='やわらかさ')
                h = gr.Slider(0,150,value=v[7],step=1,label='響きの始まり（ms）')
        controls = [a,b,c,d,e,f,g,h]
        button = gr.Button('効果をかけてWAVに保存', variant='primary')
        with gr.Row():
            original = gr.Audio(label='原音', type='filepath', interactive=False)
            processed = gr.Audio(label='効果あり', type='filepath', interactive=False)
        download = gr.File(label='完成したWAV', interactive=False)
        result = gr.Textbox(label='書き出し結果', lines=6, interactive=False)
        gr.Markdown('原音は変更しません。安全のためリミッターは常時有効です。響きを使う場合は末尾に12秒の余韻を追加します。\n'
                    '設定を変えた後は、もう一度保存ボタンを押してください。プレビューの自動音量調整は行いません。')
        preset.change(lambda name: PRESETS[name], preset, controls)
        file.change(inspect, file, [meta,original,processed,download,result])
        button.click(run, [file]+controls, [processed,download,result], concurrency_limit=1)
    return demo

if __name__ == '__main__':
    build_ui().queue(default_concurrency_limit=1).launch(server_name='127.0.0.1', server_port=7863,
        share=False, inbrowser=True, allowed_paths=[str(ROOT/'output')], max_file_size='512mb',
        show_error=True, footer_links=[])
