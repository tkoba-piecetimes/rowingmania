import json, glob, sys, io
from collections import defaultdict, Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

years = {}
for f in sorted(glob.glob(r'C:\Users\tatsu\claudecode\rowingmania\data\results\*.json')):
    d = json.load(open(f, encoding='utf-8'))
    years[d['year']] = d

def is_mixed(n):
    return '混成' in n or '合同' in n or '連合' in n or '・' in n

SUF = ['理工漕艇部', '医歯学系', '理工学系', '医学部', '理工学部', '水産学部', '教育学部',
       '工学部', '農学部', '大学院', '経済学部', '園芸学部', '行政社会学部', 'ボート部', '漕艇部']

def norm(n):
    m = n
    for s in SUF:
        if m.endswith(s):
            m = m[: -len(s)]
    return m

def first_round_crews(ev):
    total = 0
    for code, e in ev.items():
        byround = defaultdict(list)
        for r in e['races']:
            byround[r['round']].append(r)
        pick = 'heat' if 'heat' in byround else max(
            byround, key=lambda k: sum(len(r['results']) for r in byround[k]))
        total += sum(len(r['results']) for r in byround[pick])
    return total

print('year | raw | norm | crews | 男子出場(norm) | 女子出場(norm) | 男種目 | 女種目')
for y in sorted(years):
    d = years[y]; ev = d['events']
    raw = set(); fem = set(); mal = set()
    for c, e in ev.items():
        for r in e['races']:
            for res in r['results']:
                u = res['university']; raw.add(u)
                if is_mixed(u):
                    continue
                (fem if c.startswith('w') else mal).add(norm(u))
    normed = {norm(u) for u in raw if not is_mixed(u)}
    nm = len([c for c in ev if c.startswith('m')])
    nw = len([c for c in ev if c.startswith('w')])
    print(f'{y} | {len(raw)} | {len(normed)} | {first_round_crews(ev)} | {len(mal)} | {len(fem)} | {nm} | {nw}')

appear = defaultdict(set)
for y, d in years.items():
    for c, e in d['events'].items():
        for r in e['races']:
            for res in r['results']:
                if is_mixed(res['university']):
                    continue
                appear[norm(res['university'])].add(y)
full = sorted([u for u, ys in appear.items() if len(ys) == 25])
print()
print('皆勤(25大会すべて):', len(full))
print('、'.join(full))
print('総ユニーク校名:', len(appear), ' 1大会のみ:', sum(1 for v in appear.values() if len(v) == 1))
