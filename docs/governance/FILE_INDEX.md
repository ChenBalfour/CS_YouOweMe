# 文件与目录说明

自动生成，目录版本 layout-1.0，代码 0.3.3（本地未发布）。完整 SHA-256 见 [机器清单](FILE_CATALOG.json)。私有逐项清单只在 data/local/manifests/workspace-layout-1.0.json；Git 内部对象由 Git 管理。生成清单使用固定目录版本，不计算自身哈希以避免循环。

## 目录

| 路径 | 用途 | 内容版本（摘要） |
| --- | --- | --- |
| [.](../..) | 项目根及 Git/Python 所需入口元数据 | sha256:6354a8eea184 |
| [.github](../../.github) | GitHub 工具约定的根目录配置 | sha256:b04d86b4e64b |
| [.github/workflows](../../.github/workflows) | 既有自动检查配置 | sha256:b04d86b4e64b |
| [data](../../data) | 来源数据及其伴随元数据 | sha256:f76946d0c54e |
| [data/samples](../../data/samples) | 已公开、冻结待复审的旧匿名样本 | sha256:644f35f0c47c |
| [data/samples/pilot_20261011](../../data/samples/pilot_20261011) | 旧匿名样本批次及原始/表/报告分组 | sha256:644f35f0c47c |
| [data/samples/pilot_20261011/raw](../../data/samples/pilot_20261011/raw) | 旧匿名样本批次及原始/表/报告分组 | sha256:be9fba468537 |
| [data/samples/pilot_20261011/reports](../../data/samples/pilot_20261011/reports) | 旧匿名样本批次及原始/表/报告分组 | sha256:67309b9a13e4 |
| [data/samples/pilot_20261011/tables](../../data/samples/pilot_20261011/tables) | 旧匿名样本批次及原始/表/报告分组 | sha256:d04bb394675d |
| [docs](../../docs) | 计划、制度、使用说明和交接记录 | sha256:edc6b15f0db4 |
| [docs/data](../../docs/data) | 来源、schema 与字段说明 | sha256:503ef6fa866d |
| [docs/governance](../../docs/governance) | 管理、阶段、资产登记与版本索引 | sha256:681b31fd8ef6 |
| [docs/releases](../../docs/releases) | 历史发布与本地版本变更说明 | sha256:113008d65fae |
| [docs/research](../../docs/research) | 唯一主计划与旧研究参考 | sha256:bfe2899f6066 |
| [docs/usage](../../docs/usage) | 旧实现使用参考，非执行授权 | sha256:8142c8c9e0c5 |
| [scripts](../../scripts) | 所有可执行代码及其工程配套 | sha256:6f2aeae6cdc0 |
| [scripts/config](../../scripts/config) | 脚本配置、空白模板与受保护本地凭证 | sha256:e3194c4b19c9 |
| [scripts/hooks](../../scripts/hooks) | 本地 Git 凭证检查 hooks | sha256:89d7eda41c4a |
| [scripts/sql](../../scripts/sql) | 旧历史库只读诊断查询 | sha256:78d833bce86b |
| [scripts/src](../../scripts/src) | Python 包源码 | sha256:6e49eca2b771 |
| [scripts/src/cs_youoweme](../../scripts/src/cs_youoweme) | 旧技术实现，可按对应用途审查复用 | sha256:6e49eca2b771 |
| [scripts/src/cs_youoweme/collectors](../../scripts/src/cs_youoweme/collectors) | 旧公开页面、官方和匿名接口采集机制 | sha256:76b5897b7757 |
| [scripts/src/cs_youoweme/history](../../scripts/src/cs_youoweme/history) | 旧目录、分页任务、SQLite、查询和候选机制 | sha256:233d93cbf954 |
| [scripts/tests](../../scripts/tests) | 离线与合成回归测试 | sha256:b13c5469a8c0 |

## 文件

| 路径 | 用途 | 内容版本（摘要） |
| --- | --- | --- |
| [.gitattributes](../../.gitattributes) | 跨平台文本换行规则 | sha256:8886e081ad1d |
| [.github/workflows/ci.yml](../../.github/workflows/ci.yml) | 既有远程离线检查工作流，根目录位置由 GitHub 约定 | sha256:dfe66c8ce281 |
| [.gitignore](../../.gitignore) | 私有数据、文档、凭证与生成缓存的 Git 排除规则 | sha256:3e41120a23af |
| [AGENTS.md](../../AGENTS.md) | 协作者的执行、阶段、凭证及发布约束 | sha256:3c41ef206cc1 |
| [LICENSE](../../LICENSE) | 原创代码与文档的 MIT 授权 | sha256:9ccc1508d876 |
| [README.md](../../README.md) | 项目入口、当前状态与三类目录索引 | sha256:e35fa7337638 |
| [data/README.md](../../data/README.md) | 私有数据与已公开冻结样本的生命周期说明 | sha256:55be20c980a1 |
| [data/samples/pilot_20261011/raw/item_001.nuxt.json](../../data/samples/pilot_20261011/raw/item_001.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:1557dc48382f |
| [data/samples/pilot_20261011/raw/item_002.nuxt.json](../../data/samples/pilot_20261011/raw/item_002.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:1c5884b75e48 |
| [data/samples/pilot_20261011/raw/item_003.nuxt.json](../../data/samples/pilot_20261011/raw/item_003.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:2b78a484076d |
| [data/samples/pilot_20261011/raw/item_004.nuxt.json](../../data/samples/pilot_20261011/raw/item_004.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:4cb976acc8f6 |
| [data/samples/pilot_20261011/raw/item_005.nuxt.json](../../data/samples/pilot_20261011/raw/item_005.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:ad5f1b331c16 |
| [data/samples/pilot_20261011/raw/item_006.nuxt.json](../../data/samples/pilot_20261011/raw/item_006.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:5870242700f1 |
| [data/samples/pilot_20261011/raw/item_007.nuxt.json](../../data/samples/pilot_20261011/raw/item_007.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:3197382574df |
| [data/samples/pilot_20261011/raw/item_008.nuxt.json](../../data/samples/pilot_20261011/raw/item_008.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:4fe027323006 |
| [data/samples/pilot_20261011/raw/item_009.nuxt.json](../../data/samples/pilot_20261011/raw/item_009.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:8cef1346c10d |
| [data/samples/pilot_20261011/raw/item_010.nuxt.json](../../data/samples/pilot_20261011/raw/item_010.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:0977af2def5b |
| [data/samples/pilot_20261011/raw/item_011.nuxt.json](../../data/samples/pilot_20261011/raw/item_011.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:8e25106e1d12 |
| [data/samples/pilot_20261011/raw/item_012.nuxt.json](../../data/samples/pilot_20261011/raw/item_012.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:85733eec5e3e |
| [data/samples/pilot_20261011/raw/item_013.nuxt.json](../../data/samples/pilot_20261011/raw/item_013.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:8267cf7c1f6a |
| [data/samples/pilot_20261011/raw/item_014.nuxt.json](../../data/samples/pilot_20261011/raw/item_014.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:107e63bbcc9d |
| [data/samples/pilot_20261011/raw/item_015.nuxt.json](../../data/samples/pilot_20261011/raw/item_015.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:be1a14705725 |
| [data/samples/pilot_20261011/raw/item_016.nuxt.json](../../data/samples/pilot_20261011/raw/item_016.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:f562062ec089 |
| [data/samples/pilot_20261011/raw/item_017.nuxt.json](../../data/samples/pilot_20261011/raw/item_017.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:81f7ae935d34 |
| [data/samples/pilot_20261011/raw/item_018.nuxt.json](../../data/samples/pilot_20261011/raw/item_018.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:2a7e17a2a13a |
| [data/samples/pilot_20261011/raw/item_019.nuxt.json](../../data/samples/pilot_20261011/raw/item_019.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:23c802e6a70a |
| [data/samples/pilot_20261011/raw/item_020.nuxt.json](../../data/samples/pilot_20261011/raw/item_020.nuxt.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:598b88f2d9a9 |
| [data/samples/pilot_20261011/reports/manifest.json](../../data/samples/pilot_20261011/reports/manifest.json) | 旧匿名公开样本的来源响应或来源清单，冻结待 UU 用途复审 | sha256:ac75c93e6113 |
| [data/samples/pilot_20261011/reports/quality_report.md](../../data/samples/pilot_20261011/reports/quality_report.md) | 旧匿名公开样本的质量说明，冻结待 UU 用途复审 | sha256:713a2111b221 |
| [data/samples/pilot_20261011/tables/items.csv](../../data/samples/pilot_20261011/tables/items.csv) | 旧匿名公开样本的派生表，冻结待 UU 用途复审 | sha256:a429c153662a |
| [data/samples/pilot_20261011/tables/quotes.csv](../../data/samples/pilot_20261011/tables/quotes.csv) | 旧匿名公开样本的派生表，冻结待 UU 用途复审 | sha256:bb3d0815d6e6 |
| [data/samples/pilot_20261011/tables/related_variants.csv](../../data/samples/pilot_20261011/tables/related_variants.csv) | 旧匿名公开样本的派生表，冻结待 UU 用途复审 | sha256:4db527f3b702 |
| [docs/README.md](../../docs/README.md) | 当前计划、制度、历史参考和整理说明索引 | sha256:37cc7a16042d |
| [docs/data/DATA_DICTIONARY.md](../../docs/data/DATA_DICTIONARY.md) | 旧公开快照表的字段字典 | sha256:f0589a84da9c |
| [docs/data/DATA_SOURCES.md](../../docs/data/DATA_SOURCES.md) | 旧来源、采集证据及口径限制 | sha256:c81a42660293 |
| [docs/data/HISTORY_SCHEMA.md](../../docs/data/HISTORY_SCHEMA.md) | 旧历史库 schema v2、时间与字段口径 | sha256:62af74eaff65 |
| [docs/governance/ASSET_REGISTER.md](../../docs/governance/ASSET_REGISTER.md) | 旧资产保留依据及按用途准入状态 | sha256:dd3b26e93c5c |
| [docs/governance/CONTRIBUTING.md](../../docs/governance/CONTRIBUTING.md) | 本地工程修改与检查方法 | sha256:638174a11fda |
| [docs/governance/FILE_CATALOG.json](../../docs/governance/FILE_CATALOG.json) | 公开文件及目录的用途、版本和内容哈希索引 | layout-1.0.catalog |
| [docs/governance/FILE_INDEX.md](../../docs/governance/FILE_INDEX.md) | 逐文件与逐目录用途和内容版本的可读索引，由 manage_assets 生成 | layout-1.0.catalog |
| [docs/governance/FILE_MANAGEMENT.md](../../docs/governance/FILE_MANAGEMENT.md) | 文件布局、资产生命周期、版本、迁移及发布制度 | sha256:92913b70e675 |
| [docs/governance/HANDOFF.md](../../docs/governance/HANDOFF.md) | 人类与 agent 交接，以及本地与远程版本差异 | sha256:581b99df0ffb |
| [docs/governance/ORGANIZATION.md](../../docs/governance/ORGANIZATION.md) | layout-1.0 整理结果、迁移、清理及恢复方法 | sha256:08073c10b260 |
| [docs/governance/SECURITY.md](../../docs/governance/SECURITY.md) | 凭证隔离与安全问题处理说明 | sha256:1e28de94832a |
| [docs/governance/STATE.md](../../docs/governance/STATE.md) | 当前阶段、版本和停止点 | sha256:472fa014d5f8 |
| [docs/releases/CHANGELOG.md](../../docs/releases/CHANGELOG.md) | 代码历史变更及未发布本地版本说明 | sha256:42e9996abed1 |
| [docs/releases/v0.1.0.md](../../docs/releases/v0.1.0.md) | v0.1.0 已发布版本的历史说明 | sha256:135b86703901 |
| [docs/releases/v0.2.0.md](../../docs/releases/v0.2.0.md) | v0.2.0 已发布版本的历史说明 | sha256:002370597842 |
| [docs/releases/v0.3.0.md](../../docs/releases/v0.3.0.md) | v0.3.0 已发布版本的历史说明 | sha256:ac1f97086ec2 |
| [docs/research/PLAN.md](../../docs/research/PLAN.md) | 唯一研究主计划，当前版本见文档头 | sha256:96e840398cba |
| [docs/research/PROGRESS_20261013.md](../../docs/research/PROGRESS_20261013.md) | 2026-10-13 阶段总结、相对早期的改动、整体规划与今晚停止点 | sha256:2740650940c4 |
| [docs/research/SELECTION_PLAN.md](../../docs/research/SELECTION_PLAN.md) | P02 选品计划、事先固定的范围预算及身份纠正修订依据 | sha256:9c0fb3ffe4f6 |
| [docs/research/SELECTION_REPORT.md](../../docs/research/SELECTION_REPORT.md) | P02 主力、候补、排除与观察结果、来源快照和未知项 | sha256:dfb4394c754e |
| [docs/research/UNIVERSE.md](../../docs/research/UNIVERSE.md) | 旧筛选方法和候选说明，仅作历史参考 | sha256:ff17d43748dc |
| [docs/usage/COLLECTION.md](../../docs/usage/COLLECTION.md) | 旧采集器的接口、配置和输出说明 | sha256:b4a37b5d4071 |
| [docs/usage/DATABASE.md](../../docs/usage/DATABASE.md) | 旧库的可选查询、时间精度与备份方法 | sha256:73c0c8b3da1f |
| [docs/usage/HISTORY.md](../../docs/usage/HISTORY.md) | 旧目录、候选、历史任务及查询命令参考 | sha256:4c9eb369e472 |
| [pyproject.toml](../../pyproject.toml) | Python 打包配置及单一源码版本入口 | sha256:5fccbcc7bee3 |
| [scripts/README.md](../../scripts/README.md) | 代码、配置、测试、SQL 和检查入口说明 | sha256:105dff741a69 |
| [scripts/check_secrets.py](../../scripts/check_secrets.py) | 暂存区及 Git 历史的凭证隔离检查，不打印真实值 | sha256:deeb89ea73de |
| [scripts/collect.py](../../scripts/collect.py) | 旧采集 CLI 的薄入口，当前不恢复采集 | sha256:68a4e27d6d7d |
| [scripts/config/.env.example](../../scripts/config/.env.example) | 公开的空白凭证配置模板 | sha256:52b696866d0f |
| [scripts/config/seeds.json](../../scripts/config/seeds.json) | 旧试采精确英文规格种子，不是正式 UU 名单 | sha256:ddedf38ac869 |
| [scripts/config/vscode.code-workspace](../../scripts/config/vscode.code-workspace) | 旧库可选 SQLTools 工作区配置 | sha256:4f88c319a783 |
| [scripts/config/watchlist.json](../../scripts/config/watchlist.json) | 流金王朝、燃料喷射器等旧调查线索 | sha256:298f1fdecd1c |
| [scripts/hooks/pre-commit](../../scripts/hooks/pre-commit) | 本地提交前的暂存凭证检查 | sha256:377f8130236b |
| [scripts/hooks/pre-push](../../scripts/hooks/pre-push) | 历史凭证检查；新增远程推送仍暂停 | sha256:8bcdeaad4b7d |
| [scripts/manage_assets.py](../../scripts/manage_assets.py) | 生成及校验逐文件、逐目录版本和用途清单 | sha256:fddd51ed3569 |
| [scripts/pilot_uu_day.py](../../scripts/pilot_uu_day.py) | 单品单日 YOUPIN 小时行情与混合成交的独立有限试跑、离线核验及导出 | sha256:c14040085907 |
| [scripts/select_uu_research.py](../../scripts/select_uu_research.py) | 有预算的 P02 候选调查、正确商品身份补查和版本化验证名单选择 | sha256:19ceeeaa03de |
| [scripts/sql/01_catalog.sql](../../scripts/sql/01_catalog.sql) | 旧库目录搜索与身份查询 | sha256:7c51db5d6c1e |
| [scripts/sql/02_universe.sql](../../scripts/sql/02_universe.sql) | 旧候选名单查询 | sha256:c22e9b3e2b87 |
| [scripts/sql/03_market.sql](../../scripts/sql/03_market.sql) | 旧逐笔与行情查询 | sha256:fa8a82775930 |
| [scripts/sql/04_coverage.sql](../../scripts/sql/04_coverage.sql) | 旧覆盖和分页进度诊断 | sha256:dd7c696d2535 |
| [scripts/src/cs_youoweme/__init__.py](../../scripts/src/cs_youoweme/__init__.py) | 模块身份及包版本或职责说明 | sha256:71e095f1d8dc |
| [scripts/src/cs_youoweme/__main__.py](../../scripts/src/cs_youoweme/__main__.py) | Python 模块形式的 CLI 入口 | sha256:935a1c1166b0 |
| [scripts/src/cs_youoweme/cleaning.py](../../scripts/src/cs_youoweme/cleaning.py) | 规格、价格、数量、币种与时间标准化 | sha256:48ae59ccfc0d |
| [scripts/src/cs_youoweme/cli.py](../../scripts/src/cs_youoweme/cli.py) | 命令注册、参数与工作流调度 | sha256:a74dd9850179 |
| [scripts/src/cs_youoweme/collectors/__init__.py](../../scripts/src/cs_youoweme/collectors/__init__.py) | 模块身份及包版本或职责说明 | sha256:54d33ce8eae3 |
| [scripts/src/cs_youoweme/collectors/official.py](../../scripts/src/cs_youoweme/collectors/official.py) | 旧官方 API 客户端、缓存与配额节奏 | sha256:9738556f6f47 |
| [scripts/src/cs_youoweme/collectors/public.py](../../scripts/src/cs_youoweme/collectors/public.py) | 旧公开页面采集流程 | sha256:3ce200d6c932 |
| [scripts/src/cs_youoweme/collectors/website.py](../../scripts/src/cs_youoweme/collectors/website.py) | 旧匿名网页接口客户端、时钟同步与访问停止 | sha256:3cd3fae5bd6b |
| [scripts/src/cs_youoweme/config.py](../../scripts/src/cs_youoweme/config.py) | 旧种子与受保护本地凭证读取 | sha256:2e9cd406f322 |
| [scripts/src/cs_youoweme/errors.py](../../scripts/src/cs_youoweme/errors.py) | 安全可展示的采集异常类型 | sha256:33de510974d6 |
| [scripts/src/cs_youoweme/history/__init__.py](../../scripts/src/cs_youoweme/history/__init__.py) | 模块身份及包版本或职责说明 | sha256:d1daff51ccf3 |
| [scripts/src/cs_youoweme/history/aggregate.py](../../scripts/src/cs_youoweme/history/aggregate.py) | 行情聚合，保留缺失和覆盖语义 | sha256:154a0e27a927 |
| [scripts/src/cs_youoweme/history/catalog.py](../../scripts/src/cs_youoweme/history/catalog.py) | 目录身份、来源平台编号及搜索映射 | sha256:178e35a43db3 |
| [scripts/src/cs_youoweme/history/cli.py](../../scripts/src/cs_youoweme/history/cli.py) | 命令注册、参数与工作流调度 | sha256:65933b7672ed |
| [scripts/src/cs_youoweme/history/jobs.py](../../scripts/src/cs_youoweme/history/jobs.py) | 有预算的分页任务、恢复与原子检查点 | sha256:182c576dbaf9 |
| [scripts/src/cs_youoweme/history/normalize.py](../../scripts/src/cs_youoweme/history/normalize.py) | 逐笔及行情精度、时间和空值验证 | sha256:aaaa913c4ade |
| [scripts/src/cs_youoweme/history/query.py](../../scripts/src/cs_youoweme/history/query.py) | 旧库覆盖、状态、参数化查询和导出 | sha256:5ac2245777d6 |
| [scripts/src/cs_youoweme/history/schema.sql](../../scripts/src/cs_youoweme/history/schema.sql) | 旧历史库表、索引与任务结构 schema v2 | sha256:4bbee4ab4323 |
| [scripts/src/cs_youoweme/history/store.py](../../scripts/src/cs_youoweme/history/store.py) | 旧库 schema、事务、压缩归档和 worker 锁 | sha256:7b880556de0d |
| [scripts/src/cs_youoweme/history/universe.py](../../scripts/src/cs_youoweme/history/universe.py) | 旧候选筛选实现，仅机制参考，不沿用为新选品规则 | sha256:9b2670351d67 |
| [scripts/src/cs_youoweme/parsing.py](../../scripts/src/cs_youoweme/parsing.py) | Nuxt 响应解析及精确商品匹配 | sha256:d555ec0aa877 |
| [scripts/src/cs_youoweme/paths.py](../../scripts/src/cs_youoweme/paths.py) | 独立于工作目录的项目、配置与数据路径 | sha256:0c4ad1a5e3b9 |
| [scripts/src/cs_youoweme/storage.py](../../scripts/src/cs_youoweme/storage.py) | 原始证据、快照表、报告与本地 SQLite 存储 | sha256:f0bb61cafd4f |
| [scripts/src/cs_youoweme/transport.py](../../scripts/src/cs_youoweme/transport.py) | HTTP 传输及凭证重定向限制 | sha256:e94ef1008584 |
| [scripts/tests/_support.py](../../scripts/tests/_support.py) | 离线测试辅助与共享样本路径 | sha256:72d1db2c1218 |
| [scripts/tests/test_cleaning.py](../../scripts/tests/test_cleaning.py) | cleaning 模块的离线行为回归测试 | sha256:fd9a35252d7f |
| [scripts/tests/test_cli.py](../../scripts/tests/test_cli.py) | cli 模块的离线行为回归测试 | sha256:14b3111c2552 |
| [scripts/tests/test_collection.py](../../scripts/tests/test_collection.py) | collection 模块的离线行为回归测试 | sha256:c27cd56c8d63 |
| [scripts/tests/test_history.py](../../scripts/tests/test_history.py) | history 模块的离线行为回归测试 | sha256:c923f30defdd |
| [scripts/tests/test_parsing.py](../../scripts/tests/test_parsing.py) | parsing 模块的离线行为回归测试 | sha256:de780b4e0af1 |
| [scripts/tests/test_samples.py](../../scripts/tests/test_samples.py) | samples 模块的离线行为回归测试 | sha256:7cd15623e8d5 |
| [scripts/tests/test_secret_checks.py](../../scripts/tests/test_secret_checks.py) | secret_checks 模块的离线行为回归测试 | sha256:70bc3fbc2eb7 |
| [scripts/tests/test_selection.py](../../scripts/tests/test_selection.py) | selection 模块的离线行为回归测试 | sha256:571a40d68c4d |
| [scripts/tests/test_transport.py](../../scripts/tests/test_transport.py) | transport 模块的离线行为回归测试 | sha256:94369afa0d94 |
| [scripts/tests/test_universe.py](../../scripts/tests/test_universe.py) | universe 模块的离线行为回归测试 | sha256:98667d0001b0 |
| [scripts/tests/test_website.py](../../scripts/tests/test_website.py) | website 模块的离线行为回归测试 | sha256:930c0122e11d |
