# 七品小时数据清洗：字段与运行

版本 steamdt-cleaning-guide-1.1；2026-10-20。组件steamdt-hourly-cleaning-1.0，规范steamdt-cleaning-spec-1.0。[方法调研](../research/DATA_METHODS_20261019.md)说明近期论文、采用理由与后续对照。

## 使用

打开[steamdt_cleaning.ipynb](../../scripts/notebooks/steamdt_cleaning.ipynb)，选择Python3.11+内核，直接运行全部查看已生成结果。默认RUN_CLEAN=False，不联网、不构建、不训练。需要新清洗版本时，先完成来源有限更新，再显式改True运行构建单元格；已有目录不覆盖。

```powershell
python -B scripts/clean_steamdt_data.py status
python -B scripts/clean_steamdt_data.py build --workspace research_20261016_v1
```

实现位于scripts/research/data/clean_hourly.py，入口只做委托。原库mode=ro，从保存报告的请求上限和完整小时截止冻结来源版本，保留当时规范、registry、报告和实际代码依赖；清洗前后原库/WAL哈希必须一致。

## 输出

位置为data/local/datasets/steamdt_clean/具体ID，latest.json只指向具体冻结版。

| 文件/表 | 内容 |
| --- | --- |
| clean.sqlite / source_versions | 请求上限内的全部七品来源版本，保留原始数值与修订，不因去重删除旧值 |
| clean.sqlite / source_requests、items | 请求与raw哈希追溯、精确商品映射和历史起点 |
| clean.sqlite / hourly | 逐规格/小时唯一网格，保留合法价格、可空来源量额、mask、信息年龄和诊断 |
| clean.sqlite / input_quality_windows | 只用过去的28日价格覆盖和最近24h完整度；不是训练资格或预测特征 |
| clean.sqlite / valid_observed_prices | 真实已观测且价格合法的只读视图，仍保留大涨跌 |
| gaps.csv | 首次观察前、内部缺口、尾部缺口分别登记 |
| flagged_hours.csv | 版本/时间偏移/价格事件诊断，不等于错误或操盘 |
| quarantine.csv | 非法价格/OHLC/量额的来源版本链接，原值留在source_versions |
| quality_report.json、report.md | 七品数量、缺失、事件与输入质量候选计数 |
| source、protocol_locked.json、manifest.json | 准确源码/规范/方法/来源快照、规则先行冻结及输出哈希 |

不重复导出全部小时CSV以减少空间。数据库读取仍用mode=ro；不要用原采集Store初始化清洗库。

source_requests.raw_path仍相对原研究工作区，按manifest.source_database的父目录定位；本版保留引用与哈希，不复制所有原始响应。历史价格不因超出当前选品价格带而删除，避免把历史变化筛掉。

## 缺失与真实极端行情

网格从每品登记起点到报告截止，不改变已经收到的价格。observed=0表示无来源小时；price_valid=0也可能是观察存在但价格非法，二者分开。open/close/high/low及量额缺失均为NULL；volume_missing/turnover_missing表明未知，来源明确0仍保留0。

price_age_hours是距最近有效来源小时的距离，首个有效价格前为空。missing_kind区分首次观察前与内部缺口，只作审计，不作为预测输入；source_version_id、source_request及version_count同样是追溯信息，不自动作为特征。

相邻小时涨跌≥30%、单小时振幅≥30%、过去168h相邻收益median/MAD分数≥6只标记不删值。MAD参考至少48个过去收益，不含当前收益；MAD=0留空分数，不人为加分母，缺小时不跨缺口算一小时收益。这些阈值是预设工程候选，不是数据驱动认定操盘、市场情绪或异常概率。

非法的非有限/非正价格、OHLC矛盾使该小时清洗价格为空，raw值及版本链接保留；非法量额单独置空，不抹掉合法价格。身份或时间桶结构不符则停止构建，避免擅自搬动价格。

## 与特征工程的边界

input_quality_pass暂用过去28天有效价格覆盖≥95%且最近24小时完整，同时保留strict_input_complete作完整窗口对照。它不生成x/y特征、标签，不意味着可训练或可交易；不按已看过的测试成绩调阈值。下游需要原生支持缺失或明确适配器，不能把NULL悄悄当0。

已增加[七品特征与标签](SEVEN_DAILY_SAMPLES.md)，显式读取这版数据库，独立生成21个过去特征与七日点/路径标签；清洗层仍不承担特征或训练。点目标与路径风险分别判断完整性，不假造缺失目标。旧Cyrex严格样本和预测Notebook保持原版；新规则效果仍需新评估与未来留出验证。历史available_at和UU执行价格/费用仍未验证，清洗不能解决这些缺口。
