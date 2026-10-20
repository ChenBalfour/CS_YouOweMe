# 代码与运行入口

冻结采集核心0.3.5保持原版；当前研究包独立版本化。文件与目录用途、内容SHA见[统一索引](../docs/governance/FILE_INDEX.md)。

## 用户入口与功能包

1. [steamdt_research.ipynb](notebooks/steamdt_research.ipynb)：更新七品小时SQLite、查看任务和缺口；[操作说明](../docs/usage/STEAMDT_RESEARCH.md)。
2. [steamdt_cleaning.ipynb](notebooks/steamdt_cleaning.ipynb)：七品小时清洗、NULL/mask、事件和质量报告；[操作与字段](../docs/data/STEAMDT_CLEANING.md)。
3. [seven_daily_samples.ipynb](notebooks/seven_daily_samples.ipynb)：七品21特征、独立七日点/路径标签与样本资格；[说明](../docs/data/SEVEN_DAILY_SAMPLES.md)。
4. [cyrex_daily_samples.ipynb](notebooks/cyrex_daily_samples.ipynb)：冻结本地来源并构建次时代日级样本；[字段说明](../docs/data/CYREX_DAILY_SAMPLES.md)。
5. [cyrex_forecast_dashboard.ipynb](notebooks/cyrex_forecast_dashboard.ipynb)：基准评估、历史/预测图、测试误差；[图表说明](../docs/usage/FORECAST_DASHBOARD.md)。

清洗→七品21特征/独立七日标签已接通；下一步建立新七品评估。旧Cyrex样本/预测保留原版。新版交付Notebook默认关闭变更开关。用户已经保存的旧Notebook输出不清空。重启内核可加载本次包迁移后的代码。

## 按功能放实现

| 包/入口 | 职责 |
| --- | --- |
| research/data/clean_hourly.py | 清洗1.0：只读来源、规则小时网格、NULL/mask、真实价格保留和过去窗口诊断 |
| clean_steamdt_data.py、config/steamdt_cleaning_spec.json | 清洗薄入口与评分前固定规范；独立输出SQLite，默认status只读 |
| research/data/seven_samples.py、build_seven_samples.py | 新七品1.0：显式父清洗版本、过去21x、独立点/路径y、共同split/purge与不可变输出 |
| research/data/daily_samples.py | 样本组件1.1；只读小时快照、28天序列、七日标签和时间隔离 |
| research/models/baselines.py | 固定持平与3/7/14日趋势规则；没有训练参数 |
| research/evaluation/baseline_report.py | 校验候选、验证选规则、锁定测试与不可变评估 |
| research/evaluation/costs.py | 显式报价/费用的保本情景；缺参不当0 |
| research/visualization/forecast_charts.py | 历史、目标/预测、七日路径和PNG报告 |
| build_research_samples.py | 原样本CLI/API兼容薄入口 |
| evaluate_research_baselines.py | 离线评估薄入口 |
| steamdt_research.py | 采集组件1.0：registry、回补/增量、检查点、修订与导出 |
| config/ | 商品种子、样本/评估固定规范和受保护本地配置 |
| tests/ | 离线行为测试 |
| manage_assets.py、check_secrets.py、hooks/ | 逐文件版本与提交凭证检查 |

采集和研究使用Python3.11+标准库，图表另需Matplotlib。研究包从项目根导入；冻结核心仍位于src/cs_youoweme。源码准确快照由各轮清单保留，不能移动到旧运行里。

## UU与历史兼容入口

| 文件/目录 | 保留用途 |
| --- | --- |
| collect_uu_direct.py | 本地有限UU纯HTTP采集；登录配置仅由用户填写，见[说明](../docs/usage/UU_DIRECT_COLLECT.md) |
| collect_uu_charts.js、import_uu_chart_batch.py、review_uu_chart.py | 已登录页面历史图表、纯离线导入与指标核验 |
| notebooks/uu_history_collect.ipynb | 用户图表导出与入库 |
| observe_uu_24h.py、notebooks/uu_observe_24h.ipynb | 原有限连续观察/恢复；已有运行和输出保持 |
| collect.py、src/cs_youoweme/、sql/ | 旧采集核心、查询与恢复机制；仍被当前入口依赖 |
| pilot_uu_day.py、select_uu_research.py | 原有限试跑与选品调查 |
| verify_public_evidence.py、verify_uu_fields.py、review_uu_verification.py | 原来源/字段证据与冻结运行复核 |
| local/ | 私有准确运行源码，不提交Git |

这些入口仍有引用或证据用途，不能当垃圾删除。当前新研究实现集中在research包，不在Notebook重复堆计算代码。

修改后更新[进展](../docs/PROGRESS.md)、架构和资产清单。本轮针对性验证命令见根README；无需为画图重复跑市场请求或完整旧回归。
