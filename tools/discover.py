#!/usr/bin/env python3
"""
AnyLearn 第三方书籍发现器。

1. 用 GitHub Search API 扫 topic:al-book（以及 al-book- 开头的仓库名）
2. 对每个候选读 albook.json，三重标记全对上才继续
3. 跑 validate_book.py 完整校验
4. 写出 registry.json + reports/<owner>__<repo>.json

用法:
    python3 discover.py [--dry] [--only owner/repo]
"""
import sys, os, json, time, datetime
from urllib.parse import urlencode

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
# gh.py 与 .tokens 不入库（含密钥），从本地工作区找
for _cand in ['/data/workspace', os.environ.get('AL_HOME', '')]:
    if _cand and os.path.isfile(os.path.join(_cand, 'gh.py')):
        sys.path.insert(0, _cand)
        break
try:
    import gh
except ImportError:
    gh = None
    print('警告：找不到 gh.py，无法访问 GitHub。设置 AL_HOME 指向含 gh.py 的目录。')
import validate_book as VB

DRY = '--dry' in sys.argv
ONLY = None
if '--only' in sys.argv:
    ONLY = sys.argv[sys.argv.index('--only') + 1]

TOPICS = ['al-book']
NAME_PREFIX = 'al-book-'


def search_repos():
    """搜出候选仓库（去重）。"""
    found = {}
    for q in [f'topic:{t}' for t in TOPICS] + [f'{NAME_PREFIX} in:name']:
        page = 1
        while page <= 5:
            # 查询串必须转义，否则含空格的 q（如 "al-book- in:name") 会直接报错
            d = gh.req('GET', '/search/repositories?' + urlencode(
                {'q': q, 'per_page': 100, 'page': page, 'sort': 'updated'}), tok=gh.COOL)
            if d.get('__err__'):
                print('  搜索失败:', d.get('message', d)); break
            items = d.get('items', [])
            for it in items:
                found[it['full_name']] = it
            if len(items) < 100:
                break
            page += 1
            time.sleep(1)
    return found


def looks_like_candidate(repo):
    """三重标记的第一重：仓库名。名字不对也继续（可能只是没按约定起名），
    但会在报告里记一笔。"""
    return repo['name'].startswith(NAME_PREFIX)


def check_marks(owner, repo):
    """三重标记的第二、三重：topic + albook.json 的 format 字段。"""
    info = {'name_ok': repo['name'].startswith(NAME_PREFIX),
            'topic_ok': False, 'format_ok': False, 'reason': ''}
    try:
        topics = gh.req('GET', f'/repos/{owner}/{repo["name"]}/topics', tok=gh.COOL).get('names', [])
    except Exception:
        topics = []
    info['topic_ok'] = 'al-book' in (topics or [])

    raw = gh.getfile(owner, repo['name'], 'albook.json')
    if raw is None:
        info['reason'] = '根目录没有 albook.json'
        return info, None
    try:
        meta = json.loads(raw)
    except Exception as e:
        info['reason'] = f'albook.json 不是合法 JSON：{e}'
        return info, None
    fmt = str(meta.get('format', '')).strip()
    info['format_ok'] = (fmt == 'al-book')
    if not info['format_ok']:
        info['reason'] = f'format 字段是 "{fmt}"，应为 "al-book"'
    return info, meta


def main():
    if ONLY:
        owner, name = ONLY.split('/', 1)
        cands = {ONLY: {'full_name': ONLY, 'name': name, 'owner': {'login': owner},
                        'html_url': f'https://github.com/{ONLY}',
                        'description': '', 'stargazers_count': 0, 'pushed_at': '',
                        'default_branch': 'main'}}
    else:
        print('搜索候选仓库…')
        cands = search_repos()
    print(f'候选 {len(cands)} 个')

    registry = {'updated': datetime.datetime.utcnow().isoformat() + 'Z',
                'format_version': 1, 'books': []}
    seen_ids = {}

    for full, repo in sorted(cands.items()):
        owner, name = full.split('/', 1)
        if name in ('al-docs',):
            continue
        print(f'\n--- {full}')
        marks, meta = check_marks(owner, repo)
        if not marks['format_ok']:
            print(f'  跳过：{marks["reason"] or "format 字段不匹配"}')
            continue
        if not marks['name_ok']:
            print('  提示：仓库名不以 al-book- 开头（不影响收录，但建议改）')
        if not marks['topic_ok']:
            print('  提示：没有打 topic:al-book（不影响本次收录，但下次可能扫不到）')

        files = VB.load_from_github(full)
        rep = VB.validate(files)
        leaks = [r for r in VB.run_python_questions(files, rep) if r['starter_leaks']]
        for r in leaks:
            rep['errors'].append(f"{r['file']}#{r['idx']}: 题目无区分力——初始代码原样就能通过（{r['detail']}）")
        rep['ok'] = not rep['errors']

        bid = str((meta or {}).get('id', '')).strip() or name.replace(NAME_PREFIX, '', 1)
        if rep['ok']:
            if bid in seen_ids:
                rep['ok'] = False
                rep['errors'].append(f'id "{bid}" 与已收录的 {seen_ids[bid]} 冲突')
            else:
                seen_ids[bid] = full

        entry = {
            'id': bid,
            'repo': full,
            'url': repo.get('html_url', f'https://github.com/{full}'),
            'branch': repo.get('default_branch', 'main'),
            'stars': repo.get('stargazers_count', 0),
            'pushed_at': repo.get('pushed_at', ''),
            'ok': rep['ok'],
            'title': (meta or {}).get('title', name),
            'subtitle': (meta or {}).get('subtitle', ''),
            'desc': (meta or {}).get('desc', ''),
            'stage': (meta or {}).get('stage', 'other'),
            'level': (meta or {}).get('level', ''),
            'langs': (meta or {}).get('langs', []),
            'tags': (meta or {}).get('tags', []),
            'cover': (meta or {}).get('cover', ''),
            'license': (meta or {}).get('license', ''),
            'author': (meta or {}).get('author', {}),
            'chapters': (meta or {}).get('chapters', []),
            'stats': rep.get('stats', {}),
            'n_errors': len(rep['errors']),
            'n_warnings': len(rep['warnings']),
            'errors': rep['errors'][:20],
            'warnings': rep['warnings'][:20],
            'marks': marks,
        }
        registry['books'].append(entry)

        rdir = os.path.join(ROOT, 'reports')
        os.makedirs(rdir, exist_ok=True)
        with open(os.path.join(rdir, f'{owner}__{name}.json'), 'w', encoding='utf-8') as f:
            json.dump({'repo': full, 'meta': meta, 'report': rep}, f, ensure_ascii=False, indent=1)

        print(f"  {'✅ 通过' if rep['ok'] else '❌ 未通过'}："
              f"{entry['stats'].get('lessons', 0)} 课 / "
              f"{entry['stats'].get('questions', 0)} 题 / "
              f"错误 {len(rep['errors'])} / 警告 {len(rep['warnings'])}")
        for e in rep['errors'][:8]:
            print('     ✗', e)

    registry['books'].sort(key=lambda b: (not b['ok'], -b.get('stats', {}).get('lessons', 0)))
    reg_path = os.path.join(ROOT, 'registry.json')
    with open(reg_path, 'w', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, indent=1)
    nok = sum(1 for b in registry['books'] if b['ok'])
    print(f'\n共 {len(registry["books"])} 本，通过 {nok} 本 → {reg_path}')


if __name__ == '__main__':
    main()
