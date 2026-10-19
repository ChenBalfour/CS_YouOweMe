# 次时代预测图与基准评估

版本 forecast-dashboard-1.1，绘图组件 forecast-charts-1.1，2026-10-19，北京时间。

打开 [VS Code Notebook](../../scripts/notebooks/cyrex_forecast_dashboard.ipynb)，选择 Python 3.11+ 内核并按顺序运行。默认 `RUN_EVALUATION=False`，只读展示已有离线评估；不联网、不采集、不下单。画图使用 matplotlib，当前本机环境可用；若内核提示缺少该包，先选已安装 matplotlib 的内核。

## 运行与更新

1. 首次没有评估结果时，将 `RUN_EVALUATION=True`，运行“读取或新建评估”单元格。
2. `CANDIDATE_ID=None` 使用最新日级候选，也可指定已有候选目录编号。每轮评估另建版本，旧输出不覆盖。
3. 运行后续数字和绘图单元格，即可查看这轮的指标及两张图。该入口执行固定规则比较，没有训练深度模型。
4. 日后先完成 SteamDT 有限 daily 采集、日级候选构建，再在此新建评估；新采集不会自动改写旧候选或旧预测。

## 两张图如何读

**测试期目标图**的横轴为七日目标截止时刻，预测来自各目标日前七天。展示真实来源目标、validation 选定规则和不变价基准，下面附选定规则误差。规则选择只用 validation；test 用于锁定后的比较，不能看完 test 再改规则却沿用同一次测试成绩。缺日期时曲线断开。

**历史与未来路径图**展示起点前最多28天小时收盘，以及 day 0～7 的固定规则日点。源小时以 bucket+1h 表示收盘截止，与每日时点一致。历史缺小时断线；未来没有真实价格就不绘制真实线。日点之间连线仅展示规则推导，不制造未来小时波动，不代表置信区间。

图中分开显示研究起点与实际生成时刻。比如固定研究起点为10:00，但源数据实际在12:31收到，这属于之后生成的回顾示例，不能声称10:00已经发出真实预测。历史 available_at 仍未知，来源修订也不能直接视为过去已知值。

## 显示参数

| 参数 | 作用 |
| --- | --- |
| `LOOKBACK_DAYS` | 历史图显示1～28天，默认28 |
| `FORECAST_ORIGIN_BEIJING` | 默认 `None` 使用最近保存研究起点；可填已有完整候选时点，如 `2026-10-12T10:00:00+08:00` |
| `TEST_START_TARGET_BEIJING` | 测试目标图起点，含端点；`None` 显示全部 |
| `TEST_END_TARGET_BEIJING` | 测试目标图终点，含端点；`None` 显示全部 |
| `SAVE_CHARTS` | 默认 False，仅Notebook显示；True导出独立PNG与哈希清单 |

自选历史研究起点只调用评估中已经锁定的同一规则，读取候选的过去特征；不重新选择规则，不使用未来标签预测。该功能用于查看路径，不构成一份当时发出的历史预测记录。

## 文件与接口

源码位于 `scripts/research/visualization/forecast_charts.py`。绘图模块没有数据库写入、网络或训练入口。

```python
from scripts.research.evaluation import baseline_report
from scripts.research.visualization import forecast_charts

manifest = baseline_report.status()
plots = forecast_charts.figures(manifest, lookback_days=28)  # 只读，不写盘
saved = forecast_charts.render(manifest)  # 新建独立图表目录，不覆盖
```

评估输入为 `history.csv`、`forecast.csv`、`test_predictions.csv` 与 `metrics.json`；按评估 manifest 的路径和已登记哈希检查。自选起点额外核对该评估绑定的候选 manifest、`samples.csv` 与 `source_hourly.csv`。导出位置为 `data/local/reports/baseline_charts/<新编号>/`，包含 `holdout.png`、`projection.png`、`source/`源码快照和 `manifest.json`。快照登记绘图模块与本地包初始化文件；自选起点时还保存实际使用的基准预测模块及其包初始化文件。manifest的`source_files`和`outputs`分别登记源码和全部输出哈希。图表不追加到已冻结评估目录，旧版图表不改写。

## 当前能力

参考价格预测不等于实际解锁后的出售净额。历史可得时间、UU实时匹配报价、费用、结算和实际解锁状态没有在本页完成核验；不得把历史截图当当前报价或据此输出确定盈利。Notebook 保留“观察／执行数据不足”，模型是否有效先看留出误差，再由后续执行评估检验。
