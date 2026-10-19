# 文档索引

## 三大主文档

1. [产品说明](PRODUCT.md)：目标、用户流程、范围、策略与验收。
2. [产品架构](ARCHITECTURE.md)：实际实现、数据流和待建能力。
3. [当前进展与卡点](PROGRESS.md)：当前成果、卡点、未来工作及逐项验收。

每次操作完成更新进展，相关产品或架构变更同步对应页面。下面仅为专项附件，不另立当前状态。

| 专项 | 入口 |
| --- | --- |
| 选品规则与历史调查 | [计划](research/SELECTION_PLAN.md)、[报告](research/SELECTION_REPORT.md)、[百元修订](research/SELECTION_REVISION_20261014.md) |
| 来源与执行证据 | [P03计划](research/P03_VERIFICATION_PLAN.md)、[有限报告](research/P03_VERIFICATION_REPORT.md)、[字段](data/UU_FIELD_CONTRACT.md)、[规则](data/UU_EXECUTION_RULES.md)、[历史图表](data/UU_HISTORY_CHART.md) |
| 预测、误差与可视化 | [新Notebook](../scripts/notebooks/cyrex_forecast_dashboard.ipynb)、[操作与图表说明](usage/FORECAST_DASHBOARD.md)；固定基准已评估，默认读取已有结果 |
| 七品清洗和方法调研 | [Notebook](../scripts/notebooks/steamdt_cleaning.ipynb)、[字段/用法](data/STEAMDT_CLEANING.md)、[近期一手方法与采用方案](research/DATA_METHODS_20261019.md)；新特征工程尚待接入 |
| 次时代日级研究候选 | [字段与使用说明](data/CYREX_DAILY_SAMPLES.md)、[离线Notebook](../scripts/notebooks/cyrex_daily_samples.ipynb) |
| SteamDT小时研究库 | [VS Code Notebook](../scripts/notebooks/steamdt_research.ipynb)、[商品清单/续采/去重说明](usage/STEAMDT_RESEARCH.md) |
| 用户本地运行 | [连续观察计划](research/P03_OBSERVATION_PLAN.md)、[VS Code说明](usage/OBSERVE_24H.md)、[Notebook](../scripts/notebooks/uu_observe_24h.ipynb) |
| 用户图表导出 | [Edge复制响应与离线核验](usage/UU_CHART_EXPORT.md)、[字段和实际间隔](data/UU_HISTORY_CHART.md) |
| UU历史批量采集 | [登录页面采集与入库步骤](usage/UU_HISTORY_COLLECT.md)、[新Notebook](../scripts/notebooks/uu_history_collect.ipynb)；真实稳定性待用户试跑 |
| 文件与版本 | [制度](governance/FILE_MANAGEMENT.md)、[逐项索引](governance/FILE_INDEX.md)、[清单](governance/FILE_CATALOG.json)、[清理恢复](governance/ORGANIZATION.md) |
| 历史操作 | [2026-10-14至19日工作日志](releases/WORK_LOG_20261014_20261019.md)；历史指示不覆盖最新授权 |
| 资产与工程 | [资产登记](governance/ASSET_REGISTER.md)、[贡献说明](governance/CONTRIBUTING.md)、[凭证保护](governance/SECURITY.md)、[版本历史](releases/CHANGELOG.md) |

旧 PLAN/STATE/HANDOFF 是兼容导航。旧数据库和使用说明保留其技术参考用途；历史总结、旧加权名单及重复发布说明已从工作目录移除，清理前 Git `babb125` 保留完整原文。私有原始证据和精确源码版本不公开。
