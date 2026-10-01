"""
给 GitHub Actions 用的 gh.py 替代实现：只读 GITHUB_TOKEN 环境变量。
本地跑 discover.py 时用的是仓库外的 gh.py（含多账号），Actions 里没有那份文件，
所以这里提供一个只依赖官方 token 的最小实现。
"""
import os, json, urllib.request, urllib.error, base64

TOKEN = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN') or ''
API = 'https://api.github.com'
COOL = FENG = None


def hdr(tok):
    tok = tok or TOKEN
    return {'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'al-docs-bot'}


def req(method, path, payload=None, tok=None, raw=False):
    url = path if path.startswith('http') else API + path
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, method=method, headers=hdr(tok), data=data)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            b = resp.read()
            return b if raw else (json.loads(b) if b else {})
    except urllib.error.HTTPError as e:
        b = e.read()
        try:
            return {'__err__': True, 'status': e.code, **json.loads(b)}
        except Exception:
            return {'__err__': True, 'status': e.code, 'message': b[:300].decode('utf-8', 'ignore')}
    except Exception as e:
        return {'__err__': True, 'status': -1, 'message': str(e)}


def tree(owner, repo, branch='main', tok=None):
    d = req('GET', f'/repos/{owner}/{repo}/git/trees/{branch}?recursive=1', tok=tok)
    return d.get('tree', [])


def getfile(owner, repo, path, branch='main', tok=None):
    d = req('GET', f'/repos/{owner}/{repo}/contents/{path}?ref={branch}', tok=tok)
    if d.get('__err__'):
        return None
    try:
        return base64.b64decode(d['content']).decode('utf-8')
    except Exception:
        return None
