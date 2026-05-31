# resources/ —— 入库的静态资产（版本控制）

这里的一切都是**你/开发者亲手编写的输入**，**纳入 git 版本控制**。
与 `../data/` 相对——那里是仅运行时、被 git 忽略的。（CLAUDE.md §3）

```
resources/
├── fonts/      自带字体（免费的 Tiempos/Styrene 替代，如 Newsreader、Inter）
├── prompts/    LLM 提示词模板（要版本化！）—— 按名加载，不在代码里内联
└── sources/    新闻信源注册表（YAML）：要摄取的精选全球顶级源
```

## 规则

- **提示词在这里版本化**，不嵌进 Python——这样提示词改动是可审阅的 diff。
- **信源注册表**（`sources/*.yaml`）是增删/精选新闻源的唯一入口。
- 大二进制要克制；字体可以，别往这倒几 MB 的数据集（那是 `data/`）。
