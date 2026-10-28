"""Manage voices locally. Authorization must reflect the user's actual statement."""
import argparse
import json
import shutil
import uuid
from common import catalog, lock, load_model, private_path, root, status, valid_id, voice, write_json


def import_trial(data):
    with lock(data, 'catalog'):
        entries = catalog(data)
        if 'uyghur-trial' in entries['voices']:
            return {'result': 'already_imported', **status(data)}
        previous = json.loads((data / 'project-status.json').read_text(encoding='utf-8'))
        if not previous.get('speaker_authorization') or not previous.get('trial_authorization'):
            raise ValueError('Existing trial lacks user authorization records.')
        from pathlib import Path
        prompt = Path(previous['voice_prompt']).resolve()
        if data not in prompt.parents or not prompt.is_file():
            raise ValueError('Existing private voice prompt is unavailable.')
        entries['voices']['uyghur-trial'] = {
            'name': '维语参考音色 · 试用', 'prompt': str(prompt.relative_to(data)),
            'authorization': previous['speaker_authorization'],
            'transcript_status': previous['reference_transcript_status'],
            'trial_authorization': previous['trial_authorization']}
        if not entries.get('default_voice'):
            entries['default_voice'] = 'uyghur-trial'
        write_json(data / 'voices.json', entries)
    return status(data)


def add(data, args):
    import numpy as np
    import soundfile as sf
    from pathlib import Path
    key = valid_id(args.id)
    text = Path(args.transcript).read_text(encoding='utf-8').strip()
    if not text or len(text) > 2000:
        raise ValueError('Reference transcript must contain 1–2000 characters.')
    if not args.authorization.strip():
        raise ValueError('An actual user authorization record is required.')
    if args.transcript_status == 'automatic_draft_user_approved_for_trial' and not args.trial_authorization:
        raise ValueError('Record the user’s approval to use this automatic draft for a trial.')
    audio, sr = sf.read(args.audio, dtype='float32', always_2d=True)
    if not 3 <= len(audio) / sr <= 10.1:
        raise ValueError('Choose a clean 3–10 second single-speaker reference clip.')
    if not np.isfinite(audio).all() or np.sqrt(np.mean(audio ** 2)) < 1e-5:
        raise ValueError('Reference is invalid or silent.')
    with lock(data), lock(data, 'catalog'):
        entries = catalog(data)
        if key in entries['voices']:
            raise ValueError('This voice ID already exists; choose a new ID.')
        destination = private_path(data, 'voices/' + key + '-' + uuid.uuid4().hex[:8])
        destination.mkdir(parents=True)
        try:
            sf.write(destination / 'reference.wav', audio, sr, subtype='PCM_16')
            (destination / 'transcript.txt').write_text(text + '\n', encoding='utf-8')
            model, _ = load_model(data)
            prompt = model.create_voice_clone_prompt(ref_audio=str(destination / 'reference.wav'), ref_text=text)
            prompt.save(str(destination / 'prompt.pt'))
            entries['voices'][key] = {
                'name': args.name, 'prompt': str((destination / 'prompt.pt').relative_to(data)),
                'authorization': args.authorization, 'transcript_status': args.transcript_status,
                'trial_authorization': args.trial_authorization}
            if not entries.get('default_voice'):
                entries['default_voice'] = key
            write_json(data / 'voices.json', entries)
        except BaseException:
            shutil.rmtree(destination)
            raise
    return status(data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir')
    commands = p.add_subparsers(dest='command', required=True)
    commands.add_parser('status')
    commands.add_parser('import-trial')
    default = commands.add_parser('set-default')
    default.add_argument('id')
    new = commands.add_parser('add')
    for field in ('id', 'name', 'audio', 'transcript', 'authorization'):
        new.add_argument('--' + field, required=True)
    new.add_argument('--transcript-status', required=True,
                     choices=['human_verified', 'automatic_draft_user_approved_for_trial'])
    new.add_argument('--trial-authorization')
    args = p.parse_args()
    data = root(args.data_dir)
    if args.command == 'status':
        result = status(data)
    elif args.command == 'import-trial':
        result = import_trial(data)
    elif args.command == 'add':
        result = add(data, args)
    else:
        with lock(data, 'catalog'):
            voice(data, args.id)
            entries = catalog(data)
            entries['default_voice'] = args.id
            write_json(data / 'voices.json', entries)
        result = status(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
