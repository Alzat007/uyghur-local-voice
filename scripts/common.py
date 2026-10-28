"""Portable paths and private voice catalog; no model imports in the web server."""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile

DEFAULT_DATA = Path.home() / 'Library/Application Support/uyghur-voice-lab'
SKILL = Path(__file__).resolve().parent.parent
MAX_CHARS = 2000


def root(value=None):
    return Path(value or os.environ.get('UYGHUR_VOICE_DATA_DIR') or DEFAULT_DATA).expanduser().resolve()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.writing-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextlib.contextmanager
def lock(data, name='inference'):
    data.mkdir(parents=True, exist_ok=True)
    with (data / ('.' + name + '.lock')).open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('已有任务正在运行，请稍后再试。')
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def valid_id(value):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', value or ''):
        raise ValueError('音色 ID 只能包含小写字母、数字、下划线和连字符。')
    return value


def private_path(data, relative):
    path = (data / relative).resolve()
    if data not in path.parents:
        raise ValueError('音色文件必须保存在私人数据目录中。')
    return path


def catalog(data):
    path = data / 'voices.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'version': 1, 'default_voice': None, 'voices': {}}


def voice(data, selected=None):
    entries = catalog(data)
    selected = selected or entries.get('default_voice')
    item = entries['voices'].get(selected)
    if not item:
        raise ValueError('尚未保存此音色，请先导入已授权的参考音频。')
    if not item.get('authorization'):
        raise ValueError('此音色没有授权记录。')
    if item.get('transcript_status') not in ('human_verified', 'automatic_draft_user_approved_for_trial'):
        raise ValueError('参考文字尚未确认可用于合成。')
    if not private_path(data, item['prompt']).is_file():
        raise ValueError('音色提示文件缺失。')
    return selected, item


def status(data):
    entries = catalog(data)
    missing = []
    for relative in ('.venv/bin/python', 'models/OmniVoice/model.safetensors',
                     'models/OmniVoice/config.json', 'models/OmniVoice/tokenizer.json',
                     'models/OmniVoice/audio_tokenizer/model.safetensors'):
        if not (data / relative).is_file():
            missing.append(relative)
    voices = []
    for key, item in entries['voices'].items():
        error = None
        try:
            voice(data, key)
        except ValueError as exc:
            error = str(exc)
        voices.append({'id': key, 'name': item['name'], 'ready': not missing and not error,
                       'trial': item.get('transcript_status') != 'human_verified', 'error': error})
    return {'service': 'uyghur-local-voice', 'data_dir': str(data), 'missing': missing,
            'ready': not missing and any(v['ready'] for v in voices),
            'default_voice': entries.get('default_voice'), 'voices': voices}


def offline():
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')


def load_model(data):
    offline()
    import torch
    from omnivoice import OmniVoice
    torch.set_num_threads(4)
    torch.manual_seed(42)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    return OmniVoice.from_pretrained(data / 'models/OmniVoice', device_map=device,
                                    dtype=torch.float16 if device == 'mps' else torch.float32,
                                    local_files_only=True), device
