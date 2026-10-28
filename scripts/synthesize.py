"""Generate Uyghur speech with a saved authorized voice, completely offline."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import time
import uuid
from common import MAX_CHARS, load_model, lock, private_path, root, voice, write_json


def progress(stage):
    print('PROGRESS ' + json.dumps({'stage': stage}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir')
    p.add_argument('--text-file', type=Path, required=True)
    p.add_argument('--voice')
    p.add_argument('--output', type=Path)
    p.add_argument('--steps', type=int, default=32)
    args = p.parse_args()
    data = root(args.data_dir)
    text = args.text_file.read_text(encoding='utf-8').strip()
    if not 1 <= len(text) <= MAX_CHARS:
        raise ValueError('请输入 1–2000 字符的维语文案；长文请分段生成。')
    if not 8 <= args.steps <= 64:
        raise ValueError('steps must be between 8 and 64.')
    output = (args.output or data / 'outputs' / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8] + '.wav')).expanduser().absolute()
    if output.suffix.lower() != '.wav':
        raise ValueError('Output must be a WAV file.')
    if output.exists() or output.with_suffix('.json').exists():
        raise FileExistsError('Refusing to overwrite an existing output.')
    key, selected = voice(data, args.voice)
    start = time.monotonic()
    with lock(data):
        import numpy as np
        import soundfile as sf
        from omnivoice import VoiceClonePrompt
        progress('loading')
        model, device = load_model(data)
        prompt = VoiceClonePrompt.load(str(private_path(data, selected['prompt'])))
        progress('generating')
        samples = np.asarray(model.generate(text=text, language='ug', num_step=args.steps,
                                           voice_clone_prompt=prompt)[0], dtype=np.float32)
        if not samples.size or not np.isfinite(samples).all():
            raise RuntimeError('模型输出为空或含无效数值。')
        rms = float(np.sqrt(np.mean(samples ** 2)))
        if rms < 1e-5:
            raise RuntimeError('模型输出接近静音。')
        peak = float(np.max(np.abs(samples)))
        # Only attenuate peaks; preserve natural volume while avoiding PCM clipping.
        gain = min(1.0, 0.98 / max(peak, 1e-8))
        progress('saving')
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as stream:
            sf.write(stream, samples * gain, model.sampling_rate, format='WAV', subtype='PCM_16')
        info = {'text': text, 'voice_id': key, 'voice_name': selected['name'], 'language': 'ug',
                'mode': 'saved_cloned_voice', 'reference_transcript_status': selected['transcript_status'],
                'sample_rate': model.sampling_rate, 'duration_seconds': len(samples) / model.sampling_rate,
                'elapsed_seconds': time.monotonic() - start, 'device': device, 'peak_before_gain': peak,
                'gain': gain, 'rms_dbfs': 20 * float(np.log10(rms * gain)),
                'pronunciation_and_similarity': 'requires_listening_review', 'output': str(output)}
        write_json(output.with_suffix('.json'), info)
        progress('done')
        print(json.dumps(info, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
