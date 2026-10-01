# AnyLearn 第三方书籍格式规范（al-book v1）

任何人都可以给 AnyLearn 写教材。你只要按这份规范建一个 GitHub 仓库，
AnyLearn 的索引机器人会**自动发现它、自动校验它**，通过后出现在书库里供所有人阅读。

---

## 一、怎么让机器人认出你的仓库（三重标记，缺一不可）

| # | 标记 | 要求 | 作用 |
|---|---|---|---|
| 1 | **仓库名** | 必须以 `al-book-` 开头，例如 `al-book-web-scraping` | 人类可读，一眼看出是本 al 书 |
| 2 | **GitHub topic** | 必须打上 topic `al-book` | 机器人发现你的**唯一入口** |
| 3 | **声明文件** | 仓库根目录必须有 `albook.json`，且含 `"format": "al-book"` | 防止 topic 被误用、防止同名无关仓库被误收 |

**三重标记是为了不误伤**。只靠仓库名会撞车（全世界都可能有 `al-book-demo`）；
只靠 topic 会被无关仓库误打标签混进来。三个都对上，机器人才会停下来读你的内容。

> **topic 是硬性入口，这一项缺了机器人根本扫不到你。**
> 早期版本还会顺带搜 `al-book- in:name`，但 GitHub 的仓库名搜索是模糊匹配，
> 会把 `AliAlQaseerBooks`、`virtual-book-allestimento` 这类毫不相关的仓库全捞进来，
> 既慢又全是噪声。所以现在只认 topic——**记得打**。

>`format` 字段的值必须是**精确字符串** `al-book`。写成 `albook`、`AL-BOOK`、`al_book` 都会被视为无效、
>直接跳过，不会给你报错——所以发现不了自己的书时，**第一件事就是检查这个字段**。

---

## 二、目录结构

一个仓库 = 一本书。路径从 `content/` 开始，**不需要** `books/<id>/` 这一层：

```
al-book-my-book/
├── albook.json              ← 声明文件 + 作者简介 + 书籍介绍（必需）
├── README.md                ← 给人类看的说明（可选，但推荐）
└── content/
    ├── zh/                  ← 中文（至少要有 zh 或 en 中的一种）
    │   ├── toc.json         ← 目录（必需）
    │   └── lessons/
    │       ├── 01.md
    │       ├── 02.md
    │       ├── test-01.md   ← 第 1 章大测验
    │       └── test-02.md
    └── en/                  ← 英文（可选，但强烈推荐）
        ├── toc.json
        └── lessons/
            ├── 01.md
            └── test-01.md
```

**硬性规则：**

- 课号**两位数字**：`01.md` ~ `30.md`，连续不跳号
- 每 **5 课**为一个章节，章末一个 `test-NN.md`（第 1 章 `test-01.md`）
- `toc.json` 里的条目必须和 `lessons/` 里的文件**一一对应**
- 中英文都写时，**两边文件数必须相同**，且题号、题型逐条对齐

---

## 三、`albook.json`（声明文件）

```json
{
  "format": "al-book",
  "version": 1,
  "id": "web-scraping",
  "title": "Python 网络爬虫入门",
  "subtitle": "从 requests 到反爬应对",
  "desc": "面向会 Python 基础语法的学习者。讲清请求、解析、存储与合规边界。",
  "stage": "实战",
  "level": "进阶",
  "langs": ["zh", "en"],
  "tags": ["爬虫", "requests", "实战"],
  "cover": "https://……/cover.png",
  "license": "CC BY-NC 4.0",
  "author": {
    "name": "张三",
    "bio": "十年后端工程师，业余写教程。",
    "url": "https://github.com/zhangsan",
    "avatar": "https://avatars.githubusercontent.com/u/xxxxx"
  },
  "repo": "https://github.com/zhangsan/al-book-web-scraping",
  "chapters": [
    { "n": 1, "title": "第 1 章 · 第一个请求" },
    { "n": 2, "title": "第 2 章 · 解析 HTML" }
  ]
}
```

### 字段说明

| 字段 | 必需 | 说明 |
|---|---|---|
| `format` | ✅ | **必须精确等于 `"al-book"`**，否则整个仓库被忽略 |
| `version` | ✅ | 格式版本，当前为 `1` |
| `id` | ✅ | 书籍唯一标识，只能用 `a-z 0-9 -`，建议和仓库名去掉 `al-book-` 前缀后一致 |
| `title` / `subtitle` / `desc` | ✅ | 书名、副标题、简介 |
| `stage` | ✅ | 分类：基础 / 标准库 / 数据 / 桌面 / 算法 / 工程 / 网页 / 实战 |
| `level` | ✅ | 入门 / 进阶 / 高级 |
| `langs` | ✅ | 支持的语言数组，如 `["zh"]` 或 `["zh","en"]` |
| `author` | ✅ | 至少要有 `name`；`bio`/`url`/`avatar` 推荐填 |
| `license` | ✅ | 开源协议，推荐 `CC BY-NC 4.0` |
| `chapters` | ❌ | 章节标题列表，缺省时机器人按每 5 课一章自动推断 |
| `cover` / `tags` / `repo` | ❌ | 封面图、标签、仓库地址 |

>`id` 冲突时（两本书用了同一个 id），**先被收录的保留**，后来者会被标记为冲突。
>所以起 id 时最好带上你的用户名，例如 `zhangsan-web-scraping`。

---

## 四、`toc.json`（目录）

最简写法——`lessons` 里只放课号：

```json
{
  "book": "web-scraping",
  "chapters": [
    {
      "title": "第 1 章 · 第一个请求",
      "lessons": ["01", "02", "03", "04", "05"],
      "test": "test-01"
    },
    {
      "title": "第 2 章 · 解析 HTML",
      "lessons": ["06", "07", "08", "09", "10"],
      "test": "test-02"
    }
  ]
}
```

`lessons` 里的每一项是**不带 `.md` 的课号**。`test` 是章测文件名（同样不带 `.md`），没有章测就填 `null`。

### 标题和摘要不用手写

这样写**就够了**——阅读器会自动打开每一课的 `NN.md`，取第一行 `# 标题` 当目录标题、
取第一句 `> 引言` 当摘要。所以你只要把课文标题写清楚，目录就是完整的。

如果你想要和课文标题**不一样**的目录标题（比如课文标题很长，目录里想短一点），
可以把某项写成对象：

```json
"lessons": [
  { "id": "01", "title": "为什么要自动化", "summary": "算一笔时间的账" },
  { "id": "02", "title": "遍历目录" },
  "03",
  "04",
  "05"
]
```

同一个 `lessons` 数组里**字符串和对象可以混着写**：给了 `title` 就用你的，没给就自动抓。
`summary` 同理，不写就从课文的 `>` 引言抓。

---

## 五、课文文件（`NN.md`）

```markdown
# 标题

> 一句话引言：这一节解决什么问题

## 小标题

正文。用 ```python 围栏写**能运行**的代码。

## 小结

- 要点

## 随堂练习

```quiz
type: function
q: 写一个函数 is_even(n)，偶数返回 True
func: is_even
starter: |
  def is_even(n):
      return False
cases: |
  2 -> True
  3 -> False
hint: 用 n % 2 == 0
explain: 布尔判断直接 return 回去
```

---

## 本节测验

```quiz
type: choice
exam: true
q: 下面哪个是对的？
options:
- A
- B
answer: 1
explain: 因为……
```
```

**关键区别**：`## 随堂练习` 的题**不带** `exam`，在正文里当场做；
`## 本节测验` 的题**必须带** `exam: true`，只出现在独立测验页，**全对才标记这一课完成**。

### 题型

| 类型 | 怎么判 |
|---|---|
| `choice` | 比对 `answer` 下标 |
| `code` | 真跑代码，用 `tests:` 里的 `assert` 判 |
| `function` | 真调用学生写的函数，`cases:` 逐用例比对返回值 |
| `project` | 不判功能，跑得通 + 清单自评 |
| `local` | 浏览器跑不了（GUI/网络），给「在 VS Code 里打开」+ 清单 |
| `js` / `css` / `html` | 网页书专用，查 DOM 与计算样式 |

---

## 六、机器人会怎么检查你的书

发现后，机器人会跑一遍完整校验。**任何一条「错误」都会导致你的书不被收录**，
「警告」则只是提示，不影响收录。

### 会判为「错误」的

1. `albook.json` 缺失、JSON 解析失败、`format` 不是 `al-book`
2. 必需字段缺失（`id`/`title`/`desc`/`stage`/`level`/`langs`/`author`/`license`）
3. `id` 含非法字符（只允许 `a-z 0-9 -`）
4. `langs` 里声明的语言在 `content/` 下找不到对应目录
5. `toc.json` 缺失或解析失败
6. toc 里列出的课号在 `lessons/` 下**找不到文件**
7. `lessons/` 下有文件但 toc **没列出**（孤儿文件）
8. 课文里**一道题都没有**
9. 选择题 `answer` 下标越界，或 `options` 少于 2 个
10. `function` 题的 `func` 函数名在 `starter` 里**找不到定义**
11. quiz 块**没有闭合**（末尾缺 ``` 独占一行）——这会让整段脚本读不出来
12. 中英文都写了，但**两边题数不一致**
13. **代码题的参考答案跑不通**，或**初始代码原样就能通过**（题目没有区分力）

### 会判为「警告」的

- 课号不连续（跳号）
- 某课只有 1 道题
- 章节课数不是 5 的倍数
- 缺章测
- 课文行数过少（少于 60 行，可能是占位内容）

### 第 13 条最容易踩

我们**会真的跑一遍你的每一道代码题**：

- 写出参考解跑一遍，确认能过
- 再写一个故意写错的版本，确认**会被拒绝**

只跑参考解只能证明"题目能过"，证明不了"题目有区分力"。
如果初始代码（starter）原样提交就能通过，这道题就是废的——学生什么都不做也能得分。

---

## 七、提交之后

1. 机器人定期扫 `topic:al-book`，发现新仓库
2. 跑校验，生成报告
3. 通过的书进入 **al-docs 索引页**，显示书名、作者、课程数、校验状态
4. 读者在 AnyLearn 里挑选并阅读

**你的书没出现？** 按顺序自查：

1. topic 打了吗？必须是 `al-book`，不是 `albook` 或 `al-book-`
2. `albook.json` 在**仓库根目录**吗（不是 `content/` 里）？
3. `format` 的值是**精确的** `al-book` 吗？
4. 跑一遍上面的校验清单，看有没有「错误」级别的条目

---

## 八、最小可用示例

只要这三个文件就能被收录：

```
al-book-hello/
├── albook.json
└── content/
    └── zh/
        ├── toc.json
        └── lessons/
            ├── 01.md
            └── test-01.md
```

`albook.json` 最小内容：

```json
{
  "format": "al-book",
  "version": 1,
  "id": "hello",
  "title": "我的第一本书",
  "subtitle": "试试看",
  "desc": "一本书的最小骨架。",
  "stage": "基础",
  "level": "入门",
  "langs": ["zh"],
  "license": "CC BY-NC 4.0",
  "author": { "name": "我" }
}
```
