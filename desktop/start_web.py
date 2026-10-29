"""Start the source web app independently of a terminal; keep user data intact."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent.parent


def ensure(port=3340, data_dir=None):
    url = f'http://127.0.0.1:{port}'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def healthy():
        try:
            with opener.open(url+'/api/health', timeout=1) as response:
                return json.load(response).get('features', {}).get('review_opening_commercial') == 1
        except (OSError, ValueError, urllib.error.URLError):
            return False
    if healthy():
        return {'url': url, 'started': False, 'ready': True}
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', port)) == 0:
            raise RuntimeError('端口已由其他服务或旧版占用，请先停止旧服务。')
    python = ROOT/'.venv/Scripts/pythonw.exe' if os.name == 'nt' else ROOT/'.venv/bin/python'
    if not python.exists():
        raise RuntimeError('缺少本项目运行环境。请先按README安装依赖，或使用Windows EXE安装包。')
    data = Path(data_dir) if data_dir else Path(os.getenv('LOCALAPPDATA', str(Path.home())))/'AICounselReview'
    data.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    log = open(data/'web-start.log', 'ab')
    try:
        process = subprocess.Popen([str(python), '-X', 'utf8', str(ROOT/'desktop/server.py'), '--port', str(port), '--data-dir', str(data)],
                                   cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   creationflags=flags, start_new_session=os.name != 'nt')
    finally:
        log.close()
    deadline = time.monotonic()+60
    while time.monotonic() < deadline:
        if healthy():
            return {'url': url, 'started': True, 'ready': True, 'pid': process.pid}
        if process.poll() is not None:
            raise RuntimeError('服务启动失败，请查看数据目录中的web-start.log和server.log。')
        time.sleep(.3)
    raise RuntimeError('启动等待超时，请查看数据目录中的日志。')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=3340)
    parser.add_argument('--data-dir')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    try:
        result = ensure(args.port, args.data_dir)
        if not args.no_browser:
            webbrowser.open(result['url'])
        if sys.stdout:
            print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        if os.name == 'nt' and not args.no_browser:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), 'AI审稿团启动失败', 0x10)
        elif sys.stderr:
            print(str(error), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
