# 七品本地模型训练与重载评估

版本 **seven-training-usage-1.1**；2026-10-21。入口为[seven_model_training_v1_1.ipynb](../../scripts/notebooks/seven_model_training_v1_1.ipynb)，实现与数据流见[架构](../ARCHITECTURE.md)，最新实测见[进展](../PROGRESS.md)。

## 现在怎样运行

1. 重启VS Code的Notebook内核，打开修复版seven_model_training_v1_1.ipynb，选择已有CUDA环境对应的Python内核。先保持所有开关False，运行全部，检查环境、v2预处理版本和样本数量；这一步不训练、不采行情。
2. 本次重跑配置格设`RUN_CUDA_TRAIN=True`、`RUN_EVALUATE=True`，其余开关False，再运行全部。CUDA默认float32；CPU基线可另轮单独打开RUN_CPU_TRAIN，一次只开一个训练开关。
3. 运行结束，保存打印的`EXPERIMENT_ID`和`REPORT_ID`。下面会显示validation成绩、七品真实目标/预测/持平对照、误差图，以及神经模型训练历史。
4. 把训练和评估开关改回False。以后只评估时，把旧实验ID填入配置的`EXPERIMENT_ID`，仅打开`RUN_EVALUATE=True`，无需重新训练。

默认`DATASET_ID="seven_daily_20261020_v1"`、`PREPARED_ID="seven_prep_20261021_v2"`，本次已准备好预处理版，只读加载即可。若以后换电脑或缺少本地私有产物，Notebook会提示显式prepare；已有ID不能覆盖，新数据/特征/预处理必须另建ID。prepare只拟合训练集的缺失适配/缩放，不训练预测模型。配置格重新执行会按填写值重置ID，所以单独重跑评估前要把已保存ID贴回去。

默认全部开关False，包括`RUN_EXPLORATORY_TEST`。旧test已经看过，继续评分只能探索，首轮不用打开它。

## 本次报错与恢复

两轮真实实验中，持平基线成功，四神经模型都在第一轮完成前因fp16梯度非有限停止；随后Incomplete experiment是评估对partial实验的拦截。旧轮没有完成的神经模型checkpoint，不能只跳过错误继续评估成神经模型成绩。

v1.1默认CUDA float32并保留有限性检查；AMP半精度改为显式可选，正常溢出时记录跳步/降低scale。修复后190项离线测试通过，四模型已在真实64条train/16条validation上各完成1epoch/batch8 CUDA数值及保存重载验证；这是有限诊断，完整训练和成绩仍需用户运行。请使用上面的新Notebook和v2预处理，新实验ID自动生成。旧Notebook、实验、参数和数据均保留；不用重抓数据或重新清洗，也不要修改旧manifest来绕过源码校验。

## 环境和模型

本机已验证Python3.11、torch2.0.1+cu118、CUDA11.8、RTX3060 Laptop6GB。环境检查应显示`cuda_available=true`和相同GPU；要留意Notebook的`sys.executable`。Notebook不会自动安装或替换CUDA包。CPU可选依赖见[pyproject.toml](../../pyproject.toml)的research部分，图表依赖见test部分；缺包先在选中的同一解释器环境补齐，再重新开始实验。

| 入口 | 候选 | 输入与选择 |
| --- | --- | --- |
| CPU | Persistence（持平） | 七日收益预测为0，始终保留作对照 |
| CPU | Ridge | 21项特征适配＋mask＋商品身份，验证选择固定候选alpha |
| CPU | 有界ARIMA | 各品训练历史价格；固定少量阶数，以训练AIC选阶，不无限搜索 |
| CPU | LightGBM | 21项原NaN特征＋商品身份，验证早停 |
| CUDA | DLinear、LSTM、小Transformer、门控LSTM–Transformer cross attention | 相同672h序列＋21项特征，MSE训练、validation收益MAE早停 |

CPU默认比较4模型，CUDA入口比较4神经模型并附持平。门控结构借鉴用户毕设，但这是本任务的新权重和联合训练，不导入交通预测权重。可选Chronos-2仅有本地权重适配器，尚未验证真实权重，不在默认训练或评分列表。

6GB显存默认CUDA float32、batch8、最多50epoch、patience8；每轮输出耗时。显式amp_float16不是本次重跑默认项。可先显式改为2epoch做自己的短轮，再以新实验ID正式运行；短轮不能用于判断模型优劣。若显存不足，失败信息会保留，确认后降低到batch4或2，新建实验运行；程序不会自行更换设备或自动重试。也不保证深度模型超过持平/简单模型。

## 数据、缺失与防泄漏

源清洗与样本版本冻结，完整小时截至2026-10-19 12:00。每品每日北京时间10点，用此前28天672小时，预测`+168h`前完整小时来源close；不是自己的成交卖价。

quality点任务共有3,009行：train1,714、validation588、旧探索test707。各品同日期同组，七日标签触及下一组分界的样本purge；不随机拆分。历史available_at仍未核验，旧test不是新的独立留出。

- 表格21项特征：仅用train拟合median填充，再用填充后的train拟合mean/std，附21个缺失mask和7个训练商品one-hot，共49列。树模型保留原NaN＋one-hot，共28列。
- 序列3项数值为log(close/reference)、相邻真实一小时log收益、log(high/low)，附3个缺失mask，共6通道。缺口不插值、不跨缺口计算收益，也不从未来补值。
- 全缺失训练列显式fallback0并保留mask，常量列scale1；这些只是模型输入适配，不写回源库。未知商品拒绝预测，需要新训练版本。
- y是未缩放的`y_return_7d`，预测价格为参考价×(1+预测收益)。输入仅取过去字段白名单，y/target/未来资格不喂给模型。

fit只接受eligible、非purged的train行。validation/test只transform；选择只依据validation收益MAE。当前固定日期划分已实现，滚动验证、新前向留出、风险区间和执行成本评估仍待后续完成。

## 文件保存在哪里

| 位置（相对项目根） | 内容 |
| --- | --- |
| `data/local/datasets/seven_daily/<dataset_id>/` | 原samples.sqlite、features/labels、schema、父清单和准确生成源码，保持冻结 |
| `data/local/artifacts/seven_training/prepared/<prepared_id>/` | 预处理JSON（特征/序列顺序、item编码、训练行键）、训练规范、源/父/schema哈希引用和源码快照 |
| `data/local/artifacts/seven_training/experiments/<experiment_id>/` | 模型参数、预处理副本、规范、环境、训练历史、进度、验证选择和哈希清单 |
| `data/local/reports/seven_training/<report_id>/` | scores.json、逐模型预测CSV、七品PNG、report.md和独立manifest |

全部保存在被Git忽略的本地目录。SQLschema仍在原不可变dataset中，训练产物按哈希引用，不重复拷贝。Notebook不是唯一存储；关闭Notebook不会丢掉已完成模型，原始来源数据也应保留，用于复算、修订、续采和追溯。

加载会校验输出哈希和源码快照；当前运行源码与冻结实验不符即拒绝。应恢复兼容Git版本再读取，或者以新ID重建预处理/实验，不能修改旧manifest“绕过”。评估仅加载参数和预处理器，`fit_calls=0`，不重新训练或更新均值方差。

单个模型失败会记录错误，其他明确请求的模型继续；最终manifest说明完整、部分失败或失败，不自动重试。统一评估要求完整实验，部分失败时先检查原因，再以新实验ID显式运行。训练中断会保留已写进度，不把它当完整实验；本版不提供训练中途续跑，采集断点续传是另一机制。

## 图和结果怎样理解

图横轴是七日后的目标时刻，每个预测点由七日前的输入生成。真实目标线、模型预测线和持平线对照；缺日期保持断线，下面画价格误差。它不是对未来168小时每小时路径的预测，也没有校准可靠区间。

报告同时给出收益MAE、价格MAE/RMSE、MAPE、偏差、方向正确率和逐品分数；验证表现用于选型。七日标签重叠、商品相关，不能把这些样本当作独立交易，也不能用来源价格上涨推断已经盈利。UU匹配买卖报价、费用、实际收货/解锁/成交/结算仍需另外接入。

## 命令行备选

项目根PowerShell可先检查环境：

```powershell
python -B scripts/train_seven_models.py environment
```

已有预处理版本时，显式训练与重载评估：

```powershell
python -B scripts/train_seven_models.py train --prepared-id seven_prep_20261021_v2 --models persistence ridge auto_arima lightgbm --device cpu
python -B scripts/train_seven_models.py evaluate --experiment-id <上一步打印的实验ID>
```

新建预处理需显式新ID：

```powershell
python -B scripts/train_seven_models.py prepare --dataset-id seven_daily_20261020_v1 --prepared-id <新的预处理ID>
```

尖括号内容需替换，不能直接照抄。已有ID不覆盖，所有训练由用户主动启动。
