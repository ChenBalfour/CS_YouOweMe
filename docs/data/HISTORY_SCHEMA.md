# 历史库口径

> 状态：legacy / unreviewed。此页描述旧技术试验，不代表已验收的 UU 研究能力；其中命令不作为本阶段执行任务。当前方向以 [主计划](../research/PLAN.md)与[资产登记](../governance/ASSET_REGISTER.md)为准。

`src/cs_youoweme/history/schema.sql` 是 SQLite schema；`user_version=2`。UTC 秒存储事件时间，时间边界与日聚合采用北京时间。`requests.collected_at` 单独保存 UTC 采集时间，不能用采集时间替代历史事件时间。早期库的成交任务从 `1h` 迁移为 `event`，保留任务 ID、游标和检查点；存在冲突任务时停止迁移供人工检查。

| 表 | 用途与关键字段 |
| --- | --- |
| catalog | 精确名称主键；category、weapon、skin、quality、exterior、family、SteamDT 编号、首次／最近目录发现、是否仍在来源目录 |
| platform_ids | 名称、平台、该交易平台编号；不会当作 SteamDT 编号 |
| styles | 同规格的多普勒相位 value、中文名、来源请求 |
| trades | 来源成交 ID、平台原始代码、秒级事件时间、价格、tradeNum、paintIndex、paintSeed、精确 wear_decimal、贴纸／相位 JSON、当时最低挂牌价、首次和最近请求 |
| bars | 规格／平台／周期／相位／来源时间；参考桶时间、网页 OHLC、来源成交量、来源成交额、请求编号 |
| snapshots | 候选补充与编号解析时的商品详情快照，供存世量、持有人和挂牌价审计 |
| universes | 名单内容 SHA-256 标识、原观察时间、入库时间、研究范围、完整规则 JSON |
| universe_members | 名单／规格主键、selected／reserve／rejected、顺序、分数、价格、供给、活跃度、热度排名和指标 JSON |
| jobs | 样本限定的日期任务、opaque 游标、页数、写入数、事件时间边界、状态与结束原因 |
| checkpoints | 已使用的游标，检测重复分页循环 |
| requests | 来源接口、无凭证请求参数、采集时间、HTTP／业务状态、私有 gzip 路径与解压后字节 SHA-256 |

## 成交精度与限制

网页真实字段 `wearFlot` 拼写如此。`wear_decimal` 保留来源十进制字符串；`wear_value` 浮点副本用于范围索引，不用于恢复原始精度。空字符串和 null 表示缺失。模板用 `paintSeed`，涂装编号用 `paintIndex`；同一市场规格可以有不同精确磨损、模板、贴纸与相位。

`platform_code` 保存来源的原始 0/1/2/3 等代码。网页将 1 展示为 Steam，其余展示为第三方；目前不把其他代码强行命名为 BUFF 或悠悠。`trade_num` 可为空或大于 1，因此一条来源记录不能一律断言为一个独立物品的交易。标准化表丢弃 `steamInfo`；私有原始响应可包含此对象。

价格用十进制 TEXT，币种依据网页请求 `x-currency=CNY` 与显示人民币。`min_sell_price_cny` 是成交时来源记录的最低挂牌价，不是本项目回填时看到的当前报价。来源可能修改既有记录，保留首末请求以便回查。

## 小时行情

网页客户端与实测返回确认数组顺序为 `[time, open, close, high, low, volume, turnover]`，1 对应小时，2 对应日。`typeVal` 使用 SteamDT 商品 ID，`maxTime` 向过去分页。官方开放 API 是另一接口，不把这套字段验证套用过去。

价格字段属于网页展示行情，不能直接说成逐笔成交构造的 OHLC；`ALL` 是来源总览口径。成交量和成交额保留为 **来源指标**，不保证覆盖全市场成交，也不等同于本地 `trades` 表的计数。未验证前不以 volume 的空值判断没有交易。

实测部分小时的原始时间偏离整点数秒，保留在 `source_time`，`bucket_time` 只作覆盖查询和显式聚合；报告统计偏移与同桶额外记录。原始 null 不填 0，价格不前向填充。最新桶可未完成。来源存在的数据获取异常、漏抓或口径变更，应与平台公告一起分析，不能因桶齐全就认为指标完整。

## 事件与研究时间

[Valve 公告](https://steamcommunity.com/games/CSGO/announcements/detail/516350567072662005)扩展了隐秘级物品兑换刀／手套的交易合同。Steam 官方新闻 API 返回该公告 epoch 为 `1761174020`，北京时间 **2025-10-23 07:00:20**。这是公告发布时间，不能自动等同于各商品崩盘开始时刻。本项目目标起点 2025-06-01，覆盖整个 2025 年 10 月；具体事件窗口在建模阶段再定义。

当前主力名单按今天的热度与供应选取，属于回顾性样本。未来论文复现与预测验证必须处理当时可得的样本选择、幸存者偏差、费用和可执行报价，不以本次数据采集给出购买决策。
