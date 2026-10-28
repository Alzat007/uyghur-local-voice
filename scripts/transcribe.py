"""Optional local Uyghur CTC draft; use CPU to avoid MPS convolution length limits."""
import argparse
import math
from pathlib import Path
from common import lock, offline, root, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir')
    p.add_argument('--audio', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists() or args.output.with_suffix('.json').exists():
        raise FileExistsError('Refusing to overwrite a transcript.')
    data = root(args.data_dir)
    offline()
    import numpy as np
    import soundfile as sf
    import torch
    from scipy.signal import resample_poly
    from transformers import AutoProcessor, Wav2Vec2ForCTC
    audio, sr = sf.read(args.audio, dtype='float32', always_2d=True)
    if not 1 <= len(audio) / sr <= 30 or not np.isfinite(audio).all():
        raise ValueError('Use a valid 1–30 second reference clip.')
    divisor = math.gcd(sr, 16000)
    audio = resample_poly(audio.mean(axis=1), 16000 // divisor, sr // divisor).astype(np.float32)
    with lock(data):
        torch.set_num_threads(4)
        model_path = data / 'models/OmniASR-CTC-300M-v2'
        processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
        model = Wav2Vec2ForCTC.from_pretrained(model_path, local_files_only=True).cpu().eval()
        with torch.inference_mode():
            text = processor.batch_decode(model(**processor(audio, sampling_rate=16000, return_tensors='pt')).logits.argmax(-1))[0]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(text + '\n')
    write_json(args.output.with_suffix('.json'), {'text': text, 'status': 'automatic_draft_not_human_verified'})
    print(text)


if __name__ == '__main__':
    main()
