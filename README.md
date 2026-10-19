# CS_YouOweMe

面向悠悠有品的 CS2 普通百元枪皮研究 demo：SteamDT 小时来源数据 → 七日参考价格预测 → UU 当前匹配报价与成本/实际解锁判断。已有七品小时库、次时代日级样本、固定基准评估和价格图；完整买卖决策仍待接入执行证据。

## 三个主文档

| 文档 | 用途 |
| --- | --- |
| [产品说明](docs/PRODUCT.md) | 目标、选品、七日CD退出策略和验收 |
| [产品架构](docs/ARCHITECTURE.md) | 当前数据流、功能包、存储和待建能力 |
| [当前进展与卡点](docs/PROGRESS.md) | 数据量、评估结果、验证、卡点和操作记录 |

## 现在主要用这三个 Notebook

| 顺序 | VS Code 文件 | 做什么 |
| --- | --- | --- |
| 1 | [steamdt_research.ipynb](scripts/notebooks/steamdt_research.ipynb) | 用户手动更新小时数据库、检查续采/覆盖 |
| 2 | [cyrex_daily_samples.ipynb](scripts/notebooks/cyrex_daily_samples.ipynb) | 从已保存数据离线生成日级候选版本 |
| 3 | [cyrex_forecast_dashboard.ipynb](scripts/notebooks/cyrex_forecast_dashboard.ipynb) | 读取或明确新建基准评估，显示历史、七日路径和测试误差 |

默认不启动采集/新评估。已有本轮结果时，第3个 Notebook 直接运行全部即可看图。各轮输入与输出另存在本地；Notebook不是唯一存储。见[采集说明](docs/usage/STEAMDT_RESEARCH.md)、[样本规范](docs/data/CYREX_DAILY_SAMPLES.md)、[图表说明](docs/usage/FORECAST_DASHBOARD.md)。

初次验证选择了“价格持平”，当前趋势外推没有超过它。来源预测不是可成交价或净利润；尚未拟合深度模型，没有自动买卖。

## 文件分工与版本

| 目录 | 内容 |
| --- | --- |
| [scripts](scripts/README.md) | Notebook、薄入口、按data/models/evaluation/visualization分工的research包及冻结采集核心 |
| [data](data/README.md) | 私有小时SQLite、原始响应、UU快照、候选、评估与图表 |
| [docs](docs/README.md) | 三大主文档、字段、使用、治理及历史附件 |

冻结核心 **0.3.5（本地未发布）**；独立组件分别版本化。文件/目录用途与SHA-256见[索引](docs/governance/FILE_INDEX.md)和[清单](docs/governance/FILE_CATALOG.json)。已有原始证据、用户Notebook输出和冻结运行保留；只清理有依据的缓存或冗余。

本轮相关离线检查：

```powershell
python -B -m unittest scripts.tests.test_research_samples scripts.tests.test_research_baselines scripts.tests.test_forecast_charts -v
python -B scripts/manage_assets.py --check
```

UU补充入口见[纯脚本说明](docs/usage/UU_DIRECT_COLLECT.md)、[历史图表Notebook](scripts/notebooks/uu_history_collect.ipynb)。登录信息仅由用户本地维护，不贴聊天或加入Git。采集由用户显式本地运行，不代启动持续采集、后台/定时服务。仅保存本地Git版本，新增远程推送、PR和release暂停。

原创代码与文档采用[MIT](LICENSE)。第三方数据及商标权利归其权利人。
