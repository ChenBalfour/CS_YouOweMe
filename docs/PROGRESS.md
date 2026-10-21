# 当前进展与卡点

版本 **progress-1.25**；2026-10-21（北京时间）。产品目标见[PRODUCT](PRODUCT.md)，实现见[ARCHITECTURE](ARCHITECTURE.md)。本页是当前成果、卡点和后续工作的唯一入口；每次操作后更新。10月14至19日的既往操作记录见[历史日志](releases/WORK_LOG_20261014_20261019.md)。

## 当前结论

**“七品小时库→清洗/特征标签→训练集缺失适配与缩放→本地训练→参数重载评估”已接通。** 用户已运行两轮真实CUDA实验：持平基线完成，四神经模型均在第一轮完成前因fp16梯度非有限停止，随后统一评估按partial状态拒绝。修复版[VS Code Notebook](../scripts/notebooks/seven_model_training_v1_1.ipynb)默认CUDA float32，保留数值检查；下一步重启内核后用新预处理/实验ID重新训练。数据不用重抓，尚无成功的真实神经模型成绩。

源样本`seven_daily_20261020_v1`保持冻结，3,346行中quality点任务可用3,009行，train1,714 / validation588 /旧探索test707。缺失适配和缩放只拟合train，选模只看validation；源training_approved=false不改，新实验单独记录用户本轮回顾研究授权。另保留旧次时代严格样本/固定规则/图表，其规则、数据和成绩不改；初次趋势规则未超过持平。

当前仍为L0来源研究。目标保持：SteamDT显式UU小时来源为主研究输入，UU补当前可匹配报价/数量/费用与实际解锁；每日判断、七日CD实际解锁后尽快退出。来源收盘不是自己的可成交卖价或净利润。

## 最新七品样本

父清洗版`seven_clean_20261019_v1`，完整小时截止 **2026-10-19 12:00**，没有代采新行情。每品每天北京时间10点，用此前28天672小时；七日点目标是t+168h前的完整小时来源收盘，路径风险另需完整未来168h。

| 项目 | 实际数量与含义 |
| --- | --- |
| 全部样本/输入 | 7品×478时点＝**3,346**行；**21**个x特征 |
| 点价标签 | 3,184成熟且终点真实；113终点缺失；49尚待未来成熟 |
| 完整路径标签 | 3,102可用；195中途或终点缺失；49未成熟；缺路径不抹掉有效点价 |
| 点价研究候选 | 严格输入 **2,815**，95%覆盖且最近24h完整 **3,009**，均已排除跨分组标签 |
| 路径研究候选 | 严格输入2,773，容缺2,965，独立于点价资格 |
| 容缺点候选分组 | train 1,714 / validation 588 / test 707；同日期跨品同组，7日标签隔离 |
| NULL与模型适配 | 3,009候选中21行部分x缺失；源NULL保留，新适配层用train median＋mask，树模型保留NaN |
| 空间与追溯 | 新产物约3.53MiB；SQLite/分离CSV、schema、4份准确代码、规范、父manifest及13份输出哈希 |

21项输入是参考价、1/3/7/14日收益、观察值MA比例、相邻真实小时log收益波动、范围/尾部、覆盖/最长缺口/年龄、同日其他品过去7日收益中位数/数量。量额、未来资格、修订编号和依赖未来判定的缺失类型不作x。没有插值、平滑、截尾、拟合标准化或删除真实大涨跌。

| 商品规格 | 全时点 | 严格点候选 | 容缺点候选 |
| --- | ---: | ---: | ---: |
| AK-47 燃料喷射器（久经沙场） | 478 | 427 | 454 |
| AK-47 流金王朝（久经沙场） | 478 | 253 | 285 |
| AWP 二西莫夫（久经沙场） | 478 | 427 | 454 |
| FAMAS 机械工业（崭新出厂） | 478 | 427 | 454 |
| Glock-18 核子花园（崭新出厂） | 478 | 427 | 454 |
| USP消音版 次时代（崭新出厂） | 478 | 427 | 454 |
| USP消音版 紫色DDPAT（崭新出厂） | 478 | 427 | 454 |

[样本Notebook](../scripts/notebooks/seven_daily_samples.ipynb)默认只读，运行全部查看摘要、最近状态和21输入；[字段与操作](data/SEVEN_DAILY_SAMPLES.md)。eligible表示本规范的研究候选；用户本轮已另行授权研究训练，仍不代表UU执行批准。历史available_at未知，旧test已查看仍仅探索，没有新前向留出。

## 既有成果与边界

| 模块 | 已完成 | 仍待核验/实现 |
| --- | --- | --- |
| 身份与采集 | 七品两平台ID；分页续采、去重、修订、SQLite/raw追溯；一次跨日22请求/105秒、每品补84小时 | 长期稳定，来源量额与实际UU订单统计，其他六品执行属性 |
| 来源缺口 | 次时代26小时源端缺口经同参/换窗核对；非DevTools折叠或本地丢失，用户页面也跳时 | 未穷尽所有网站端点；不假造缺行情 |
| 小时清洗 | 81,407源版本、81,397真实小时、84,924网格；缺失NULL/mask，29次≥30%涨跌全留 | 质量阈值效果；统计事件不认定操盘 |
| 新七品模型入口 | train-only预处理、8候选、保存/重载、validation选型、七品图；真实两轮已定位fp16梯度溢出，修复版默认CUDA float32 | 重跑真实完整训练、成绩与泛化增益、滚动验证及新前向留出 |
| 旧单品基准 | 421严格候选，验证选持平；测试68个MAE33.4232元、RMSE41.4195元、MAPE11.4933%；图表可查看 | 不是新七品模型成绩，不等于盈利 |
| UU补充 | 44828纯脚本历史7组单轮成功、1,360窗口记录；价格/在售数量各自真实频率保留 | 多品/多轮、统计、当前匹配ask/bid、费用与实际CD/结算 |
| 文件与版本 | scripts/data/docs；研究data/models/evaluation/visualization；源与实验私有、代码/文档独立版本 | 完整L1决策demo仍待接通和前向验证 |

## 当前卡点与下一步

| 优先级 | 工作与交付 | 验收条件 |
| --- | --- | --- |
| 1 | 重启内核，运行修复版Notebook：CUDA float32训练→保存参数→重载validation评估和七品图 | 记录完整实验ID/配置、成功失败、逐品误差与持平对照；没有结果前不预判冠军；不自动调旧test |
| 2：并行 | 用户显式每日有限daily更新、每周weekly复核，依次另建清洗和样本版本 | 检查新鲜度、失败停止、来源修订；旧版不覆盖；每周才更新一次不能提供每日新鲜输入 |
| 3：并行 | 补UU匹配报价/数量、费用和收货/解锁/出售/结算；核验历史available_at和量额语义 | 不用今天盘口回填过去；费用未知不当0，来源上涨不直接变买入建议 |
| 4 | 评估严格/容缺、滚动时间验证、期间风险与区间，再接UU成本情景和前向决策账本 | 不将七日点预测画成真实未来路径；候选/观察/数据不足可追溯；记录CD内不能卖、解锁等待、未成交和结算 |
| 5 | 再验收可选预训练模型、更多价格带/商品与正式发布 | Chronos本地adapter尚无真实权重验证；扩展先有新留出增益、明确请求/存储预算；不保证深度方法更准或每天都有进出 |

## 2026-10-21 CUDA梯度溢出修复

- 故障：用户的`fit_20261021T111644Z_a24b27`和`fit_20261021T111957Z_64421d`均为partial；持平基线成功，DLinear/LSTM/Transformer/门控模型均因gradient norm non-finite停止，epochs_completed=0，没有完成的神经权重。评估的Incomplete experiment是后续拦截信息。
- 原因：v1默认CUDA fp16 AMP，在GradScaler正常回退scale前就用严格裁剪抛错；此前4条合成样本没有覆盖真实训练范围的该问题。
- 修复：seven-neural-1.1默认CUDA float32，amp_float16需显式选择；AMP溢出跳过更新/降低scale并记录，float32保留有限性检查和失败停止。另建`seven_prep_20261021_v2`和`seven_model_training_v1_1.ipynb`，新实验自动ID，旧运行/预处理/Notebook及原始数据不覆盖。
- 验证：190项离线测试全部通过，用时27.138秒。4模型在CUDA float32下各用64条train/16条validation、1epoch/batch8完成；每模型8次optimizer更新、0跳步，保存重载预测有限。记录在私有repair_20261021_v1/real_cuda_diagnostic.json；这些短轮只验证数值与存取流程，不是模型优劣证据。
- 默认入口：修复版Notebook7个代码格在prepare/train/evaluate/写盘/网络拦截下通过，0违规、0数据库连接，交付保存输出为空；seven_prep_20261021_v2已成功且与冻结源码一致。旧运行保留核对另随本轮私有验收记录。
- 版本：seven-training/spec/neural及Notebook/使用说明1.1；product-1.17、architecture-1.18、progress-1.25。
- 保留核验：本轮两次实验、原v1预处理和两份原Notebook共82项字节/哈希全部不变；新v2运行源码校验通过。
- 用户下一步：重启VS Code Notebook内核，打开修复版，设RUN_CUDA_TRAIN=True和RUN_EVALUATE=True，其余开关False，再运行全部。无需重抓、重清洗或删除旧实验；成功后保存新EXPERIMENT_ID/REPORT_ID。
- 边界：本轮不代跑完整训练、不评分旧test、不修改冻结样本；可靠风险区间、新前向留出和UU执行收益仍未验收。

## 2026-10-21 本轮操作记录

- 任务：用户授权缺失适配、特征缩放、模型实现和评估；交付本地Notebook，长时间训练由用户显式运行，模型参数留本地。
- 成果：新增training_data/model_preprocessing、CPU classical、CUDA neural、seven_training、薄CLI、固定训练规范和[训练说明](usage/SEVEN_MODEL_TRAINING.md)。真实预处理版`seven_prep_20261021_v1`已完成，只拟合1,714行train的输入适配/缩放，validation588、旧探索test707不参与拟合。Notebook所有prepare/train/evaluate/test开关默认False；原库、旧样本/基准、用户原Notebook输出保持。
- 数据适配：样本/父清洗全部输出与源码快照哈希、schema/规范、SQLite完整性和split/purge只读校验；表格49列（21缩放＋21mask＋7品），树输入28列（21原NaN＋7品），672h序列为3数值＋3mask。median/mean/std只拟合train，原始NULL和真实跳变不改。
- 模型与保存：CPU持平/Ridge/有界ARIMA/LightGBM；CUDA DLinear/LSTM/Transformer/门控cross attention。门控模型借鉴毕设但重新联合训练，不读交通权重。参数、预处理、配置、源哈希、源码、环境和历史本地保存；仅完整实验进入重载评估，源码漂移或哈希不符拒绝，失败不自动重试。Chronos仅可选本地adapter，不在默认比较内。
- 验证：186项离线测试全部通过，用时26.939秒；包括数据适配4项合成测试和4个CPU/4个神经模型的合成验证。本机RTX3060 Laptop6GB、torch2.0.1+cu118、CUDA11.8实测4神经模型各4条672h合成样本、1epoch、batch2成功；GPU训练后CPU重载预测最大差约7.5e-8。这证明接口/CUDA/保存重载可运行，不代表市场预测准确。
- 验证脚本首轮把device_used误写为device，报告读取触发KeyError，当时DLinear训练本身已通过；修正验证脚本字段后四模型与重载对照成功，没有因此改动生产训练实现。源码漂移拒绝断言所在4项runner测试也再次通过。
- 默认安全性与保留：新Notebook7个代码格在prepare/train/evaluate/写盘/网络拦截下运行通过，违规0、数据库连接0，交付文件执行输出为空；1,198项旧保留资产与之前清单一致，用户旧Notebook输出未改。
- 实际数据：只读确认3,346行及1,714/588/707候选，完整小时仍截至10月19日12点；本轮没有采新行情，没有真实全量模型训练或新七品模型成绩。
- 版本：seven-training/data/preprocessing/spec/Notebook/使用说明各1.0；product-1.16、architecture-1.17、progress-1.24。文件清单、公开链接与凭证隔离按本轮收尾核验，旧历史记录不改。
- 剩余：用户运行真实训练并把实验ID/成绩用于后续分析；再补滚动验证、新前向数据、UU匹配报价/费用/CD和可靠风险区间。目前仍无自动买卖或已验证净收益。

## 2026-10-20 本轮操作记录

- 任务：用户授权接通清洗库到七品简单特征/标签，完成后说明结果并给VS Code步骤。
- 成果：新增seven_samples、冻结seven_daily_spec、薄CLI、新Notebook和字段说明；真实离线构建`seven_daily_20261020_v1`，父清洗1.0、源采集1.0和冻结核心0.3.5不改。
- 验证：15项独立合成测试通过，包含未来/跨品隔离、缺口不桥接收益、point/path分离、strict/容缺、purge、只读/哈希/拒绝覆盖/路径逃逸。测试首轮因合成fixture缺start_time失败，修正fixture后通过，生产实现未因此改动。
- 实际复核：不导入builder，从父库独立重算3,346行、70,266个特征值、43,498标签和20,076资格比较全部一致；父16＋新13输出哈希通过；1,198旧资产及源库/WAL、旧样本/评估/图和用户Notebook均未变。
- Notebook：5个代码单元格在构建/写盘/网络拦截下全部执行，3个展示、1次mode=ro连接、违规尝试0，保存文件仍为空输出。默认RUN_BUILD=False。
- 私有证据：`data/local/reports/seven_samples/connection_20261020_v1/`；新数据在`data/local/datasets/seven_daily/seven_daily_20261020_v1/`，不上传私有数据。
- 版本：组件/规范/Notebook/字段说明1.0；product-1.15、architecture-1.16、progress-1.23、management-1.6、asset-register-2.11。47份公开Markdown的439处相对链接无断链，文件/目录清单与凭证历史检查通过；测试临时子目录自动回收，遗留的一个空父目录已按计划清理。代码/文档沿既有GitHub分支迭代，最终远程状态见[PR检查页](https://github.com/ChenBalfour/CS_YouOweMe/pull/3/checks)。
- 剩余：新七品模型评估、NULL适配与前向留出，以及UU执行证据。本轮无市场请求、参数拟合或买卖输出。

## 上轮GitHub迭代

10月19日整理提交`856374f`、记录`f4e2e56`、CI修复`f683f39`已推送`planning/uu-research-reset`并建立[草稿PR #3](https://github.com/ChenBalfour/CS_YouOweMe/pull/3)。本地144项测试、远程Ubuntu Python3.11/3.13和Windows Python3.11三组通过；修复CI图表依赖及新克隆测试父目录。清理22个再生缓存、3个空缓存目录和两份可再生测试导出树，旧数据与用户输出保留；私有明细见`data/local/manifests/iteration_20261019_v1/`。公开分支不等于正式模型/交易release，不自动合并、强推或打标签。
