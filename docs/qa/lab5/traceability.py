"""Build the requirement matrix and case inventory from the reports and current pytest collection."""
import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path

from docs.qa.lab5.trace_links import BROWSER, BUSINESS, PARTIAL, POSTMAN, PYTEST, SECURITY, USE_CASES

LAB = Path(__file__).resolve().parent
QA = LAB.parent
ROOT = QA.parents[1]
REQ = re.compile(r'N?FR-\d{2}|(?:UC|BT)-\d+')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def requirements():
    srs = (ROOT / 'docs/requirements.md').read_text(encoding='utf-8')
    records = {}
    for number, value in re.findall(r'^- БТ-(\d+)\. (.+)$', srs, re.M):
        records[f'BT-{number}'] = value
    for id, value in re.findall(r'^\| (UC-\d+) \| [^|]+ \| ([^|]+?) \|', srs, re.M):
        records[id] = value
    item = re.search(r'((?:UC-9) [^)]+)', srs)
    require(item, 'UC-9 из диаграммы ЛР1 не найден.')
    records['UC-9'] = item.group(1).removeprefix('UC-9 ') + ' (из диаграммы ЛР1)'
    for id, first, second in re.findall(r'^\| (N?FR-\d{2}) \| (.*?) \| (.*?) \|$', srs, re.M):
        records.setdefault(id, second if id.startswith('NFR') else first)
    expected = (
        {f'BT-{i}' for i in range(1, 5)}
        | {f'UC-{i}' for i in range(1, 10)}
        | {f'FR-{i:02}' for i in range(1, 23)}
        | {f'NFR-{i:02}' for i in range(1, 8)}
    )
    require(records.keys() == expected, 'Список требований SRS изменился. Обновите трассировку.')
    return records


def invert(mapping, prefix=''):
    result = defaultdict(list)
    for requirement, tests in mapping.items():
        for test in tests.split():
            result[prefix + test].append(requirement)
    return result


def test_rows():
    rows = []

    def add(lab, id, name, refs, path):
        rows.append(dict(lab=lab, id=id, name=name, refs=sorted(set(refs)), path=path))

    names = invert(PYTEST, 'test_')
    collect = subprocess.check_output(
        [sys.executable, '-m', 'pytest', '-o', 'addopts=', '--collect-only', '-q'],
        cwd=ROOT, text=True,
    )
    seen = set()
    for line in sorted(collect.splitlines()):
        if not line.startswith('shop/tests/') or '::' not in line:
            continue
        node = line.strip()
        family = node.split('[', 1)[0]
        name = family.rsplit('::', 1)[-1]
        seen.add(name)
        add('ЛР2', node, name, names.get(name, []), '../../../' + node.split('::', 1)[0])
    require(names.keys() <= seen, f'Не найдены тесты pytest: {sorted(names.keys() - seen)}.')
    add('ЛР2', 'COV-01', 'pytest-cov · покрытие кода', ['NFR-07'], 'evidence/pytest.txt')

    for case in read_json(QA / 'lab3/system-results.json'):
        add('ЛР3', case['id'], case['title'], REQ.findall(case['req']), '../lab3/report.html#' + case['id'])

    pm = read_json(QA / 'lab4/postman/report.json')['results']
    manifest = read_json(QA / 'lab4/postman/AutoParts.postman_collection.json')
    registered = [item['name'] for folder in manifest['item'] for item in folder['item']]
    require([request['name'] for request in pm] == registered, 'Состав коллекции отличается от отчёта Postman.')
    names = invert(POSTMAN)
    require(names.keys() <= {str(r['n']) for r in pm}, 'Неизвестный индекс Postman.')
    for r in pm:
        add('ЛР4', f'PM-{r["n"]:02}', r['name'], names.get(str(r['n']), []), '../lab4/postman/report.html#requests')

    for record in read_json(QA / 'lab4/playwright-results.json'):
        case, project = record['id'], record['project']
        require(case in BROWSER, f'Неизвестный сценарий Playwright {case}.')
        anchor = 'ui' if project == 'Chrome-UI' else f'{project}-{case}'
        add('ЛР4', f'{project}:{case}', record['name'], BROWSER[case].split(), f'../lab4/report.html#{anchor}')
    for record in read_json(QA / 'lab4/security-results.json')['results']:
        case = record['id']
        add('ЛР4', case, record['title'], SECURITY[case].split(), '../lab4/security-results.json')
    add('ЛР3', 'VAL-01', 'Четыре HTML-страницы · vnu.jar', ['NFR-06'], '../lab3/html-validation.txt')
    load = read_json(LAB / 'evidence/load-results.json')
    for i, row in enumerate(load['steps'], 1):
        add('ЛР5', f'LOAD-{i:02}', f'Locust · {row["stage"]} · {row["users"]} пользователей',
            ['NFR-01'], 'report.html#results')
    return rows


def defect_index():
    rows = (ROOT / 'ISSUES.md').read_text(encoding='utf-8')
    result = defaultdict(set)
    for id, refs in re.findall(r'^\| (?:\[)?((?:BUG|QA)-\d+)(?:\]\([^)]*\))? \| ([^|]+) \|', rows, re.M):
        for ref in REQ.findall(refs):
            result[ref].add(id)
    return result


def csv_file(path, cells):
    with path.open('w', newline='', encoding='utf-8-sig') as file:
        csv.writer(file).writerows(cells)


def link(path, title):
    return f'<a href="{escape(path, quote=True)}">{escape(title)}</a>'


def table(headers, rows):
    head = ''.join(f'<th scope="col">{escape(h)}</th>' for h in headers)
    body = ''.join('<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>' for row in rows)
    return f'<div class="table"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render():
    srs = requirements()
    tests = test_rows()
    direct = defaultdict(list)
    for item in tests:
        require(set(item['refs']) <= srs.keys(), f'Неизвестное требование для {item["id"]}.')
        for id in item['refs']:
            direct[id].append(item)
    require(len({t['id'] for t in tests}) == len(tests), 'Повтор ID теста.')
    groups = USE_CASES | BUSINESS

    def inherited(id):
        result = {test['id']: test for test in direct[id]}
        for child in groups.get(id, '').split():
            require(child in srs, f'Неизвестная связь {id} → {child}.')
            result.update({test['id']: test for test in inherited(child)})
        return list(result.values())

    defects = defect_index()
    matrix, tables, csv_rows = [], [], []
    for id, name in srs.items():
        linked = inherited(id)
        flags = PARTIAL.get(id, '')
        status = 'Без тест-кейса' if not linked else 'Частично' if flags else 'Покрыто'
        issue_ids = sorted(defects[id])
        matrix.append(dict(id=id, text=name, status=status, defects=issue_ids, test_count=len(linked)))
        links = []
        for lab in ['ЛР2', 'ЛР3', 'ЛР4', 'ЛР5']:
            selected = [r for r in linked if r['lab'] == lab]
            labels = {}
            for r in selected:
                key = r['id'].split('[', 1)[0]
                if lab == 'ЛР2' and '::' in key:
                    key = key.rsplit('::', 1)[-1]
                labels.setdefault(key, r['path'])
            if labels:
                body = ', '.join(link(path, key) for key, path in labels.items())
                links.append(f'<details><summary>{lab} · {len(selected)}</summary>{body}</details>')
        evidence = ''
        if id.startswith(('FR-', 'NFR-')):
            evidence = link(f'../lab3/requirements.html#{id}', id)
        else:
            evidence = link('../../requirements.md', id.replace('BT-', 'БТ-'))
        badges = ' '.join(link(f'../../../ISSUES.md#{i.lower()}', i) for i in issue_ids)
        risk = ('<strong class="fail">Высокий риск</strong><br>' if len(issue_ids) >= 2 else '') + badges
        row_note = flags or ('Через ' + groups[id] if id in groups else '')
        tables.append((evidence, escape(name.replace('`', '')), escape(status) + '<br>' + escape(row_note),
                       ''.join(links) or '—', risk or '—'))
        csv_rows.append((id,status,len(linked),'; '.join(r['id'] for r in linked),'; '.join(issue_ids),row_note))

    base = [x for x in matrix if x['id'].startswith(('FR-', 'NFR-'))]
    count = sum(x['test_count'] > 0 for x in base)
    overall = sum(x['test_count'] > 0 for x in matrix)
    orphan = [t for t in tests if not t['refs']]
    orphan_groups = {}
    for t in orphan:
        key = t['id'].split('[', 1)[0]
        if key not in orphan_groups:
            orphan_groups[key] = [t, 0]
        orphan_groups[key][1] += 1
    orphan_table = table(('Набор','Тест или группа','Запусков','Что уточнить'), (
        (escape(test['lab']), link(test['path'], key), str(number),
         'Сверить с ЛР1. Если функция нужна, добавить требование и привязку.')
        for key,(test,number) in orphan_groups.items()
    ))
    inventory = table(('Набор','ID','Название','Прямые связи'), (
        (escape(t['lab']), link(t['path'], t['id']), escape(t['name']), escape(', '.join(t['refs']) or '—'))
        for t in tests
    ))
    stamp = datetime.now().astimezone().date().isoformat()
    html = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Матрица трассируемости · AutoParts</title><link rel="stylesheet" href="../report.css"></head>
<body><header><nav>{link('../index.html','Лабораторные работы')}</nav><h1>Матрица трассируемости</h1><p>ЛР5 · AutoParts · {stamp}</p></header>
<main><section><h2>Покрытие и риски</h2>
<p>Тест-кейсами связано <strong>{count}/{len(base)} FR и NFR ({100 * count / len(base):.2f}%)</strong>. С учётом БТ и UC, которые наследуют проверки нижнего уровня, связано {overall}/{len(matrix)} требований ({100 * overall / len(matrix):.2f}%). Связь показывает наличие теста независимо от статуса PASS или FAIL. Маркер «Частично» указывает на оставшуюся область.</p>
<p>Основа ЛР1 — SRS и диаграмма заказа. Для ЛР2 использована текущая коллекция pytest. Для ЛР3–ЛР5 использованы сохранённые прогоны. Параметризованные вызовы pytest, запросы Postman и браузерные профили учтены отдельными записями. Дефекты посчитаны по уникальным записям ISSUES.md. Высоким риском отмечены требования с двумя и более дефектами.</p>
<p>{link('matrix.csv','Матрица CSV')} · {link('test-inventory.csv','Инвентарь тестов CSV')} · {link('#unmapped','Тесты без связи')} · {link('#inventory','Полный инвентарь')}</p>
</section><section id="requirements"><h2>Требования и выполненные проверки</h2>{table(('Требование','Формулировка','Покрытие','Тесты и работы','Дефекты'), tables)}</section>
<section id="unmapped"><h2>Тесты без требования</h2>
<p>{len(orphan)} запусков, {len(orphan_groups)} групп. Например, слайдер, справочник сотрудников, раскрытие деталей ошибок и прикладной аудит проверены, но отдельные требования для них в SRS отсутствуют. На ревью решается, добавить ли требования или убрать лишние проверки.</p>{orphan_table}</section>
<section id="inventory"><h2>Инвентарь</h2><details><summary>Все {len(tests)} записей</summary>{inventory}</details></section></main></body></html>
"""
    (LAB / 'matrix.html').write_text(html, encoding='utf-8')
    csv_file(LAB / 'matrix.csv', [('ID','Статус','Кол-во','Тесты','Дефекты','Комментарий'), *csv_rows])
    csv_file(LAB / 'test-inventory.csv', [
        ('Работа','ID','Имя','Требования','Доказательство'),
        *((t['lab'], t['id'], t['name'], ', '.join(t['refs']), t['path']) for t in tests),
    ])
    unmapped = ', '.join(x['id'] for x in base if not x['test_count'])
    print(f'FR/NFR: {count}/{len(base)}. Все уровни: {overall}/{len(matrix)}. '
          f'Без тестов: {unmapped}. Без требования: {len(orphan)} запусков.')
    return 0


if __name__ == '__main__':
    sys.exit(render())
