# al-docs · AnyLearn 第三方书籍索引

任何人都可以给 [AnyLearn](https://cool-zimo.github.io/al/) 写教材。
这里是**第三方书籍的格式规范、自动校验器和索引站**。

- 📖 **[格式规范 SPEC.md](SPEC.md)** —— 想投稿，从这里开始
- 🌐 **[索引页](https://cool-zimo.github.io/al-docs/)** —— 看看已收录了哪些书
- 🔍 `tools/validate_book.py` —— 校验器，本地跑一遍就知道能不能过
- 🤖 `tools/discover.py` —— 发现器，扫 GitHub 找新书并更新索引

---

## 30 秒上手

1. 建仓库，名字以 `al-book-` 开头，打 topic `al-book`
2. 根目录放 `albook.json`，含 `"format": "al-book"`
3. 内容放 `content/{zh,en}/lessons/NN.md` + `content/{zh,en}/toc.json`
4. 等机器人扫（每 6 小时一次），通过后自动出现

完整要求见 [SPEC.md](SPEC.md)。

---

## 为什么是三重标记

机器人认一本书要同时满足：

| 标记 | 例子 |
|---|---|
| 仓库名前缀 | `al-book-xxx` |
| GitHub topic | `al-book`（**缺了扫不到**）|
| `albook.json` 里的 `format` | 精确等于 `al-book` |

只靠仓库名会撞车（全世界都可能有 `al-book-demo`）；
只靠 topic 会被误打标签的无关仓库混进来。三个都对上，机器人才会停下来读内容。

---

## 本地自检

投稿前先自己跑一遍，省得等 6 小时：

```bash
# 校验本地目录
python3 tools/validate_book.py /path/to/al-book-my-book

# 或者直接从 GitHub 读
python3 tools/validate_book.py owner/al-book-my-book
```

输出 `ok: true` 且 `errors` 为空，就可以提交了。

> 校验器需要 `gh.py`（含 GitHub token）才能从远端读。
> 只校验本地目录不需要任何凭据。

---

## 机器人怎么跑

`tools/discover.py` 每 6 小时由 GitHub Actions 执行一次：

1. 搜 `topic:al-book` 和 `al-book- in:name`
2. 对每个候选读 `albook.json`，三重标记全对上才继续
3. 跑完整校验（含**代码题实跑**）
4. 写出 `registry.json` 和 `reports/<owner>__<repo>.json`
5. 有变化就自动提交

AnyLearn 主站启动时读 `registry.json`，把通过校验的书并入书单。
**索引站挂了也不影响官方书**——读不到就静默跳过。

---

## 收录意味着什么

只意味着**格式合规**：题目能被判分、目录能打开、中英文对齐。

不意味着内容质量被背书。第三方教材的内容责任归原作者，
主站会在卡片上标出「第三方」和作者名。

---

## 校验会查什么

**错误（会导致不收录）**：声明文件不合规、`format` 不对、必需字段缺失、
`id` 含非法字符、语言目录对不上、toc 与实际文件不符、**课文里一道题都没有**、
选择题 `answer` 越界、`function` 题的函数名在 starter 里找不到、quiz 块没闭合、
中英题数不一致、**代码题初始代码原样就能通过**（题目没区分力）。

**警告（不影响收录）**：课号跳号、某课只有 1 道题、缺章测、课文少于 60 行。

其中最容易被忽略的是最后一条错误：我们会**真的跑一遍你的每一道题**，
既跑参考解确认能过，也跑一个故意写错的版本确认会被拒绝。
只跑参考解只能证明"题目能过"，证明不了"题目有区分力"。
