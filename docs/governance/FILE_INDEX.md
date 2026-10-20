# 文件与目录说明

自动生成，目录版本 layout-1.0，冻结核心 0.3.5（未打发布标签）。完整 SHA-256 见 [机器清单](FILE_CATALOG.json)。私有逐项清单只在 data/local/manifests/workspace-layout-1.0.json；Git 内部对象由 Git 管理。生成清单使用固定目录版本，不计算自身哈希以避免循环。

## 目录

| 路径 | 用途 | 内容版本（摘要） |
| --- | --- | --- |
| [.](../..) | 项目根及 Git/Python 所需入口元数据 | sha256:f00dd4d757e8 |
| [.github](../../.github) | GitHub 工具约定的根目录配置 | sha256:1790293e25fd |
| [.github/workflows](../../.github/workflows) | 既有自动检查配置 | sha256:1790293e25fd |
| [data](../../data) | 来源数据及其伴随元数据 | sha256:3a0a9f4c5392 |
| [data/samples](../../data/samples) | 已公开、冻结待复审的旧匿名样本 | sha256:644f35f0c47c |
| [data/samples/pilot_20261011](../../data/samples/pilot_20261011) | 旧匿名样本批次及原始/表/报告分组 | sha256:644f35f0c47c |
| [data/samples/pilot_20261011/raw](../../data/samples/pilot_20261011/raw) | 旧匿名样本批次及原始/表/报告分组 | sha256:be9fba468537 |
| [data/samples/pilot_20261011/reports](../../data/samples/pilot_20261011/reports) | 旧匿名样本批次及原始/表/报告分组 | sha256:67309b9a13e4 |
| [data/samples/pilot_20261011/tables](../../data/samples/pilot_20261011/tables) | 旧匿名样本批次及原始/表/报告分组 | sha256:d04bb394675d |
| [docs](../../docs) | 计划、制度、使用说明和交接记录 | sha256:51d1c8afda60 |
| [docs/data](../../docs/data) | 来源、schema 与字段说明 | sha256:25c5b1983007 |
| [docs/governance](../../docs/governance) | 管理、阶段、资产登记与版本索引 | sha256:97e9d6bd2a42 |
| [docs/releases](../../docs/releases) | 历史发布与本地版本变更说明 | sha256:565b4af8d0db |
| [docs/research](../../docs/research) | 专项选品、核验计划和有限调查证据，三大主文档的附件 | sha256:bcb3d7a769b6 |
| [docs/usage](../../docs/usage) | 用户本地观察、图表导出与旧实现参考，不构成采集或发布授权 | sha256:95a11e3b398b |
| [scripts](../../scripts) | 所有可执行代码及其工程配套 | sha256:097187f9e778 |
| [scripts/config](../../scripts/config) | 脚本配置、空白模板与受保护本地凭证 | sha256:a5980c8b8b12 |
| [scripts/hooks](../../scripts/hooks) | 本地 Git 凭证检查 hooks | sha256:89d7eda41c4a |
| [scripts/notebooks](../../scripts/notebooks) | 用户手动运行的 Notebook 入口，Git 中清空执行输出 | sha256:5d271afd87c1 |
| [scripts/research](../../scripts/research) | 当前离线研究包，按数据、模型、评估、可视化分工；独立于冻结采集核心 | sha256:2804ec64c299 |
| [scripts/research/data](../../scripts/research/data) | 冻结来源快照、七品清洗、缺失感知质量与日级样本/标签 | sha256:89a5fa8565a3 |
| [scripts/research/evaluation](../../scripts/research/evaluation) | 候选校验、验证集选择、锁定测试、成本情景和不可变评估产物 | sha256:d3fbc1fbd678 |
| [scripts/research/models](../../scripts/research/models) | 固定价格预测基准及以后经批准的模型实现 | sha256:624afba236cb |
| [scripts/research/visualization](../../scripts/research/visualization) | 历史、测试期真实/预测价格及七日路径图表，不联网或训练 | sha256:b009f89dfd08 |
| [scripts/sql](../../scripts/sql) | 旧历史库只读诊断查询 | sha256:78d833bce86b |
| [scripts/src](../../scripts/src) | Python 包源码 | sha256:f1cf0bb82e2b |
| [scripts/src/cs_youoweme](../../scripts/src/cs_youoweme) | 旧技术实现，可按对应用途审查复用 | sha256:f1cf0bb82e2b |
| [scripts/src/cs_youoweme/collectors](../../scripts/src/cs_youoweme/collectors) | 旧公开页面、官方和匿名接口采集机制 | sha256:292f48b673f2 |
| [scripts/src/cs_youoweme/history](../../scripts/src/cs_youoweme/history) | 旧目录、分页任务、SQLite、查询和候选机制 | sha256:169bf7b93ce2 |
| [scripts/tests](../../scripts/tests) | 离线与合成回归测试 | sha256:8ec1f9d1c857 |

## 文件

| 路径 | 用途 | 内容版本（摘要） |
| --- | --- | --- |
| [.gitattributes](../../.gitattributes) | 跨平台文本换行规则 | sha256:bef30d55070d |
| [.github/workflows/ci.yml](../../.github/workflows/ci.yml) | 既有远程离线检查工作流，根目录位置由 GitHub 约定 | sha256:e7f8b4eb1c60 |
| [.gitignore](../../.gitignore) | 私有数据、文档、凭证与生成缓存的 Git 排除规则 | sha256:3e41120a23af |
| [AGENTS.md](../../AGENTS.md) | 协作者的执行、阶段、凭证及发布约束 | sha256:71e7c588e099 |
| [LICENSE](../../LICENSE) | 原创代码与文档的 MIT 授权 | sha256:9ccc1508d876 |
| [README.md](../../README.md) | 项目入口、当前状态与三类目录索引 | sha256:2edd0ded4927 |
| [data/README.md](../../data/README.md) | 私有数据与已公开冻结样本的生命周期说明 | sha256:37fdf1428196 |
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
| [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) | 架构主文档：真实实现、数据流、存储恢复与待建模型和执行层 | sha256:cf0c28ab3718 |
| [docs/PRODUCT.md](../../docs/PRODUCT.md) | 产品主文档：目标、范围、用户流程、策略、建议输出和验收要求 | sha256:7fab04e07c60 |
| [docs/PROGRESS.md](../../docs/PROGRESS.md) | 进展主文档：每次操作成果、验证、实际运行、当前卡点和下一步 | sha256:92f834f45b2f |
| [docs/README.md](../../docs/README.md) | 三大主文档与专项字段、运行、管理附件索引 | sha256:2c485a176d5f |
| [docs/data/CYREX_DAILY_SAMPLES.md](../../docs/data/CYREX_DAILY_SAMPLES.md) | 次时代日级候选字段、28天序列、七日价格目标、缺失/隔离规则和Notebook操作说明 | sha256:5364f0b71a22 |
| [docs/data/DATA_DICTIONARY.md](../../docs/data/DATA_DICTIONARY.md) | 旧公开快照表的字段字典 | sha256:f0589a84da9c |
| [docs/data/DATA_SOURCES.md](../../docs/data/DATA_SOURCES.md) | 旧来源、采集证据及口径限制 | sha256:c81a42660293 |
| [docs/data/HISTORY_SCHEMA.md](../../docs/data/HISTORY_SCHEMA.md) | 旧历史库 schema v2、时间与字段口径 | sha256:62af74eaff65 |
| [docs/data/SEVEN_DAILY_SAMPLES.md](../../docs/data/SEVEN_DAILY_SAMPLES.md) | 七品21输入特征、独立点/路径标签、样本资格、版本与Notebook操作说明 | sha256:d8b1adf99a1b |
| [docs/data/SOURCE_ALIGNMENT_PLAN.md](../../docs/data/SOURCE_ALIGNMENT_PLAN.md) | SteamDT研究主序列与UU供给/执行补充方案，分字段聚合、过去值对齐、可得时间及登录与换品规则；尚未构建特征或训练 | sha256:10d92e65b710 |
| [docs/data/STEAMDT_CLEANING.md](../../docs/data/STEAMDT_CLEANING.md) | 七品清洗SQLite表、mask/缺失/极端事件与Notebook使用及特征工程边界 | sha256:b5a64160dd7a |
| [docs/data/UU_EXECUTION_RULES.md](../../docs/data/UU_EXECUTION_RULES.md) | Steam 和 UU 公开规则、旧版适用限制、资金时间字段及访问限制处理 | sha256:824aebde1f40 |
| [docs/data/UU_FIELD_CONTRACT.md](../../docs/data/UU_FIELD_CONTRACT.md) | 已核验 UU 来源行情、汇总快照及混合逐笔字段定义与执行准入限制 | sha256:a7069d1edce0 |
| [docs/data/UU_HISTORY_CHART.md](../../docs/data/UU_HISTORY_CHART.md) | UU 历史图表指标映射、两份用户响应的字段与实际间隔核验、统计及决策时间边界 | sha256:35159eb2941f |
| [docs/governance/ASSET_REGISTER.md](../../docs/governance/ASSET_REGISTER.md) | 旧资产保留依据及按用途准入状态 | sha256:b3c0dc1ab223 |
| [docs/governance/CONTRIBUTING.md](../../docs/governance/CONTRIBUTING.md) | 本地工程修改与检查方法 | sha256:5cfb682e98dd |
| [docs/governance/FILE_CATALOG.json](../../docs/governance/FILE_CATALOG.json) | 公开文件及目录的用途、版本和内容哈希索引 | layout-1.0.catalog |
| [docs/governance/FILE_INDEX.md](../../docs/governance/FILE_INDEX.md) | 逐文件与逐目录用途和内容版本的可读索引，由 manage_assets 生成 | layout-1.0.catalog |
| [docs/governance/FILE_MANAGEMENT.md](../../docs/governance/FILE_MANAGEMENT.md) | 文件布局、资产生命周期、版本、迁移及发布制度 | sha256:0462384bdf29 |
| [docs/governance/HANDOFF.md](../../docs/governance/HANDOFF.md) | 精简交接入口：三大主文档、接手顺序与版本保护 | sha256:b479cf1a051a |
| [docs/governance/ORGANIZATION.md](../../docs/governance/ORGANIZATION.md) | layout-1.0 整理结果、迁移、清理及恢复方法 | sha256:3399a18b667b |
| [docs/governance/SECURITY.md](../../docs/governance/SECURITY.md) | 凭证隔离与安全问题处理说明 | sha256:8e93242a8e09 |
| [docs/governance/STATE.md](../../docs/governance/STATE.md) | 旧状态路径的兼容入口，当前进展统一到 PROGRESS | sha256:33f3fa4756b9 |
| [docs/releases/CHANGELOG.md](../../docs/releases/CHANGELOG.md) | 代码历史变更及未打发布标签的迭代说明 | sha256:f0f4cca524b1 |
| [docs/releases/WORK_LOG_20261014_20261019.md](../../docs/releases/WORK_LOG_20261014_20261019.md) | 10月14至19日既往操作记录的冻结归档，不维护当前路线 | sha256:a611f034e169 |
| [docs/research/DATA_METHODS_20261019.md](../../docs/research/DATA_METHODS_20261019.md) | 2025至2026年一手论文与官方实现调研：缺失感知、异常、特征和概率预测的采用理由与候选对照 | sha256:5f30ba32958c |
| [docs/research/P03_OBSERVATION_PLAN.md](../../docs/research/P03_OBSERVATION_PLAN.md) | 用户本地连续观察的固定窗口、预算、恢复、用途与未启动状态 | sha256:0525e7c988e8 |
| [docs/research/P03_VERIFICATION_PLAN.md](../../docs/research/P03_VERIFICATION_PLAN.md) | P03 两规格来源、盘口、属性与规则核验范围、预算和验收问题 | sha256:2a0c3cc09406 |
| [docs/research/P03_VERIFICATION_REPORT.md](../../docs/research/P03_VERIFICATION_REPORT.md) | P03 有限试跑结果、证据、报价异常、未知项和 L0 准入边界 | sha256:c2fb19ab18c7 |
| [docs/research/PLAN.md](../../docs/research/PLAN.md) | 旧研究计划路径的兼容入口，当前方案统一到三大主文档 | sha256:c783e3b0aea6 |
| [docs/research/SELECTION_PLAN.md](../../docs/research/SELECTION_PLAN.md) | P02 选品计划、事先固定的范围预算及身份纠正修订依据 | sha256:1d0516debcd5 |
| [docs/research/SELECTION_REPORT.md](../../docs/research/SELECTION_REPORT.md) | P02 主力、候补、排除与观察结果、来源快照和未知项 | sha256:dfb4394c754e |
| [docs/research/SELECTION_REVISION_20261014.md](../../docs/research/SELECTION_REVISION_20261014.md) | 首批百元范围、用户求购截图的属性条件证据与待核验候选及复核顺序 | sha256:224e09232221 |
| [docs/usage/COLLECTION.md](../../docs/usage/COLLECTION.md) | 旧采集器的接口、配置和输出说明 | sha256:b4a37b5d4071 |
| [docs/usage/DATABASE.md](../../docs/usage/DATABASE.md) | 旧库的可选查询、时间精度与备份方法 | sha256:73c0c8b3da1f |
| [docs/usage/FORECAST_DASHBOARD.md](../../docs/usage/FORECAST_DASHBOARD.md) | 预测图表Notebook、固定基准、评价指标、保存位置与成本/执行边界说明 | sha256:1216803effc5 |
| [docs/usage/HISTORY.md](../../docs/usage/HISTORY.md) | 旧目录、候选、历史任务及查询命令参考 | sha256:523bfca2a135 |
| [docs/usage/OBSERVE_24H.md](../../docs/usage/OBSERVE_24H.md) | VS Code Notebook 的内核、启动、停止、恢复、输出和采样边界说明 | sha256:89250d89c963 |
| [docs/usage/STEAMDT_RESEARCH.md](../../docs/usage/STEAMDT_RESEARCH.md) | SteamDT本地小时研究库、商品清单扩展、分页恢复、去重修订、请求预算、跨周期与日常更新说明 | sha256:94519729ed83 |
| [docs/usage/UU_BROWSER_AUTOMATION.md](../../docs/usage/UU_BROWSER_AUTOMATION.md) | 待实现的专用Edge商品队列、页面自动操作与保存入库方案，明确登录边界和分阶段真实验收 | sha256:2d15fbd4fa57 |
| [docs/usage/UU_CHART_EXPORT.md](../../docs/usage/UU_CHART_EXPORT.md) | Edge 复制图表响应正文及用户本地离线核验命令，不复制请求头或启动采集 | sha256:2c2af0fd8cbe |
| [docs/usage/UU_DIRECT_COLLECT.md](../../docs/usage/UU_DIRECT_COLLECT.md) | 本地纯脚本凭证配置、单请求试采、间隔配额、停止恢复和独立输出说明；不保证Cookie单独可用 | sha256:fb37ca5605d7 |
| [docs/usage/UU_HISTORY_COLLECT.md](../../docs/usage/UU_HISTORY_COLLECT.md) | 用户登录页面历史采集、下载入库、恢复限制、当前报价用途与UU/SteamDT结合方案 | sha256:405e96e41e84 |
| [pyproject.toml](../../pyproject.toml) | Python 打包配置及单一源码版本入口 | sha256:11cbed521a6f |
| [scripts/README.md](../../scripts/README.md) | 代码、配置、测试、SQL 和检查入口说明 | sha256:9e524996cabb |
| [scripts/build_research_samples.py](../../scripts/build_research_samples.py) | 日级样本构建的兼容CLI/API薄入口，实际实现委托research/data；不联网或训练 | sha256:fb83a73151d8 |
| [scripts/build_seven_samples.py](../../scripts/build_seven_samples.py) | 七品特征/标签薄CLI与Notebook API：显式父清洗ID、离线新建版本和只读status，不训练 | sha256:f4d7f232bf42 |
| [scripts/check_secrets.py](../../scripts/check_secrets.py) | 暂存区及 Git 历史的凭证隔离检查，不打印真实值 | sha256:deeb89ea73de |
| [scripts/clean_steamdt_data.py](../../scripts/clean_steamdt_data.py) | 七品小时清洗CLI/API薄入口，只读来源、缺失感知网格、事件标记与独立SQLite版本，不训练 | sha256:f46584263495 |
| [scripts/collect.py](../../scripts/collect.py) | 旧采集 CLI 的薄入口，当前不恢复采集 | sha256:68a4e27d6d7d |
| [scripts/collect_uu_charts.js](../../scripts/collect_uu_charts.js) | 用户正常登录UU页面的有限历史批次采集，价格四窗口/数量三窗口、内存会话、限流停止与下载检查点；真实稳定性待验收 | sha256:03769ccaa8ae |
| [scripts/collect_uu_direct.py](../../scripts/collect_uu_direct.py) | 用户本地纯HTTP单请求试采与有限队列继续；私有认证配置、串行间隔、全局配额、继承访问停止及独立SQLite/CSV，真实直连待验收 | sha256:e7df498c12b6 |
| [scripts/config/.env.example](../../scripts/config/.env.example) | 公开的空白凭证配置模板 | sha256:52b696866d0f |
| [scripts/config/cyrex_baseline_spec.json](../../scripts/config/cyrex_baseline_spec.json) | 评分前固定的基准规则、验证选择准则、测试与研究边界，不按测试结果调参 | sha256:216241720c19 |
| [scripts/config/cyrex_daily_spec.json](../../scripts/config/cyrex_daily_spec.json) | 次时代日级研究的决策时间、输入窗口、目标、特征、时间划分与研究限制固定规范 | sha256:f5356ed81aa4 |
| [scripts/config/seeds.json](../../scripts/config/seeds.json) | 旧试采精确英文规格种子，不是正式 UU 名单 | sha256:ddedf38ac869 |
| [scripts/config/seven_daily_spec.json](../../scripts/config/seven_daily_spec.json) | 七品日级输入/点目标/路径风险、缺失门槛、共同日期分组及七日purge的冻结1.0规范 | sha256:9e17f5e60a3d |
| [scripts/config/steamdt_cleaning_spec.json](../../scripts/config/steamdt_cleaning_spec.json) | 七品清洗的缺失、价格/量额校验、因果波动诊断与输入质量门槛固定规范 | sha256:902052bafa18 |
| [scripts/config/steamdt_research_items.json](../../scripts/config/steamdt_research_items.json) | 七个普通百元候选的精确名称、SteamDT编号与历史起点种子；新工作区复制后另行维护 | sha256:07e5852fef23 |
| [scripts/config/uu_direct_auth.example.json](../../scripts/config/uu_direct_auth.example.json) | UU纯脚本入口的公开空白认证字段模板，不含真实凭证 | sha256:74325fe54cbc |
| [scripts/config/uu_direct_items.example.json](../../scripts/config/uu_direct_items.example.json) | UU纯脚本单品有限试采的模板和窗口参数样例，44828身份尚未核验 | sha256:b66952eb8f01 |
| [scripts/config/vscode.code-workspace](../../scripts/config/vscode.code-workspace) | 旧库可选 SQLTools 工作区配置 | sha256:4f88c319a783 |
| [scripts/config/watchlist.json](../../scripts/config/watchlist.json) | 流金王朝、燃料喷射器等旧调查线索 | sha256:298f1fdecd1c |
| [scripts/evaluate_research_baselines.py](../../scripts/evaluate_research_baselines.py) | 离线固定规则基准评估薄入口：验证集选规则、锁定测试和七日来源参考预测，不执行交易 | sha256:c15fb3364880 |
| [scripts/hooks/pre-commit](../../scripts/hooks/pre-commit) | 本地提交前的暂存凭证检查 | sha256:377f8130236b |
| [scripts/hooks/pre-push](../../scripts/hooks/pre-push) | 推送前历史凭证检查；本轮公开分支迭代已获授权 | sha256:8bcdeaad4b7d |
| [scripts/import_uu_chart_batch.py](../../scripts/import_uu_chart_batch.py) | 用户浏览器下载批次的纯离线校验与独立SQLite/CSV入库，保留窗口、状态和历史可得时间未知 | sha256:1241a8fc9a35 |
| [scripts/manage_assets.py](../../scripts/manage_assets.py) | 生成及校验逐文件、逐目录版本和用途清单 | sha256:3e09345adb03 |
| [scripts/notebooks/cyrex_daily_samples.ipynb](../../scripts/notebooks/cyrex_daily_samples.ipynb) | VS Code离线日级样本构建与检查入口，默认不构建、交付空输出；不联网或训练 | sha256:7fb48801d825 |
| [scripts/notebooks/cyrex_forecast_dashboard.ipynb](../../scripts/notebooks/cyrex_forecast_dashboard.ipynb) | VS Code离线预测评估与可视化入口，默认读取已有结果，显式开关才新建评估版本 | sha256:6bea389cab84 |
| [scripts/notebooks/seven_daily_samples.ipynb](../../scripts/notebooks/seven_daily_samples.ipynb) | VS Code七品特征/标签检查，默认只读既有结果；显式开关才新建版本，交付空输出 | sha256:42bcd2645dda |
| [scripts/notebooks/steamdt_cleaning.ipynb](../../scripts/notebooks/steamdt_cleaning.ipynb) | VS Code七品清洗与质量检查入口，默认只读已有结果；显式开关新建版本，不采集或训练 | sha256:7c8e0bfcec8e |
| [scripts/notebooks/steamdt_research.ipynb](../../scripts/notebooks/steamdt_research.ipynb) | VS Code有限采集入口：商品清单、默认关闭联网、手动续采与本地报告；交付空输出 | sha256:03bd3cc1cdc2 |
| [scripts/notebooks/uu_history_collect.ipynb](../../scripts/notebooks/uu_history_collect.ipynb) | 用户本地历史采集指引、选择下载批次、离线入库与覆盖检查；无训练代码、交付空输出 | sha256:1ea2126830c2 |
| [scripts/notebooks/uu_observe_24h.ipynb](../../scripts/notebooks/uu_observe_24h.ipynb) | VS Code 用户本地 24 小时连续观察 Notebook，交付时输出清空且未执行 | sha256:750039fe0738 |
| [scripts/observe_uu_24h.py](../../scripts/observe_uu_24h.py) | 用户显式启动的新建/恢复连续观察 CLI，status 只读，不默认运行 | sha256:dadd8661e1d3 |
| [scripts/pilot_uu_day.py](../../scripts/pilot_uu_day.py) | 单品单日 YOUPIN 小时行情与混合成交的独立有限试跑、离线核验及导出 | sha256:774810dd3002 |
| [scripts/research/__init__.py](../../scripts/research/__init__.py) | 研究功能包的职责与公共接口 | sha256:8dd0a4a413e6 |
| [scripts/research/data/__init__.py](../../scripts/research/data/__init__.py) | 研究功能包的职责与公共接口 | sha256:46b38c5c0e0c |
| [scripts/research/data/clean_hourly.py](../../scripts/research/data/clean_hourly.py) | steamdt-hourly-cleaning-1.0：只读七品源版本、NULL/mask、原值保留、因果事件诊断与质量窗口 | sha256:3cd3d20e5a82 |
| [scripts/research/data/daily_samples.py](../../scripts/research/data/daily_samples.py) | cyrex-daily-samples-1.1：只读冻结小时来源、28天样本、七日标签与准确依赖快照 | sha256:23f74b22ed36 |
| [scripts/research/data/seven_samples.py](../../scripts/research/data/seven_samples.py) | seven-daily-samples-1.0：过去21特征、独立七日点/路径标签、同日跨品与时间隔离、不可变产物 | sha256:f2003ad5e3bd |
| [scripts/research/evaluation/__init__.py](../../scripts/research/evaluation/__init__.py) | 研究功能包的职责与公共接口 | sha256:818a99b0001f |
| [scripts/research/evaluation/baseline_report.py](../../scripts/research/evaluation/baseline_report.py) | 候选完整性校验、验证选择及锁定测试、预测与实验清单 | sha256:010e93701560 |
| [scripts/research/evaluation/costs.py](../../scripts/research/evaluation/costs.py) | 已知买价与费用的保本情景计算；未知输入保留为不足 | sha256:b0742827218e |
| [scripts/research/models/__init__.py](../../scripts/research/models/__init__.py) | 研究功能包的职责与公共接口 | sha256:891dec6c2159 |
| [scripts/research/models/baselines.py](../../scripts/research/models/baselines.py) | 仅使用过去价格特征的持平/固定对数趋势规则与七日路径 | sha256:0169d0389cff |
| [scripts/research/visualization/__init__.py](../../scripts/research/visualization/__init__.py) | 研究功能包的职责与公共接口 | sha256:c37b033a0041 |
| [scripts/research/visualization/forecast_charts.py](../../scripts/research/visualization/forecast_charts.py) | 来源历史、真实七日目标与固定规则预测路径的Matplotlib图表及版本报告 | sha256:45bf9f9ea640 |
| [scripts/review_uu_chart.py](../../scripts/review_uu_chart.py) | 离线核验用户导出的 UU 图表响应，按请求指标分离价格和数量，保存独立 SQLite/CSV 与真实时间间隔 | sha256:d5031b0a6fe6 |
| [scripts/review_uu_verification.py](../../scripts/review_uu_verification.py) | 离线核对 P03 原始哈希、全页逐笔、只读库与字段准入，导出私有规范观察 | sha256:a0db71ab616d |
| [scripts/select_uu_research.py](../../scripts/select_uu_research.py) | 有预算的 P02 候选调查、正确商品身份补查和版本化验证名单选择 | sha256:19ceeeaa03de |
| [scripts/sql/01_catalog.sql](../../scripts/sql/01_catalog.sql) | 旧库目录搜索与身份查询 | sha256:7c51db5d6c1e |
| [scripts/sql/02_universe.sql](../../scripts/sql/02_universe.sql) | 旧候选名单查询 | sha256:c22e9b3e2b87 |
| [scripts/sql/03_market.sql](../../scripts/sql/03_market.sql) | 旧逐笔与行情查询 | sha256:fa8a82775930 |
| [scripts/sql/04_coverage.sql](../../scripts/sql/04_coverage.sql) | 旧覆盖和分页进度诊断 | sha256:dd7c696d2535 |
| [scripts/src/cs_youoweme/__init__.py](../../scripts/src/cs_youoweme/__init__.py) | 模块身份及包版本或职责说明 | sha256:30648bbd9bfd |
| [scripts/src/cs_youoweme/__main__.py](../../scripts/src/cs_youoweme/__main__.py) | Python 模块形式的 CLI 入口 | sha256:935a1c1166b0 |
| [scripts/src/cs_youoweme/cleaning.py](../../scripts/src/cs_youoweme/cleaning.py) | 规格、价格、数量、币种与时间标准化 | sha256:48ae59ccfc0d |
| [scripts/src/cs_youoweme/cli.py](../../scripts/src/cs_youoweme/cli.py) | 命令注册、参数与工作流调度 | sha256:a74dd9850179 |
| [scripts/src/cs_youoweme/collectors/__init__.py](../../scripts/src/cs_youoweme/collectors/__init__.py) | 模块身份及包版本或职责说明 | sha256:54d33ce8eae3 |
| [scripts/src/cs_youoweme/collectors/official.py](../../scripts/src/cs_youoweme/collectors/official.py) | 旧官方 API 客户端、缓存与配额节奏 | sha256:9738556f6f47 |
| [scripts/src/cs_youoweme/collectors/public.py](../../scripts/src/cs_youoweme/collectors/public.py) | 旧公开页面采集流程 | sha256:3ce200d6c932 |
| [scripts/src/cs_youoweme/collectors/website.py](../../scripts/src/cs_youoweme/collectors/website.py) | 旧匿名网页接口客户端、时钟同步与访问停止 | sha256:7d845693d32d |
| [scripts/src/cs_youoweme/config.py](../../scripts/src/cs_youoweme/config.py) | 旧种子与受保护本地凭证读取 | sha256:2e9cd406f322 |
| [scripts/src/cs_youoweme/errors.py](../../scripts/src/cs_youoweme/errors.py) | 安全可展示的采集异常类型 | sha256:33de510974d6 |
| [scripts/src/cs_youoweme/history/__init__.py](../../scripts/src/cs_youoweme/history/__init__.py) | 模块身份及包版本或职责说明 | sha256:d1daff51ccf3 |
| [scripts/src/cs_youoweme/history/aggregate.py](../../scripts/src/cs_youoweme/history/aggregate.py) | 行情聚合，保留缺失和覆盖语义 | sha256:154a0e27a927 |
| [scripts/src/cs_youoweme/history/catalog.py](../../scripts/src/cs_youoweme/history/catalog.py) | 目录身份、来源平台编号及搜索映射 | sha256:178e35a43db3 |
| [scripts/src/cs_youoweme/history/cli.py](../../scripts/src/cs_youoweme/history/cli.py) | 命令注册、参数与工作流调度 | sha256:65933b7672ed |
| [scripts/src/cs_youoweme/history/jobs.py](../../scripts/src/cs_youoweme/history/jobs.py) | 有预算的分页任务、恢复与原子检查点 | sha256:182c576dbaf9 |
| [scripts/src/cs_youoweme/history/normalize.py](../../scripts/src/cs_youoweme/history/normalize.py) | 逐笔及行情精度、时间和空值验证 | sha256:aaaa913c4ade |
| [scripts/src/cs_youoweme/history/observe.py](../../scripts/src/cs_youoweme/history/observe.py) | 固定截止、逐时点检查点、预算、访问停止和只读状态的用户本地前向观察机制 | sha256:b5222bf62cf5 |
| [scripts/src/cs_youoweme/history/query.py](../../scripts/src/cs_youoweme/history/query.py) | 旧库覆盖、状态、参数化查询和导出 | sha256:5ac2245777d6 |
| [scripts/src/cs_youoweme/history/schema.sql](../../scripts/src/cs_youoweme/history/schema.sql) | 旧历史库表、索引与任务结构 schema v2 | sha256:4bbee4ab4323 |
| [scripts/src/cs_youoweme/history/store.py](../../scripts/src/cs_youoweme/history/store.py) | 旧库 schema、事务、压缩归档和 worker 锁 | sha256:7b880556de0d |
| [scripts/src/cs_youoweme/history/universe.py](../../scripts/src/cs_youoweme/history/universe.py) | 旧候选筛选实现，仅机制参考，不沿用为新选品规则 | sha256:9b2670351d67 |
| [scripts/src/cs_youoweme/history/verification.py](../../scripts/src/cs_youoweme/history/verification.py) | 核验后来源平台分类、可空 Decimal 属性和 UU 汇总报价异常及执行准入标记 | sha256:1dbfe1e3f525 |
| [scripts/src/cs_youoweme/parsing.py](../../scripts/src/cs_youoweme/parsing.py) | Nuxt 响应解析及精确商品匹配 | sha256:d555ec0aa877 |
| [scripts/src/cs_youoweme/paths.py](../../scripts/src/cs_youoweme/paths.py) | 独立于工作目录的项目、配置与数据路径 | sha256:0c4ad1a5e3b9 |
| [scripts/src/cs_youoweme/storage.py](../../scripts/src/cs_youoweme/storage.py) | 原始证据、快照表、报告与本地 SQLite 存储 | sha256:f0bb61cafd4f |
| [scripts/src/cs_youoweme/transport.py](../../scripts/src/cs_youoweme/transport.py) | HTTP 传输及凭证重定向限制 | sha256:e94ef1008584 |
| [scripts/steamdt_research.py](../../scripts/steamdt_research.py) | SteamDT显式悠悠小时研究库：商品登记、有限回补、分页续采、增量复核、修订追溯及报告，独立组件1.0 | sha256:b08db3e828c8 |
| [scripts/tests/_support.py](../../scripts/tests/_support.py) | 离线测试辅助与共享样本路径 | sha256:72d1db2c1218 |
| [scripts/tests/test_cleaning.py](../../scripts/tests/test_cleaning.py) | cleaning 模块的离线行为回归测试 | sha256:fd9a35252d7f |
| [scripts/tests/test_cli.py](../../scripts/tests/test_cli.py) | cli 模块的离线行为回归测试 | sha256:14b3111c2552 |
| [scripts/tests/test_collection.py](../../scripts/tests/test_collection.py) | collection 模块的离线行为回归测试 | sha256:c27cd56c8d63 |
| [scripts/tests/test_forecast_charts.py](../../scripts/tests/test_forecast_charts.py) | forecast_charts 模块的离线行为回归测试 | sha256:cf3eee00c549 |
| [scripts/tests/test_history.py](../../scripts/tests/test_history.py) | history 模块的离线行为回归测试 | sha256:c923f30defdd |
| [scripts/tests/test_hourly_cleaning.py](../../scripts/tests/test_hourly_cleaning.py) | hourly_cleaning 模块的离线行为回归测试 | sha256:e6fe6e394bdf |
| [scripts/tests/test_observe.py](../../scripts/tests/test_observe.py) | observe 模块的离线行为回归测试 | sha256:09d8ce145210 |
| [scripts/tests/test_parsing.py](../../scripts/tests/test_parsing.py) | parsing 模块的离线行为回归测试 | sha256:de780b4e0af1 |
| [scripts/tests/test_research_baselines.py](../../scripts/tests/test_research_baselines.py) | research_baselines 模块的离线行为回归测试 | sha256:4edb8a6902ea |
| [scripts/tests/test_research_samples.py](../../scripts/tests/test_research_samples.py) | research_samples 模块的离线行为回归测试 | sha256:6d5519353a7e |
| [scripts/tests/test_samples.py](../../scripts/tests/test_samples.py) | samples 模块的离线行为回归测试 | sha256:7cd15623e8d5 |
| [scripts/tests/test_secret_checks.py](../../scripts/tests/test_secret_checks.py) | secret_checks 模块的离线行为回归测试 | sha256:70bc3fbc2eb7 |
| [scripts/tests/test_selection.py](../../scripts/tests/test_selection.py) | selection 模块的离线行为回归测试 | sha256:571a40d68c4d |
| [scripts/tests/test_seven_samples.py](../../scripts/tests/test_seven_samples.py) | seven_samples 模块的离线行为回归测试 | sha256:12468d61b6c0 |
| [scripts/tests/test_steamdt_research.py](../../scripts/tests/test_steamdt_research.py) | steamdt_research 模块的离线行为回归测试 | sha256:0a68d55417d3 |
| [scripts/tests/test_transport.py](../../scripts/tests/test_transport.py) | transport 模块的离线行为回归测试 | sha256:94369afa0d94 |
| [scripts/tests/test_universe.py](../../scripts/tests/test_universe.py) | universe 模块的离线行为回归测试 | sha256:98667d0001b0 |
| [scripts/tests/test_uu_chart.py](../../scripts/tests/test_uu_chart.py) | uu_chart 模块的离线行为回归测试 | sha256:62b941a8b6b3 |
| [scripts/tests/test_uu_chart_batch.py](../../scripts/tests/test_uu_chart_batch.py) | uu_chart_batch 模块的离线行为回归测试 | sha256:d3b75e019fae |
| [scripts/tests/test_uu_direct.py](../../scripts/tests/test_uu_direct.py) | uu_direct 模块的离线行为回归测试 | sha256:dfa80b9dd2ca |
| [scripts/tests/test_verification.py](../../scripts/tests/test_verification.py) | verification 模块的离线行为回归测试 | sha256:daadf0ab97ec |
| [scripts/tests/test_website.py](../../scripts/tests/test_website.py) | website 模块的离线行为回归测试 | sha256:c1cf0b6aa1e3 |
| [scripts/verify_public_evidence.py](../../scripts/verify_public_evidence.py) | 有预算的公开网页/规则证据和已发现 UU 只读入口抓取，访问受限主机持久停止 | sha256:775ac31fc386 |
| [scripts/verify_uu_fields.py](../../scripts/verify_uu_fields.py) | 两个精确规格的 SteamDT UU 汇总盘口字段有限补查，独立库与准确源码留存 | sha256:2b984a579216 |
