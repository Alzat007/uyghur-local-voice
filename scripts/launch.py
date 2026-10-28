"""Start or reuse the local panel, without a login service."""
import argparse
import json
import subprocess
import sys
import time
from urllib.request import urlopen
from urllib.error import URLError
import webbrowser
from common import root, SKILL


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir')
    p.add_argument('--port', type=int, default=8767)
    p.add_argument('--open', action='store_true')
    args = p.parse_args()
    data = root(args.data_dir)
    url = f'http://127.0.0.1:{args.port}'
    def check():
        try:
            with urlopen(url + '/api/status', timeout=2) as response:
                value = json.load(response)
        except URLError as exc:
            if getattr(exc, 'code', None):
                raise RuntimeError('端口已被其他服务占用，请指定其他 --port。')
            return False
        if value.get('service') != 'uyghur-local-voice' or value.get('data_dir') != str(data):
            raise RuntimeError('端口属于其他服务或数据目录，请指定其他 --port。')
        return True
    if not check():
        logs = data / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / 'panel.log').open('a') as log:
            process = subprocess.Popen([sys.executable, str(SKILL / 'scripts/panel.py'),
                                        '--data-dir', str(data), '--port', str(args.port)],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       start_new_session=True)
        for _ in range(40):
            if process.poll() is not None:
                raise RuntimeError('启动失败，请查看 logs/panel.log。')
            if check():
                break
            time.sleep(.2)
        else:
            raise RuntimeError('服务未及时启动，请查看 logs/panel.log。')
    print(url)
    if args.open:
        webbrowser.open(url)


if __name__ == '__main__':
    main()
