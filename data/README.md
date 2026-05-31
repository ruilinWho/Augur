# data/ —— 运行时状态（被 git 忽略）

**这里除本 README 外一概不入库。** 全是运行时生成/抓取、可丢弃可重建的数据。
在 git 里**永不**把 `data/` 当作真相来源。（CLAUDE.md §3、§11）

```
data/
├── cache/   Parquet 行情缓存（cache/ohlcv/<MARKET>/<CODE>/<interval>.parquet）
├── db/      SQLite：自选分区、设置、新闻、日报、报告、LLM 用量
└── logs/    运行时日志
```

这些目录由后端首次运行时创建。`.gitignore` 规则是：

```
data/*
!data/README.md
```

——所以目录 + 本说明能在 clone 后留存，但任何运行时产物（或密钥）都不会混进 git。
打包后（Phase 2）这里会移到 `~/Library/Application Support/Augur/`。
