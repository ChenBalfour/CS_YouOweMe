# 数据与来源证据

目录版本 layout-1.0。原初选验证规格10、候补6保留历史版本，当前百元候选待复核；最新状态见 [主进展](../docs/PROGRESS.md)。正式 UU 交易数据集与模型仍为0。P03 试跑仅准入 L0 来源观察。

| 位置 | 用途与状态 |
| --- | --- |
| samples/pilot_20261011/ | 已公开旧匿名快照及其 raw/tables/reports，冻结待复审 |
| local/database/ | 旧 SteamDT 库、压缩响应与 worker 锁；legacy / unreviewed |
| local/recon/、local/archive/ | 接口、事件、原网页及最初试采证据；p03_20261013_evidence 保存本轮官方/网页核验和 429 状态 |
| local/api_cache/ | 旧官方目录与配额状态，不自动刷新 |
| local/universes/ | 旧候选及新 P02 版本化验证名单，按明确用途管理 |
| local/staging/steamdt/p03_* | 独立单日与汇总字段补查库、压缩原始响应及只读复核产物，非正式数据集 |
| local/progress/ | 冻结的旧 JSON 进度记录 |
| local/manifests/ | 私有文件版本清单、整理前基线、迁移删除与核对记录 |

文字交接已集中到私有 `docs/local/progress/`。数据附带的来源 manifest、质量报告与原始网页属于数据追溯元数据，随该批数据保留。整理只删除已经核对的重复副本与缓存，没有清洗或修改旧库、响应及样本内容。

公开样本逐文件版本见 [统一清单](../docs/governance/FILE_CATALOG.json)；全部私有文件和目录的版本、用途见 `local/manifests/workspace-layout-1.0.json`。`.git` 内部对象由 Git 管理，不列入资产清单。凭证仅登记受保护配置版本，不保存内容或哈希。

`local/` 整体忽略，不把完整响应、库、凭证或私人账户资料加入 Git。原始资料不原地覆盖；新正式资产按 [文件制度](../docs/governance/FILE_MANAGEMENT.md)创建版本与来源清单。
