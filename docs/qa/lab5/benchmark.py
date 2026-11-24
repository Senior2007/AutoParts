"""Exercise the local Django QA server with a Locust user profile."""
import argparse
import csv
import json
import math
import os
import platform
import sys
from collections import Counter, defaultdict
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit

import gevent
import locust
import psutil
from locust import FastHttpUser, between, task
from locust.env import Environment

CATALOG = '/parts/'
SLA_MS = 1000
SLA_ERRORS = 1.0
TARGET_USERS = 15
STRESS_USERS = (30, 60, 90, 120, 160, 200)


class Visitor(FastHttpUser):
    wait_time = between(0.35, 0.65)
    connection_timeout = 2
    network_timeout = 3
    max_retries = 0

    def on_stop(self):
        self.client.client.close()

    def page(self, path, name, marker):
        with self.client.get(path, name=name, catch_response=True, allow_redirects=False) as response:
            if response.status_code != 200:
                response.failure(f'HTTP {response.status_code}: {getattr(response, "error", None) or "unexpected status"}')
            elif marker not in response.content:
                response.failure('Unexpected page body')

    @task(45)
    def catalog(self):
        self.page(CATALOG, CATALOG, b'id="catalog-table"')

    @task(25)
    def search(self):
        self.page('/parts/?q=QA&sort=price', '/parts/ [search]', b'id="catalog-table"')

    @task(20)
    def part(self):
        self.page(f'/parts/{self.environment.part_id}/', '/parts/<id>/', b'itemprop="name"')

    @task(10)
    def cart(self):
        self.page('/cart/', '/cart/', b'<main')


def percentile(values, p):
    return round(sorted(values)[math.ceil(len(values) * p) - 1], 2) if values else None


def summarize(points, seconds):
    times = [row[0] for row in points]
    failures = Counter(error for _, error in points if error)
    failed = sum(failures.values())
    return {
        'requests': len(points), 'rps': round(len(points) / seconds, 2),
        'errors': failed, 'error_pct': round(100 * failed / len(points), 3) if points else None,
        'p50_ms': percentile(times, 0.50), 'p95_ms': percentile(times, 0.95),
        'p99_ms': percentile(times, 0.99), 'max_ms': round(max(times), 2) if times else None,
        'failure_types': dict(failures),
    }


def draw(rows, destination):
    from matplotlib import pyplot as plt

    curve = [r for r in rows if r['stage'] != 'recovery']
    x = [r['users'] for r in curve]
    fig, ax = plt.subplots(figsize=(8.4, 4.6), layout='constrained')
    ax.plot(x, [r['p50_ms'] for r in curve], 'o-', color='#317b88', label='p50, все запросы')
    ax.plot(x, [r['p95_ms'] for r in curve], 'o-', color='#224673', label='p95, все запросы')
    ax.plot(x, [r['catalog_p95_ms'] for r in curve], 's--', color='#bd592d', label='p95, GET /parts/')
    ax.axhline(SLA_MS, color='#8c3643', linestyle=':', label='Порог 1000 мс')
    onset = next((r for r in curve if r.get('onset')), None)
    if onset:
        ax.axvline(onset['users'], color='#555b68', alpha=0.8, linestyle='-.',
                   label=f'Деградация с {onset["users"]} пользователей')
    ax.set(xlabel='Одновременные пользователи', ylabel='Время отклика, мс',
           title='AutoParts · время отклика при росте нагрузки', xticks=x, yscale='log')
    ax.grid(alpha=0.2)
    ax.legend(loc='upper left', fontsize='small')
    fig.savefig(destination / 'response-time.png', dpi=170)
    plt.close(fig)


def await_user_count(runner, users):
    deadline = monotonic() + 20
    while runner.user_count != users:
        if monotonic() >= deadline:
            raise RuntimeError(f'Locust запустил {runner.user_count} из {users} пользователей.')
        gevent.sleep(0.10)


def run(host, part_id, server_pid, destination, quick=False):
    address = urlsplit(host)
    if (address.scheme != 'http' or address.hostname != '127.0.0.1' or not address.port
            or address.username or address.password or address.path or address.query or address.fragment
            or not os.environ.get('AUTOPARTS_QA_STATE')):
        raise ValueError('Для нагрузочного прогона нужен временный стенд docs.qa на 127.0.0.1.')
    environment = Environment(user_classes=[Visitor], host=host, stop_timeout=4)
    environment.part_id = part_id
    runner = environment.create_local_runner()
    service = psutil.Process(server_pid)
    generator = psutil.Process()
    points = None

    @environment.events.request.add_listener
    def capture(name, response_time, exception, **kwargs):
        if points is not None:
            points[name].append((response_time, str(exception) if exception is not None else ''))

    def cpu_total(process):
        cpu = process.cpu_times()
        return cpu.user + cpu.system

    def stage(name, users, window):
        nonlocal points
        runner.start(users, spawn_rate=25)
        await_user_count(runner, users)
        gevent.sleep(1.5 if quick else 3.0)
        before = (cpu_total(service), cpu_total(generator))
        measured_at = monotonic()
        points = defaultdict(list)
        gevent.sleep(window)
        snapshot, points = points, None
        elapsed = monotonic() - measured_at
        after = (cpu_total(service), cpu_total(generator))
        catalog = summarize(snapshot[CATALOG], elapsed)
        if not catalog['requests']:
            raise RuntimeError(f'На этапе {name} ({users}) нет результатов GET /parts/.')
        totals = summarize([item for values in snapshot.values() for item in values], elapsed)
        row = {
            'stage': name, 'users': users, 'seconds': round(elapsed, 3), **totals,
            'catalog_p95_ms': catalog['p95_ms'], 'catalog_max_ms': catalog['max_ms'],
            'server_cpu_pct': round(100 * (after[0] - before[0]) / elapsed, 1),
            'generator_cpu_pct': round(100 * (after[1] - before[1]) / elapsed, 1),
            'server_rss_mib': round(service.memory_info().rss / 1024**2, 1),
            'server_threads': service.num_threads(),
            'routes': {route: summarize(values, elapsed) for route, values in snapshot.items()},
        }
        row['sla'] = row['p95_ms'] <= SLA_MS and row['error_pct'] <= SLA_ERRORS and row['catalog_max_ms'] <= SLA_MS
        print(f'{name:>9} {users:>3} VU · {row["rps"]:>6.1f} req/s · '
              f'p95 {row["p95_ms"]:>7.2f} ms · {row["error_pct"]:.3f}% errors', flush=True)
        return row

    rows = []
    stop_reason = 'stress-user-limit'
    try:
        rows.append(stage('baseline', 1, 7 if quick else 18))
        rows.append(stage('target', TARGET_USERS, 7 if quick else 18))
        threshold = max(50, 3 * rows[-1]['catalog_p95_ms'])
        for users in ((30, 60, 120) if quick else STRESS_USERS):
            row = stage('stress', users, 6 if quick else 14)
            row['slower'] = row['catalog_p95_ms'] > threshold
            rows.append(row)
            if row['error_pct'] >= 10 or row['p95_ms'] >= 2400:
                stop_reason = 'stress-stop-threshold'
                break
        runner.start(0, spawn_rate=25)
        await_user_count(runner, 0)
        idle_seconds = 3 if quick else 8
        gevent.sleep(idle_seconds)
        recovery = stage('recovery', 1, 7 if quick else 18)
        rows.append(recovery)
    finally:
        runner.quit()

    stress = [r for r in rows if r['stage'] == 'stress']
    repeated = next((a for a, b in zip(stress, stress[1:]) if a['slower'] and b['slower']), None)
    severe = next((r for r in stress if not r['sla']), None)
    onset = min((r for r in [repeated, severe] if r is not None), key=lambda r: r['users'], default=None)
    if onset:
        onset['onset'] = True
    recovery['restored'] = recovery['sla'] and recovery['p95_ms'] <= max(30, 2 * rows[0]['p95_ms'])
    summary = {
        'locust': locust.__version__, 'python': platform.python_version(),
        'platform': platform.platform(), 'logical_cpus': psutil.cpu_count(),
        'quick': quick, 'target_users': TARGET_USERS, 'stress_stop_reason': stop_reason,
        'degradation_users': onset['users'] if onset else None,
        'catalog_degradation_threshold_ms': threshold,
        'idle_before_recovery_seconds': idle_seconds,
        'target_passed': rows[1]['sla'], 'recovered': recovery['restored'], 'steps': rows,
    }
    (destination / 'load-results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    csv_columns = ['stage', 'users', 'seconds', 'requests', 'rps', 'errors', 'error_pct',
                   'p50_ms', 'p95_ms', 'p99_ms', 'max_ms', 'catalog_p95_ms', 'catalog_max_ms',
                   'server_cpu_pct', 'generator_cpu_pct', 'server_rss_mib', 'server_threads', 'sla']
    with (destination / 'load-results.csv').open('w', newline='') as file:
        writer = csv.DictWriter(file, csv_columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    draw(rows, destination)
    return int(not summary['target_passed'] or not summary['recovered'])


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('host')
    cli.add_argument('part_id', type=int)
    cli.add_argument('server_pid', type=int)
    cli.add_argument('destination', type=Path)
    cli.add_argument('--quick', action='store_true')
    args = cli.parse_args()
    sys.exit(run(args.host, args.part_id, args.server_pid, args.destination, args.quick))
