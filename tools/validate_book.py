#!/usr/bin/env python3
"""
第三方书籍（al-book v1）校验器。

输入：一个本地目录（已把仓库内容拉到本地），或直接从 GitHub 仓库读。
输出：一份 JSON 报告 {ok, errors[], warnings[], stats{}}

用法:
    python3 validate_book.py <本地目录>            # 校验本地目录
    python3 validate_book.py owner/repo            # 直接从 GitHub 读

严重问题（errors）会导致书籍不被收录；warnings 只是提示。
"""
import os, re, sys, json, ast, io, contextlib, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

FORMAT_KEY = 'al-book'
REQUIRED = ['id', 'title', 'subtitle', 'desc', 'stage', 'level', 'langs', 'author', 'license']
VALID_STAGES = {'基础', '标准库', '数据', '桌面', '算法', '工程', '网页', '实战', 'other'}
ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')


# ---------- quiz 解析（与 validate.py 保持一致） ----------
def parse_quiz(src):
    data = {}
    lines = src.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'^(\w+)\s*:\s*(.*)$', line)
        if not m:
            i += 1; continue
        key, val = m.group(1), m.group(2)
        if val in ('|', '>'):
            buf = []; i += 1
            while i < len(lines) and (re.match(r'^\s{2,}', lines[i]) or lines[i].strip() == ''):
                if lines[i].strip() != '': buf.append(re.sub(r'^\s{2}', '', lines[i]))
                i += 1
            data[key] = '\n'.join(buf); continue
        if val == '':
            buf = []; i += 1
            while i < len(lines) and re.match(r'^\s*-\s+', lines[i]):
                buf.append(re.sub(r'^\s*-\s+', '', lines[i]).strip()); i += 1
            data[key] = buf; continue
        data[key] = val.strip(); i += 1
    return data


def blocks(md):
    return [parse_quiz(m.group(1)) for m in re.finditer(r'```quiz\n([\s\S]*?)^```\s*$', md, re.M)]


def truthy(v):
    return str(v or '').strip().lower() == 'true'


# ---------- 从 GitHub 读一个仓库的内容 ----------
def load_from_github(slug):
    import gh
    owner, repo = slug.split('/', 1)
    files = {}
    for entry in gh.tree(owner, repo):
        if entry['type'] != 'blob':
            continue
        p = entry['path']
        # 只取我们需要的：声明文件 + content 下的文本
        if p == 'albook.json' or p == 'README.md' or p.startswith('content/'):
            if p.endswith(('.md', '.json')):
                files[p] = gh.getfile(owner, repo, p) or ''
    return files


def load_from_dir(root):
    files = {}
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if not fn.endswith(('.md', '.json')):
                continue
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, root).replace(os.sep, '/')
            if rel.startswith('.git/'):
                continue
            if rel == 'albook.json' or rel == 'README.md' or rel.startswith('content/'):
                try:
                    files[rel] = open(full, encoding='utf-8').read()
                except Exception:
                    pass
    return files


# ---------- 主校验 ----------
def validate(files):
    errors, warnings, stats = [], [], collections.Counter()

    # 1. 声明文件
    raw = files.get('albook.json')
    if raw is None:
        return {'ok': False, 'errors': ['albook.json 缺失：仓库根目录必须有这个文件'],
                'warnings': [], 'stats': {}}
    try:
        meta = json.loads(raw)
    except Exception as e:
        return {'ok': False, 'errors': [f'albook.json 不是合法 JSON：{e}'],
                'warnings': [], 'stats': {}}

    fmt = str(meta.get('format', '')).strip()
    if fmt != FORMAT_KEY:
        return {'ok': False,
                'errors': [f'format 字段必须是精确字符串 "{FORMAT_KEY}"，当前是 "{fmt}"'],
                'warnings': [], 'stats': {}}

    for k in REQUIRED:
        if not meta.get(k):
            errors.append(f'albook.json 缺必需字段：{k}')

    bid = str(meta.get('id', '')).strip()
    if bid and not ID_RE.match(bid):
        errors.append(f'id "{bid}" 含非法字符：只允许小写字母、数字和连字符，且必须以字母或数字开头')

    stage = str(meta.get('stage', '')).strip()
    if stage and stage not in VALID_STAGES:
        warnings.append(f'stage "{stage}" 不在常用分类里（{"/".join(sorted(VALID_STAGES))}），仍会收录但归为 other')
        meta['stage'] = 'other'

    langs = meta.get('langs') or []
    if not isinstance(langs, list) or not langs:
        errors.append('langs 必须是非空数组，例如 ["zh"] 或 ["zh","en"]')
        langs = []
    else:
        for L in langs:
            if L not in ('zh', 'en'):
                errors.append(f'langs 含未知语言 "{L}"（只支持 zh / en）')

    author = meta.get('author')
    if author is not None:
        if not isinstance(author, dict) or not str(author.get('name', '')).strip():
            errors.append('author 必须是对象且至少含 name')
    if not str(meta.get('license', '')).strip():
        pass  # 已在 REQUIRED 里报过

    # 2. 语言目录
    present = []
    for L in ('zh', 'en'):
        if any(p.startswith(f'content/{L}/') for p in files):
            present.append(L)
    for L in langs:
        if L not in present:
            errors.append(f'langs 声明了 "{L}"，但 content/{L}/ 下没有任何文件')

    if not present:
        errors.append('content/ 下找不到任何 zh/ 或 en/ 目录')

    # 3. 逐语言校验
    per_lang = {}
    for L in present:
        per_lang[L] = check_lang(L, files, errors, warnings, stats)

    # 4. 中英题数对齐
    if 'zh' in per_lang and 'en' in per_lang:
        zh_q = per_lang['zh']['questions']
        en_q = per_lang['en']['questions']
        if zh_q != en_q:
            errors.append(f'中英题数不一致：中文 {zh_q} 道，英文 {en_q} 道（必须逐文件对齐）')
        zh_l = per_lang['zh']['lessons']
        en_l = per_lang['en']['lessons']
        if zh_l != en_l:
            errors.append(f'中英课文数不一致：中文 {zh_l} 课，英文 {en_l} 课')

    stats['languages'] = len(present)
    return {
        'ok': not errors,
        'errors': errors,
        'warnings': warnings,
        'stats': {
            'lessons': stats['lessons'], 'tests': stats['tests'],
            'questions': stats['questions'], 'code_questions': stats['code'],
            'languages': len(present), 'lines': stats['lines'],
        },
        'per_lang': {k: v for k, v in per_lang.items()},
        'meta': meta,
    }


def check_lang(L, files, errors, warnings, stats):
    pre = f'content/{L}/'
    toc_raw = files.get(pre + 'toc.json')
    toc = None
    if toc_raw is None:
        errors.append(f'[{L}] 缺 content/{L}/toc.json')
    else:
        try:
            toc = json.loads(toc_raw)
        except Exception as e:
            errors.append(f'[{L}] toc.json 不是合法 JSON：{e}')

    # 目录里的实际文件
    lessons = {}
    tests = {}
    for p, txt in files.items():
        if not p.startswith(pre + 'lessons/'):
            continue
        fn = p[len(pre + 'lessons/'):]
        if fn.startswith('test-'):
            tests[fn[:-3]] = txt
        elif re.match(r'^\d{2}\.md$', fn):
            lessons[fn[:-3]] = txt

    # toc 声明的课号
    declared, declared_tests = [], []
    if toc:
        for ch in toc.get('chapters', []):
            for it in ch.get('lessons', []) or []:
                declared.append(str(it))
            if ch.get('test'):
                declared_tests.append(str(ch['test']))
    elif lessons:
        # 没有 toc 就按文件名推断（给警告）
        declared = sorted(lessons)
        warnings.append(f'[{L}] toc.json 不可用，按 lessons/ 下的文件名推断目录')

    # 缺失 / 孤儿
    for n in declared:
        if n not in lessons:
            errors.append(f'[{L}] toc 声明了 {n}.md，但 lessons/ 下找不到')
    for n in sorted(lessons):
        if n not in declared:
            errors.append(f'[{L}] lessons/ 下有 {n}.md，但 toc.json 没列出')

    # 课号连续性
    nums = sorted(int(n) for n in lessons if n.isdigit())
    if nums:
        expected = list(range(1, max(nums) + 1))
        if nums != expected:
            missing = [f'{i:02d}' for i in expected if i not in nums]
            warnings.append(f'[{L}] 课号不连续，缺：{", ".join(missing)}')

    nq = 0
    for n in sorted(lessons):
        nq += check_lesson(L, n, lessons[n], errors, warnings, stats, is_test=False)
    for t in sorted(tests):
        nq += check_lesson(L, t, tests[t], errors, warnings, stats, is_test=True)

    stats['lessons'] += len(lessons)
    stats['tests'] += len(tests)
    stats['questions'] += nq          # 题数要累加，否则 stats 里恒为 0
    return {'lessons': len(lessons), 'tests': len(tests), 'questions': nq}


def check_lesson(L, name, md, errors, warnings, stats, is_test):
    tag = f'[{L}] {name}.md'
    lines = md.count('\n') + 1
    stats['lines'] += lines
    qs = blocks(md)

    # 未闭合的 quiz 块检测
    opens = len(re.findall(r'^```quiz\s*$', md, re.M))
    if opens != len(qs):
        errors.append(f'{tag}: 有 {opens - len(qs)} 个 quiz 块没有闭合（末尾缺 ``` 独占一行）')

    if not qs:
        errors.append(f'{tag}: 一道题都没有')
        return 0

    if lines < 60:
        warnings.append(f'{tag}: 只有 {lines} 行，可能是占位内容')

    if is_test:
        if len(qs) < 5:
            warnings.append(f'{tag}: 章测只有 {len(qs)} 题，建议 8 题')
    else:
        exam = [q for q in qs if truthy(q.get('exam'))]
        if len(exam) != 2:
            errors.append(f'{tag}: 带 exam: true 的题 {len(exam)} 道（应为 2）')
        if len(qs) < 3:
            warnings.append(f'{tag}: 只有 {len(qs)} 道题（建议 3 道：1 随堂 + 2 测验）')

    for q in qs:
        t = (q.get('type') or 'choice').strip()
        if t == 'choice':
            opts = q.get('options') or []
            if not isinstance(opts, list):
                opts = []
            # 多选题的 answer 是逗号分隔的下标列表，不能当单个整数解析 ——
            # 否则 int('0, 1') 抛异常回退成 -1，直接报"越界"，是假错误。
            is_multi = str(q.get('multi') or '').strip().lower() == 'true'
            if len(opts) < 2:
                errors.append(f'{tag}: 选择题只有 {len(opts)} 个选项')
            elif is_multi:
                picks = []
                bad = False
                for part in str(q.get('answer') or '').split(','):
                    part = part.strip()
                    if not part:
                        bad = True
                        continue
                    try:
                        n = int(part)
                    except Exception:
                        bad = True
                        continue
                    if not (0 <= n < len(opts)):
                        bad = True
                    picks.append(n)
                if bad or not picks:
                    errors.append(
                        f'{tag}: 多选题 answer="{q.get("answer")}" 有越界下标（共 {len(opts)} 个选项）')
            else:
                try:
                    ans = int(q.get('answer', -1))
                except Exception:
                    ans = -1
                if not (0 <= ans < len(opts)):
                    errors.append(f'{tag}: 选择题 answer={q.get("answer")} 越界（共 {len(opts)} 个选项）')
            if not str(q.get('q', '')).strip():
                errors.append(f'{tag}: 选择题缺题干 q')
        elif t in ('code', 'function', 'project', 'local', 'js', 'css', 'html'):
            stats['code'] += 1
            if t == 'function':
                fnm = (q.get('func') or '').strip()
                st = q.get('starter', '') or ''
                if fnm and f'def {fnm}' not in st and f'class {fnm}' not in st:
                    errors.append(f'{tag}: func="{fnm}" 在 starter 里找不到定义')
                if not str(q.get('cases') or '').strip():
                    errors.append(f'{tag}: function 题缺 cases')
            if t == 'code' and not (q.get('tests') or []):
                errors.append(f'{tag}: code 题缺 tests')
            if t in ('js', 'css', 'html') and not (q.get('checks') or []):
                warnings.append(f'{tag}: {t} 题没有 checks，无法判分')
            if t == 'local' and not (q.get('checklist') or []):
                warnings.append(f'{tag}: local 题缺 checklist')
            if t == 'project' and not q.get('starter'):
                warnings.append(f'{tag}: project 题缺 starter')
        elif t == 'fill':
            # 填空题：answer 是关键词，可用 | 分隔多个可接受的写法。
            # 不认识这个题型的话，缺 answer 也不会被检查 ——
            # 那样作者发一道没答案的填空题照样收录，读者做了永远判不对。
            ans = str(q.get('answer') or '').strip()
            if not ans:
                errors.append(f'{tag}: 填空题缺 answer')
            if not str(q.get('q') or '').strip():
                errors.append(f'{tag}: 填空题缺题干 q')
        else:
            warnings.append(f'{tag}: 未知题型 "{t}"')
    return len(qs)


# ---------- 代码题实跑（Python 部分） ----------
def run_python_questions(files, report):
    """对 function/code 题做实跑抽检：参考解要能过，starter 原样要被拒。"""
    results = []
    for L in ('zh', 'en'):
        pre = f'content/{L}/'
        for p, txt in sorted(files.items()):
            if not p.startswith(pre + 'lessons/'):
                continue
            for i, q in enumerate(blocks(txt)):
                t = (q.get('type') or '').strip()
                if t != 'function':
                    continue
                fnm = (q.get('func') or '').strip()
                cases = str(q.get('cases') or '')
                if not fnm or not cases.strip():
                    continue
                ok, detail = try_run(fnm, cases, q.get('starter', ''))
                results.append({'file': p, 'idx': i + 1, 'func': fnm,
                                'starter_leaks': ok, 'detail': detail})
    return results


def try_run(fnm, cases, starter):
    """starter 原样提交时，是否会被判为通过？返回 (是否通过, 说明)"""
    ns = {}
    try:
        exec(starter or 'pass', ns)
    except Exception as e:
        return False, f'starter 无法执行：{e}'
    if fnm not in ns:
        return False, f'starter 里没有 {fnm}'
    passed = total = 0
    for ln in cases.split('\n'):
        ln = ln.strip()
        if '->' not in ln:
            continue
        a, e = ln.split('->', 1)
        try:
            args = eval('[' + a.strip() + ']', {'__builtins__': __builtins__})
        except Exception:
            try:
                args = [json.loads(a.strip())]
            except Exception:
                continue
        expect = e.strip()
        try:
            expect_v = eval(expect, {'__builtins__': __builtins__})
        except Exception:
            expect_v = expect.strip('"\'')
        total += 1
        try:
            got = ns[fnm](*args)
        except Exception:
            got = None
        if got == expect_v and type(got) is type(expect_v):
            passed += 1
    if total == 0:
        return False, 'cases 无法解析'
    return passed == total, f'starter 原样通过 {passed}/{total}'


if __name__ == '__main__':
    src = sys.argv[1]
    files = load_from_github(src) if '/' in src and not os.path.isdir(src) else load_from_dir(src)
    rep = validate(files)
    leaks = [r for r in run_python_questions(files, rep) if r['starter_leaks']]
    for r in leaks:
        rep['errors'].append(f"{r['file']}#{r['idx']}: 题目无区分力——初始代码原样就能通过（{r['detail']}）")
    rep['ok'] = not rep['errors']
    print(json.dumps(rep, ensure_ascii=False, indent=1))
