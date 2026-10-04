/**
 * 浏览器端书籍校验 —— 与 tools/validate_book.py 同一套规则。
 *
 * 为什么要在浏览器里再实现一遍：
 *   al-docs 是纯静态站，没有后端。作者贴个仓库名想立刻知道"我这本能过吗"，
 *   如果只能等 Actions 跑一轮，反馈要等一两分钟，改一次等一次没法用。
 *   公开仓库用未认证 API 就能读（60 次/小时，校验一本够用），即时出结果。
 *
 * 代价是规则要维护两份。所以两边的错误文案保持一致，
 *   并且这里的输出结构和 Python 版一致，便于对照排查。
 */
const BookCheck = (() => {

  const FORMAT_KEY = 'al-book';
  const REQUIRED = ['id','title','subtitle','desc','stage','level','langs','author','license'];
  const ID_RE = /^[a-z0-9][a-z0-9-]*$/;

  /**
   * 书的种类。
   *
   * 为什么要有这个：最初只想着"教材"，于是强制每课 1 随堂 + 2 测验、
   * 一道题都没有就报错。但有人想用这套格式写小说、写笔记 ——
   * 那些东西本来就没有题，硬卡着就写不了。
   *
   *   textbook  教材（默认）：要求题目数量，中英题数要一致
   *   novel     小说：不要求题目
   *   notes     笔记 / 随笔：不要求题目
   *   other     其它
   *
   * 非教材只是"不强制数量"，题目本身写错了照样报错 ——
   * 有题就得是能判分的题。
   */
  const KINDS = ['textbook', 'novel', 'notes', 'other'];
  const KINDS_ZH = {
    textbook: '教材', novel: '小说', notes: '笔记 / 随笔', other: '其它',
  };
  const isTextbook = kind => String(kind || 'textbook').trim() === 'textbook';

  /* ---- quiz 块解析：与 validate.py 一致的「结束围栏必须独占一行且顶格」 ---- */
  function blocks(md) {
    const out = [];
    const re = /```quiz\n([\s\S]*?)^```\s*$/gm;
    let m;
    while ((m = re.exec(md)) !== null) out.push(parseQuiz(m[1]));
    return out;
  }

  function parseQuiz(src) {
    const data = {};
    const lines = src.split('\n');
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      const m = line.match(/^(\w+)\s*:\s*(.*)$/);
      if (!m) { i++; continue; }
      let [key, val] = [m[1], m[2]];
      if (val === '|' || val === '>') {
        const buf = []; i++;
        while (i < lines.length && (/^\s{2,}/.test(lines[i]) || lines[i].trim() === '')) {
          if (lines[i].trim() !== '') buf.push(lines[i].replace(/^\s{2}/, ''));
          i++;
        }
        data[key] = buf.join('\n'); continue;
      }
      if (val === '') {
        const buf = []; i++;
        while (i < lines.length && /^\s*-\s+/.test(lines[i])) {
          buf.push(lines[i].replace(/^\s*-\s+/, '').trim()); i++;
        }
        data[key] = buf; continue;
      }
      data[key] = val.trim(); i++;
    }
    return data;
  }

  const truthy = v => String(v || '').trim().toLowerCase() === 'true';

  function checkLesson(name, md, isTest, lang, errors, warnings, stats, strict) {
    const tag = `[${lang}] ${name}.md`;
    const lines = md.split('\n').length;
    stats.lines += lines;

    const opens = (md.match(/^```quiz\s*$/gm) || []).length;
    const qs = blocks(md);
    if (opens !== qs.length) {
      errors.push(`${tag}: 有 ${opens - qs.length} 个 quiz 块没有闭合（末尾缺 \`\`\` 独占一行）`);
    }
    // 占位判断不能只看行数：60 行的门槛对"从现成文章导入"是误报 ——
    // 一篇真实文章每节 6 行很正常，一次导入能刷出十几条警告，全是噪音，
    // 用户会以为自己做错了。行数少但字多的显然是正经内容。
    // 真正的占位是"一句话"级别（几十字），不是"一小节"（几十行）。
    // 阈值定在 80 字：少于这个数基本就是"待补充"，多于此的短小节是正经内容。
    const chars = md.replace(/\s/g, '').length;
    if (chars < 80) {
      warnings.push(`${tag}: 只有 ${chars} 字，可能是占位内容`);
    }

    // 非教材：题目是可选的。没题就过，有题就照常校验合法性。
    if (!qs.length) return strict ? (errors.push(`${tag}: 一道题都没有`), 0) : 0;

    if (strict) {
      if (isTest) {
        if (qs.length < 5) warnings.push(`${tag}: 章测只有 ${qs.length} 题，建议 8 题`);
      } else {
        const exam = qs.filter(q => truthy(q.exam));
        if (exam.length !== 2) errors.push(`${tag}: 带 exam: true 的题 ${exam.length} 道（应为 2）`);
        if (qs.length < 3) warnings.push(`${tag}: 只有 ${qs.length} 道题（建议 3 道：1 随堂 + 2 测验）`);
      }
    }

    for (const q of qs) {
      const t = String(q.type || 'choice').trim();
      if (t === 'choice') {
        const opts = Array.isArray(q.options) ? q.options : [];
        const ans = parseInt(q.answer, 10);
        if (opts.length < 2) errors.push(`${tag}: 选择题只有 ${opts.length} 个选项`);
        else if (!(ans >= 0 && ans < opts.length)) errors.push(`${tag}: 选择题 answer=${q.answer} 越界（共 ${opts.length} 个选项）`);
        if (!String(q.q || '').trim()) errors.push(`${tag}: 选择题缺题干 q`);
        // 多选题的 answer 是逗号分隔的下标列表，逐个检查越界
        if (String(q.multi || '').toLowerCase() === 'true') {
          const picks = String(q.answer ?? '').split(',').map(x => parseInt(x.trim(), 10));
          if (!picks.length || picks.some(n => !(n >= 0 && n < opts.length))) {
            errors.push(`${tag}: 多选题 answer="${q.answer}" 有越界下标（共 ${opts.length} 个选项）`);
          }
        }
      } else if (t === 'fill') {
        // 填空题：answer 是关键词，可用 | 分隔多个可接受写法
        if (!String(q.answer || '').trim()) errors.push(`${tag}: 填空题缺 answer`);
        if (!String(q.q || '').trim()) errors.push(`${tag}: 填空题缺题干 q`);
      } else if (['code','function','project','local','js','css','html'].includes(t)) {
        stats.code++;
        if (t === 'function') {
          const fnm = String(q.func || '').trim();
          const st = q.starter || '';
          if (fnm && !st.includes('def ' + fnm) && !st.includes('class ' + fnm)) {
            errors.push(`${tag}: func="${fnm}" 在 starter 里找不到定义`);
          }
          if (!String(q.cases || '').trim()) { errors.push(`${tag}: function 题缺 cases`); }
          else { const bad = badCaseLine(q.cases); if (bad) {
            // 参数只按逗号分隔。写空格的话整段会变成一个参数，
            // 运行时报"缺少参数"而不是告诉你写法错了 —— 所以在这里提前拦。
            errors.push(`${tag}: cases 里 "${bad}" 的参数要用逗号分隔（如 1, 2 -> 3）`);
          } }
        }
        if (t === 'code' && !(q.tests || []).length) errors.push(`${tag}: code 题缺 tests`);
        if (['js','css','html'].includes(t) && !(q.checks || []).length) {
          warnings.push(`${tag}: ${t} 题没有 checks，无法判分`);
        }
        if (t === 'local' && !(q.checklist || []).length) warnings.push(`${tag}: local 题缺 checklist`);
        if (t === 'project' && !q.starter) warnings.push(`${tag}: project 题缺 starter`);
      } else {
        warnings.push(`${tag}: 未知题型 "${t}"`);
      }
    }
    return qs.length;
  }

  /** files: { path: text }，只含 albook.json / README.md / content/** */
  function validate(files) {
    const errors = [], warnings = [];
    const stats = { lessons: 0, tests: 0, questions: 0, code: 0, lines: 0 };

    const raw = files['albook.json'];
    if (raw == null) {
      return { ok: false, errors: ['albook.json 缺失：仓库根目录必须有这个文件'], warnings, stats };
    }
    let meta;
    try { meta = JSON.parse(raw); }
    catch (e) { return { ok: false, errors: [`albook.json 不是合法 JSON：${e.message}`], warnings, stats }; }

    const fmt = String(meta.format || '').trim();
    if (fmt !== FORMAT_KEY) {
      return { ok: false, errors: [`format 字段必须是精确字符串 "${FORMAT_KEY}"，当前是 "${fmt}"`], warnings, stats };
    }

    for (const k of REQUIRED) if (!meta[k]) errors.push(`albook.json 缺必需字段：${k}`);

    // kind 决定要不要卡题目数量。未知值按宽松处理：
    // 宁可放过一本合法的另类书，也别因为拼错就拦住一本正经教材。
    const kind = String(meta.kind || 'textbook').trim();
    const strict = isTextbook(kind);
    if (kind && !KINDS.includes(kind)) {
      warnings.push(`kind "${kind}" 不在推荐取值里（${KINDS.join(' / ')}），已按"不要求题目"处理`);
    }

    const bid = String(meta.id || '').trim();
    if (bid && !ID_RE.test(bid)) {
      errors.push(`id "${bid}" 含非法字符：只允许小写字母、数字和连字符`);
    }

    let langs = meta.langs;
    if (!Array.isArray(langs) || !langs.length) {
      errors.push('langs 必须是非空数组，例如 ["zh"] 或 ["zh","en"]');
      langs = [];
    } else {
      for (const L of langs) if (!['zh','en'].includes(L)) errors.push(`langs 含未知语言 "${L}"（只支持 zh / en）`);
    }

    const a = meta.author;
    if (a != null && (typeof a !== 'object' || !String(a.name || '').trim())) {
      errors.push('author 必须是对象且至少含 name');
    }

    const present = ['zh','en'].filter(L =>
      Object.keys(files).some(p => p.startsWith(`content/${L}/`)));

    for (const L of langs) {
      if (!present.includes(L)) errors.push(`langs 声明了 "${L}"，但 content/${L}/ 下没有任何文件`);
    }
    if (!present.length) errors.push('content/ 下找不到任何 zh/ 或 en/ 目录');

    const perLang = {};
    for (const L of present) {
      const pre = `content/${L}/`;
      let toc = null;
      const traw = files[pre + 'toc.json'];
      if (traw == null) errors.push(`[${L}] 缺 content/${L}/toc.json`);
      else {
        try { toc = JSON.parse(traw); }
        catch (e) { errors.push(`[${L}] toc.json 不是合法 JSON：${e.message}`); }
      }

      const lessons = {}, tests = {};
      for (const [p, txt] of Object.entries(files)) {
        if (!p.startsWith(pre + 'lessons/')) continue;
        const fn = p.slice((pre + 'lessons/').length);
        if (fn.startsWith('test-')) tests[fn.replace(/\.md$/, '')] = txt;
        else if (/^\d{2}\.md$/.test(fn)) lessons[fn.replace(/\.md$/, '')] = txt;
      }

      let declared = [], declaredTests = [];
      if (toc) {
        for (const ch of (toc.chapters || [])) {
          for (const it of (ch.lessons || [])) declared.push(String(it.id || it));
          if (ch.test) declaredTests.push(String(ch.test));
        }
      } else if (Object.keys(lessons).length) {
        declared = Object.keys(lessons).sort();
        warnings.push(`[${L}] toc.json 不可用，按 lessons/ 下的文件名推断目录`);
      }

      for (const n of declared) {
        if (!(n in lessons)) errors.push(`[${L}] toc 声明了 ${n}.md，但 lessons/ 下找不到`);
      }
      for (const n of Object.keys(lessons).sort()) {
        if (!declared.includes(n)) errors.push(`[${L}] lessons/ 下有 ${n}.md，但 toc.json 没列出`);
      }

      const nums = Object.keys(lessons).filter(n => /^\d+$/.test(n)).map(Number).sort((a,b)=>a-b);
      if (nums.length) {
        const miss = [];
        for (let i = 1; i <= nums[nums.length-1]; i++) if (!nums.includes(i)) miss.push(String(i).padStart(2,'0'));
        if (miss.length) warnings.push(`[${L}] 课号不连续，缺：${miss.join(', ')}`);
      }

      let nq = 0;
      for (const n of Object.keys(lessons).sort()) nq += checkLesson(n, lessons[n], false, L, errors, warnings, stats, strict);
      for (const t of Object.keys(tests).sort()) nq += checkLesson(t, tests[t], true, L, errors, warnings, stats, strict);

      stats.lessons += Object.keys(lessons).length;
      stats.tests += Object.keys(tests).length;
      stats.questions += nq;
      perLang[L] = { lessons: Object.keys(lessons).length, tests: Object.keys(tests).length, questions: nq };
    }

    if (perLang.zh && perLang.en) {
      // 只有教材才要求中英题数一致：小说/笔记先写完一边很正常
      if (strict && perLang.zh.questions !== perLang.en.questions) {
        errors.push(`中英题数不一致：中文 ${perLang.zh.questions} 道，英文 ${perLang.en.questions} 道`);
      }
      if (perLang.zh.lessons !== perLang.en.lessons) {
        errors.push(`中英课文数不一致：中文 ${perLang.zh.lessons} 课，英文 ${perLang.en.lessons} 课`);
      }
    }

    return {
      ok: errors.length === 0,
      errors, warnings,
      stats: { ...stats, languages: present.length },
      perLang, meta, kind, strict,
    };
  }

  /**
   * 找出"参数段有空格却没有逗号"的用例行。
   *
   * 什么情况算可疑：参数段里含空格，但整个参数段既不含逗号，
   * 也没有被引号/括号包起来 —— 那基本就是想写多个参数却用了空格。
   *
   * 反过来这些要放过：
   *   "hello world" -> 5     单参数字符串，里面本来就有空格
   *   [1, 2, 3] -> 6         列表参数（含逗号）
   *   -> 3                   无参
   */
  function badCaseLine(cases) {
    const lines = Array.isArray(cases) ? cases
      : String(cases || '').split('\n');
    for (const raw of lines) {
      const line = String(raw).trim();
      if (!line || !line.includes('->')) continue;
      let argStr = line.slice(0, line.indexOf('->')).trim();
      if (!argStr) continue;                                  // 无参
      const m = /^\*(\d+)\s*(?:,\s*(.*))?$/.exec(argStr);   // *N 前缀
      if (m) argStr = (m[2] || '').trim();
      if (!argStr) continue;
      if (!/\s/.test(argStr)) continue;                       // 没有空格，正常
      if (argStr.includes(',')) continue;                      // 有逗号，正常写法
      const ch = argStr[0];
      if ((ch === '"' || ch === "'") && argStr.length > 1 && argStr.endsWith(ch)) continue;
      if (ch === '[' || ch === '(' || ch === '{') continue;
      return line;
    }
    return null;
  }

  return { validate, blocks, badCaseLine, KINDS, KINDS_ZH, isTextbook };
})();
