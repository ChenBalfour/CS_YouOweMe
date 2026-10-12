# 数据与来源证据

目录版本 layout-1.0。当前正式 UU 名单、已验收数据集、模型均为 0。

| 位置 | 用途与状态 |
| --- | --- |
| samples/pilot_20261011/ | 已公开旧匿名快照及其 raw/tables/reports，冻结待复审 |
| local/database/ | 旧 SteamDT 库、压缩响应与 worker 锁；legacy / unreviewed |
| local/recon/、local/archive/ | 接口、事件、原网页及最初试采证据 |
| local/api_cache/ | 旧官方目录与配额状态，不自动刷新 |
| local/universes/ | 旧候选，非正式 UU 名单 |
| local/progress/ | 冻结的旧 JSON 进度记录 |
| local/manifests/ | 私有文件版本清单、整理前基线、迁移删除与核对记录 |

文字交接已集中到私有 `docs/local/progress/`。数据附带的来源 manifest、质量报告与原始网页属于数据追溯元数据，随该批数据保留。整理只删除已经核对的重复副本与缓存，没有清洗或修改旧库、响应及样本内容。

公开样本逐文件版本见 [统一清单](../docs/governance/FILE_CATALOG.json)；全部私有文件和目录的版本、用途见 `local/manifests/workspace-layout-1.0.json`。`.git` 内部对象由 Git 管理，不列入资产清单。凭证仅登记受保护配置版本，不保存内容或哈希。

`local/` 整体忽略，不把完整响应、库、凭证或私人账户资料加入 Git。原始资料不原地覆盖；新正式资产按 [文件制度](../docs/governance/FILE_MANAGEMENT.md)创建版本与来源清单。
