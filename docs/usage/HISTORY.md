# 主力商品目录与历史采集

本阶段先做好数据系统，建模与论文复现后置。目标时间从北京时间 **2025-06-01** 开始。完整商品目录用于查询；只有明确选入样本的商品回填行情和成交，不默认采集全市场历史。

## 1. 同步轻量目录

```bash
python scripts/collect.py catalog sync
python scripts/collect.py catalog search --query "AK-47 Fuel Injector"
python scripts/collect.py catalog search --query "流金王朝"
python scripts/collect.py catalog search --category weapon --exterior "Field-Tested"
```

目录同步使用官方 API 和现有本地密钥，24 小时缓存一次；网页历史使用匿名接口，不读取该密钥。不得把官方 key 当作网页 access-token。可用 `catalog sync --source <本地官方基础目录响应.json>` 导入已下载文件。

2026-10-11 实测官方目录返回 44,502 个名称：武器皮肤 14,185、刀 3,422、手套 470、其他 26,425。这是来源当前列出的规格，不保证包含全部历史下架商品。普通、StatTrak、纪念品与磨损档均独立区分；平台商品编号与 SteamDT 编号分别存储，不能互换。

## 2. 用市场热度建立研究样本

“千百战”指百元、千元价位枪皮，不代表战痕磨损。当前名单只筛普通枪皮；刀、手套不进入本阶段研究样本。

```bash
python scripts/collect.py universe scan --output data/local/universes/qianbaizhan.json
```

初版从网站 `pvNums` 热度降序枪皮列表查询 2 页，最多补充 20 个候选的详情和近期行情，入选容量上限 12。数量不固定，资格不足不凑数；每涂装最多 2 个磨损档，每个价格层最多 8 个规格，避免千元层挤掉百元层。可用 `--candidate-pages`、`--enrich-per-sector`、`--max-items` 调整扫描预算。

价格区间为 `100 ≤ 最新第三方挂牌价 < 10000 CNY`，百元层为 `[100,1000)`、千元层为 `[1000,10000)`。至少一条一小时内更新的 BUFF、悠悠、C5 或 Halo 报价。热度限定候选后，在枪皮候选内部计算百分位：40% 热度排名、35% 低存世量、25% 近 7 天小时来源量的已知部分。近 7 天价格小时覆盖低于 80%、无已知成交活跃度、供给缺失等进入排除名单；缺失成交量仍为空，不视为零。持有人数和当日推算成交量也保留供检查，来源零值尚不能解释为真实无人持有或无成交。

输出保存入选、候补、排除原因、来源请求编号、筛选时间、分数与全部规则。这里的权重是可调整的研究规则，不是训练出的因子，也不是收益预测。网站未返回 `pvNums` 的绝对数值，不能把排名写成浏览次数。来源存世量不是全 Steam 账户普查；低存世量也不直接意味着有可执行的购买机会。

候选池有限，名单只代表本次扫描。用今天的热度挑样本回看 2025 年属于回顾性研究；不能把这份名单当作 2025 年当时已经知道的交易股票池。日后需要保存每次名单版本，并在训练、回测时采用当时可得的入选规则。

保存的旧观察可以离线重新筛选，不发生联网请求，也不把旧报价描述成重建时的最新报价：

```bash
python scripts/collect.py universe narrow --source data/local/universes/core_20261012.json --output data/local/universes/qianbaizhan_20261012.json
```

该示例源文件属于维护者本地数据，其他机器应改为自己的扫描输出。原观察时间和重建时间分别保留；名单及成员同时进入 SQLite，查询方法见 [数据库指南](DATABASE.md)。第一版选择摘要见 [UNIVERSE](../research/UNIVERSE.md)。

## 3. 明确名单后计划回填

```bash
python scripts/collect.py history plan --universe data/local/universes/qianbaizhan.json --start 2025-06-01 --end 2026-10-11
python scripts/collect.py history work --max-pages 100 --max-storage-mb 2048
python scripts/collect.py history status --limit 10
```

也可以逐个指定精确规格：

```bash
python scripts/collect.py history plan --name "AK-47 | Fuel Injector (Field-Tested)" --start 2025-06-01 --end 2026-10-11
```

日期型 `--end` 包含该北京时间整天；带时间的 ISO 值作为排他边界。省略结束时间会冻结本次执行时刻。**重复计划请使用同一个明确结束时间**，避免产生不同窗口的重叠任务；新一次时间窗口由使用者明确规划。相同精确窗口幂等。无 `--name` 或 `--universe` 的计划命令会拒绝运行。

默认两类任务是网页最细的 **1 小时行情**和**成交记录**。`--kind bars` 或 `--kind trades` 可只选一种；`--period 1d` 可选来源日线。默认平台 `ALL` 是网站总览；需要平台价差研究时，可以重复指定 `--platform BUFF --platform YOUPIN`，不要跨平台把 OHLC 合并成一次成交。多普勒商品从来源返回的相位目录增加独立行情任务，成交则保留每条记录的相位。

`--max-pages` 限定每次提交的历史页数，0 表示处理到队列耗尽。默认请求间隔 2.5 秒，最低 2 秒。容量限制默认 2 GiB，统计该数据库文件、WAL 和压缩原始响应；这是软上限，最后一页可能略微超出。CSV 导出、旧归档等文件不计入此限制。达到上限停止并保存检查点，不删除数据、不假装回填完成。

同一数据库只允许一个写入采集进程。分页成功后数据与游标在同一事务提交，成交按来源记录 ID 去重；重叠页可更新同一记录并保留首次、最近请求。小时行情按原始来源时间保留，异常偏移时间不会悄悄改写。每页响应有压缩归档和解压后 SHA-256，可审计。

网络错误保留游标，下次运行 `work` 继续。401、403、429、验证要求和来源 `success=false` 会停止并标为 blocked；查清原因后再用 `--retry-blocked`。不会自动绕过登录、验证或限制。Ctrl+C 后重新运行即可，操作系统锁随进程退出释放。

## 4. 查询与检查缺口

```bash
python scripts/collect.py history coverage --name "AK-47 | Fuel Injector (Field-Tested)"
python scripts/collect.py history trades --name "AK-47 | Fuel Injector (Field-Tested)" --start 2025-10-20 --end 2025-10-30 --wear-min 0.15 --wear-max 0.20 --limit 20
python scripts/collect.py history aggregate --name "AK-47 | Fuel Injector (Field-Tested)" --period 1d --start 2025-10-20 --end 2025-10-30
python scripts/collect.py history export --table catalog --output data/local/exports/catalog.csv
```

`coverage` 返回请求范围、已观察桶、缺失桶和连续缺口、缺失成交量／额、异常时间偏移及来源结束原因。任务 `done` 只表示来源分页结束或已经到达目标起点，不保证所有实际市场成交都被网站捕获。成交分页走完且返回空列表也不是全市场“零成交”的证明。

小时向 4 小时／日线属于向粗粒度聚合；无法从日线还原真实逐笔成交。聚合保留缺口和缺失指标：小时不全或任一成交量为空时，整段成交量不补零；只输出已观察时段价格。重叠小时采用最近请求的观察，原表保留全部来源时间。最后一个时段可能尚未结束。

默认数据库在 `data/local/database/market.sqlite`，目录、成交、行情、任务、检查点与请求分表保存；原始响应进入旁边的 `raw/`。所有新采集、名单和导出默认留在 Git 忽略目录；raw 可能包含来源公开展示的 Steam 账户信息，标准化成交表不保存 `steamInfo`，不得直接把 raw 上传到开源仓库。`--db` 在 `catalog`、`universe`、`history` 后、具体子命令前指定，且必须位于 `data/local/`。
