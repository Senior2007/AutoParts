"""Start the AutoParts QA labs from the project root."""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from contextlib import contextmanager, redirect_stderr
from datetime import datetime
from pathlib import Path
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import urlopen

QA = Path(__file__).resolve().parent
ROOT = QA.parents[1]
UI = QA / 'lab4/ui'
MANAGE = [sys.executable, str(ROOT / 'manage.py')]


def run(args, cwd=ROOT, **kwargs):
    return subprocess.run(args, cwd=cwd, **kwargs).returncode


def setup_django():
    import django

    django.setup()


def local_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@contextmanager
def server(port, log_path=None):
    command = [*MANAGE, 'runserver', f'127.0.0.1:{port}', '--noreload', '--insecure']
    with (log_path.open('w') if log_path else open(os.devnull, 'w')) as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        base = f'http://127.0.0.1:{port}'
        try:
            deadline = monotonic() + 10
            while monotonic() < deadline:
                if process.poll() is not None:
                    break
                try:
                    with urlopen(base + '/parts/', timeout=0.5) as response:
                        if response.status == 200:
                            break
                except (URLError, TimeoutError):
                    sleep(0.15)
            else:
                raise RuntimeError(f'Стенд не ответил, журнал {log_path}.')
            if process.poll() is not None:
                raise RuntimeError(f'Стенд завершился с кодом {process.returncode}, журнал {log_path}.')
            print(f'Стенд {base}', flush=True)
            yield base, process
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def prepare(state):
    (state / '.autoparts-qa').touch()
    os.environ.update(
        DJANGO_SETTINGS_MODULE='docs.qa.stand.settings',
        AUTOPARTS_QA_STATE=str(state),
        QA_PYTHON=sys.executable,
        MPLCONFIGDIR=str(state / 'matplotlib'),
        XDG_CACHE_HOME=str(state / 'cache'),
        PYTHONDONTWRITEBYTECODE='1',
    )
    for command in ['migrate', 'seed_data']:
        args = ['--noinput'] if command == 'migrate' else []
        subprocess.run([*MANAGE, command, *args], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, '-m', 'docs.qa', 'fixture', 'api'], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)


def fixture(args):
    if os.environ.get('DJANGO_SETTINGS_MODULE') != 'docs.qa.stand.settings':
        raise SystemExit('Фикстуры создаются в запущенном QA-стенде.')
    setup_django()
    from docs.qa.stand.fixtures import seed_api, seed_ui

    if args.mode == 'api':
        seed_api()
    else:
        if not args.key:
            raise SystemExit('Для UI-фикстуры нужен уникальный ключ.')
        seed_ui(args.mode, args.key)
    return 0


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run_lab(args, destination):
    if args.action == 'system':
        with (destination / 'application.txt').open('w') as log, redirect_stderr(log):
            setup_django()
            from docs.qa.lab3.system_cases import run as run_system

            run_system(destination)
        results = json.loads((destination / 'system-results.json').read_text())
        return int(any(row['status'] != 'PASS' for row in results))

    port = args.port if args.action == 'serve' else local_port()
    with server(port, destination / 'server.txt') as (base, process):
        if args.action == 'serve':
            print('Для остановки нажмите Ctrl+C. Для Postman задайте baseUrl из строки выше.',
                  flush=True)
            return process.wait()
        if args.action == 'security':
            with (destination / 'application.txt').open('w') as log, redirect_stderr(log):
                setup_django()
                from docs.qa.lab4.security_checks import run as run_security

                results = run_security(base)
            write_json(destination / 'security-results.json', results)
            for row in results['results']:
                print(f'{row["id"]} {row["status"]} · {row["title"]}')
            return int(any(row['status'] != 'PASS' for row in results['results']))
        if args.action == 'ui':
            npm = shutil.which('npm')
            if not npm or not (UI / 'node_modules' / '@playwright/test').exists():
                raise RuntimeError('Установите зависимости командой npm --prefix docs/qa/lab4/ui ci.')
            env = os.environ | {
                'QA_BASE_URL': base,
                'QA_PW_RESULTS': str(destination / 'ui-artifacts'),
                'QA_PW_JSON': str(destination / 'playwright-results.json'),
                'QA_PW_HTML': str(destination / 'playwright-report'),
            }
            project = [] if args.all_browsers else ['--project=Chrome-UI']
            return run([npm, 'test', '--', *project], cwd=UI, env=env)
        if args.action == 'api':
            local_postman = UI / 'node_modules/.bin/postman'
            postman = str(local_postman) if local_postman.exists() else shutil.which('postman')
            if not postman:
                raise RuntimeError(
                    'Установите зависимости командой npm --prefix docs/qa/lab4/ui ci --ignore-scripts '
                    'или запустите docs.qa serve для Postman Desktop.'
                )
            return run([postman, 'collection', 'run',
                        str(QA / 'lab4/postman/AutoParts.postman_collection.json'),
                        '--env-var', f'baseUrl={base}', '--ignore-redirects',
                        '--reporters', 'cli,json', '--reporter-json-export',
                        str(destination / 'postman-results.json')])
        if args.action == 'load':
            setup_django()
            from docs.qa.lab5.diagnostics import catalog_diagnostics
            from shop.models import Part

            sample = Part.objects.get(sku='QA-API-PART')
            write_json(destination / 'diagnostics.json', catalog_diagnostics())
            command = [sys.executable, '-m', 'docs.qa.lab5.benchmark', base,
                       str(sample.pk), str(process.pid), str(destination)]
            if args.quick:
                command.append('--quick')
            return run(command)
    return 0


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest='action', required=True)
    commands.add_parser('system', help='ЛР3: 36 системных кейсов')
    commands.add_parser('security', help='ЛР4: базовые проверки и локальный замер')
    ui = commands.add_parser('ui', help='ЛР4: Playwright')
    ui.add_argument('--all-browsers', action='store_true', help='добавить матрицу совместимости')
    commands.add_parser('api', help='ЛР4: Postman CLI')
    serve = commands.add_parser('serve', help='локальный стенд для демонстрации')
    serve.add_argument('--port', type=int, default=8765)
    load = commands.add_parser('load', help='ЛР5: профиль нагрузки Locust и график')
    load.add_argument('--quick', action='store_true', help='короткий демонстрационный прогон')
    commands.add_parser('lint', help='ЛР5: статическая проверка Ruff')
    commands.add_parser('matrix', help='ЛР5: проверка матрицы и построение заново')
    child = commands.add_parser('fixture', help='служебная команда подготовки синтетических данных')
    child.add_argument('mode', choices=['api', 'part', 'large'])
    child.add_argument('key', nargs='?')
    return cli


def main():
    args = parser().parse_args()
    if args.action == 'fixture':
        return fixture(args)
    if args.action == 'lint':
        return run([sys.executable, '-m', 'ruff', 'check', '--config', str(QA / 'ruff.toml'),
                    'config', 'shop', 'manage.py', 'docs/qa'])
    if args.action == 'matrix':
        return run([sys.executable, '-m', 'docs.qa.lab5.traceability'])
    if args.action == 'serve' and not 1024 <= args.port <= 65535:
        raise SystemExit('Укажите порт от 1024 до 65535.')
    destination = QA / 'runs' / f'{datetime.now():%Y%m%d-%H%M%S-%f}-{args.action}'
    destination.mkdir(parents=True)
    print(f'Результаты: {destination}', flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix='autoparts-qa-') as tmp:
            prepare(Path(tmp))
            return run_lab(args, destination)
    except KeyboardInterrupt:
        return 130
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
