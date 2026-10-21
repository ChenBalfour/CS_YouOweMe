# CS_YouOweMe

面向悠悠有品的CS2普通百元枪皮研究demo：SteamDT小时来源数据→七日参考价格预测→UU匹配报价/成本与实际解锁判断。已有七品小时库、清洗/特征标签、本地CPU/CUDA训练与参数重载评估入口。预处理已准备，真实模型训练由用户在VS Code运行；完整买卖决策仍待UU执行证据。

## 三个主文档

| 文档 | 用途 |
| --- | --- |
| [产品说明](docs/PRODUCT.md) | 目标、选品、七日CD退出策略和验收 |
| [产品架构](docs/ARCHITECTURE.md) | 当前数据流、功能包、存储和待建能力 |
| [当前进展与卡点](docs/PROGRESS.md) | 真实成果、卡点、未来工作与验收；历史操作另归档 |

## 当前 Notebook 入口

| 顺序 | VS Code 文件 | 做什么 |
| --- | --- | --- |
| 1 | [steamdt_research.ipynb](scripts/notebooks/steamdt_research.ipynb) | 用户手动更新小时数据库、检查续采/覆盖 |
| 2 | [steamdt_cleaning.ipynb](scripts/notebooks/steamdt_cleaning.ipynb) | 只读查看或显式新建七品清洗版、检查缺口和事件 |
| 3 | [seven_daily_samples.ipynb](scripts/notebooks/seven_daily_samples.ipynb) | 查看七品21特征、七日点/路径标签、样本数量和待成熟状态 |
| 4 | [seven_model_training.ipynb](scripts/notebooks/seven_model_training.ipynb) | 显式运行CPU或CUDA训练，保存本地参数；重载评估并显示七品价格/预测/误差图 |
| 旧单品 | [cyrex_daily_samples.ipynb](scripts/notebooks/cyrex_daily_samples.ipynb) | 从已保存数据离线生成原严格候选版本 |
| 旧单品 | [cyrex_forecast_dashboard.ipynb](scripts/notebooks/cyrex_forecast_dashboard.ipynb) | 读取或明确新建旧固定基准评估，显示历史、七日路径和误差 |

默认不采集、不训练、不新建评估。新训练Notebook先保持全False运行全部检查，再打开一个CPU/CUDA训练开关和RUN_EVALUATE；操作见[七品训练说明](docs/usage/SEVEN_MODEL_TRAINING.md)。模型、预处理、准确源码与结果都留本地；以后评估只加载参数，不重新fit。旧Cyrex样本/评估保持原严格规范。另见[七品特征标签](docs/data/SEVEN_DAILY_SAMPLES.md)、[清洗说明](docs/data/STEAMDT_CLEANING.md)、[采集说明](docs/usage/STEAMDT_RESEARCH.md)、[旧图表说明](docs/usage/FORECAST_DASHBOARD.md)。

新入口提供持平/Ridge/有界ARIMA/LightGBM，以及DLinear/LSTM/Transformer/门控cross attention；已通过合成模型与3060 CUDA验证，尚无真实七品模型成绩。旧单品趋势规则未超过持平。来源预测不是可成交价或净利润，没有自动买卖。

## 文件分工与版本

| 目录 | 内容 |
| --- | --- |
| [scripts](scripts/README.md) | Notebook、薄入口、按data/models/evaluation/visualization分工的research包及冻结采集核心 |
| [data](data/README.md) | 私有小时SQLite、原始响应、UU快照、候选、评估与图表 |
| [docs](docs/README.md) | 三大主文档、字段、使用、治理及历史附件 |

冻结核心 **0.3.5（未打发布标签）**；独立组件分别版本化。文件/目录用途与SHA-256见[索引](docs/governance/FILE_INDEX.md)和[清单](docs/governance/FILE_CATALOG.json)。已有原始证据、用户Notebook输出和冻结运行保留；只清理有依据的缓存或冗余。

本轮相关离线检查：

```powershell
python -m pip install ".[test]"
python -B -m unittest discover -s scripts/tests -v
python -B scripts/manage_assets.py --check
```

UU补充入口见[纯脚本说明](docs/usage/UU_DIRECT_COLLECT.md)、[历史图表Notebook](scripts/notebooks/uu_history_collect.ipynb)。登录信息仅由用户本地维护，不贴聊天或加入Git。采集由用户显式本地运行，不代启动持续采集、后台/定时服务。公开代码/文档在`planning/uu-research-reset`分支迭代；私有数据和用户已保存的Notebook输出留在本地。分支上传不代表正式release或交易能力上线。

原创代码与文档采用[MIT](LICENSE)。第三方数据及商标权利归其权利人。
