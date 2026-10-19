# 本地数据与研究产物

逐品历史价格要保存。SQLite负责去重、续采和修订；Notebook只配置、读取和展示。UU当前快照也有历史价值：K线不能重建原时刻的价差、数量和属性条件。

| 当前位置（data下） | 职责 |
| --- | --- |
| local/staging/steamdt/research_20261016_v1/ | 七品registry、小时SQLite、原始raw、分页任务、来源修订、运行源码和覆盖报告 |
| local/staging/steamdt/research_control/ | 共享访问停止/配额/锁，不能通过清理重置 |
| local/staging/uu_charts/ | UU历史价格/数量的独立来源、窗口、SQLite与采集时间 |
| local/datasets/steamdt_clean/ | 七品清洗研究版：全部源版本、小时网格、NULL/mask与事件/质量诊断，不自动训练 |
| local/reports/cleaning_reviews/ | 清洗原值、时间窗口和默认Notebook只读行为的独立复核 |
| local/staging/research_samples/ | 每版冻结来源、日级特征/标签、28日序列、质量与源码规范 |
| local/artifacts/baseline_evaluations/ | 固定基准、验证选择、锁定测试、七日路径与准确源码 |
| local/reports/baseline_charts/ | 从冻结评估生成的价格图和独立清单 |
| local/manifests/ | 私有逐项版本、清理计划/回执和保留核验 |

各轮使用独立ID，latest指向明确版本，旧结果不覆盖。原始响应压缩保存，小时主表去重且保留修订；派生CSV/PNG可重建，但不自动删除唯一冻结版本或用户真实运行结果。

旧资产仍保留：local/database、recon、archive、api_cache、universes、原P03试跑和samples/pilot_20261011。旧数据是否可用于其他用途，以[资产登记](../docs/governance/ASSET_REGISTER.md)为准；不因旧或当前未训练而删除。

正式UU执行数据集、拟合模型和净收益证据仍未完成；已有回顾样本与固定基准不等于正式交易准入。历史available_at未知、来源量额空值与推算口径分别保留。

local整体忽略，不把库、响应、截图、登录信息或实验加入Git。私有文件/目录版本见local/manifests/workspace-layout-1.0.json；公开样本见[统一清单](../docs/governance/FILE_CATALOG.json)。凭证只登记保护状态，不读内容或记录哈希。文字交接统一在docs/local/progress，运行元数据随数据保留。
