# UU 有限核验字段契约

版本 uu-field-contract-1.1；2026-10-14，北京时间。适用范围为 P03 的流金王朝久经、M4A1-S 印花集崭新有限核验，并补充用户截图揭示的求购属性限制。当前准入为 **L0 来源观察**；单件 UU 盘口、真实订单、成交结算及可执行退出尚未验收。旧 DATA_DICTIONARY/HISTORY_SCHEMA 保留历史意义，此契约不将旧字段升级为执行数据；本次没有修改解析代码或已有运行的契约快照。

## 身份、来源与时间

| 字段 | 类型/单位 | 来源及含义 | 缺失与限制 |
| --- | --- | --- | --- |
| market_hash_name | 字符串 | ITEM 返回并与请求精确相等的英文商品、版本、磨损 | 名称不符则拒绝解析，不混合磨损 |
| steamdt_item_id | 字符串 | SteamDT 的商品编号 | 与 UU template_id 不互换 |
| template_id | 字符串 | UU 商品链接中 gameId=730 下的 templateId | 本轮流金王朝 113014；印花集 46298；编号本身不是单件挂牌 ID |
| source / venue | 字符串 | 来源为 steamdt；明确的 YOUPIN/悠悠行归属 UU | 逐笔使用独立平台代码映射，不继承 K 线选择器 |
| source_run_id / source_request | 字符串/整数 | 原始请求的运行和编号 | 不同运行的编号可重复，联合使用 |
| raw_sha256 | SHA-256 | 原始响应字节校验 | 不对凭证做内容快照；原始响应保持私有 |
| observed_at_utc | 有时区 ISO 时间 | 客户端请求前的采集时间 | 与来源更新时间、事件时间分开；不假定采集就是历史可得时点 |
| source_update_time | Unix 秒 | 来源 updateTime，可能为 null | 大于 1 小时标 stale_over_1h；未来时间单独标异常，不更正原值 |
| source_time / bucket_time | Unix 秒 | K 线原始时间/显式小时桶 | 来源秒数偏移保留，不悄悄改成整点 |
| contract / code / schema version | 字符串 | 字段、解析、库结构的各自版本及内容哈希 | 不与工程发布版本或正式数据集 ID 混淆 |

当前抓取结果不能证明更早决策时点已能看到这些历史记录。P04 若用于预测，必须另审查历史修订和信息可得时间。

## 小时行情

请求 `/user/steam/category/v1/kline` 使用 `platform=YOUPIN`、`type=1` 和确切 itemId。七元数组的来源顺序为 `[time,open,close,high,low,volume,turnover]`，与既有解析一致。

| 规范字段 | 类型/单位 | 准入用途与规则 |
| --- | --- | --- |
| open_cny / close_cny / high_cny / low_cny | 非负 Decimal 文本，元 | 来源标称 UU OHLC；验证高低范围，仅支持 L0 价格观察 |
| source_volume | 可空非负整数 | 来源量字段；空值保留 null，不填 0。未确认真实成交计数、推算程度和缺失原因，不当实际成交量 |
| source_turnover_cny | 可空 Decimal 文本，元 | 来源额字段；空值保留 null。不能视为已结算款项或由其计算真实周转能力 |
| period | 1h | 固定小时颗粒度；不插值成逐笔或单件盘口 |
| source_time / bucket_time | Unix 秒 | 时间窗口左闭右开；本轮每规格 24 桶，原始接口批次 720 行，只保留指定日的 24 行 |

报告同时给出价格桶覆盖、量非空小时、额非空小时。价格覆盖 24/24 不意味着真实成交完整；量额缺失只能判定“响应为空”，尚不能判定无成交或来源未覆盖。

## UU 汇总市场快照

新增允许的只读端点 `/user/skin/v1/market-comparsion`，拼写沿用来源。商品页脚本调用该接口，侧栏用 platformMarket 显示在售与求购。确认 `platform=youpin`、`platformName=悠悠` 及 UU 商品链接后才赋予 venue=UU。

| 规范字段 ← 来源字段 | 类型/单位 | 含义与限制 |
| --- | --- | --- |
| source_sell_price_cny ← sellPrice | 可空 Decimal 文本，元 | 来源显示的在售价；未核验单件是否可买、属性及数量匹配，不保证立即成交 |
| source_bidding_price_cny ← biddingPrice | 可空 Decimal 文本，元 | 来源显示的求购价；未核验 float/贴纸等求购条件，不作为自己物品可卖价 |
| source_sell_count ← sellCount | 可空非负整数 | 来源在售数量；具体是单件数、有效挂牌数还是其他口径未知，不是此价格可买数量 |
| source_bidding_count ← biddingCount | 可空非负整数 | 来源求购数量；未核验订单数/待购件数及属性条件，不是此价格可卖深度 |
| source_update_time / age_seconds | 可空秒数 | 行级来源更新与采集时差；没有买卖两侧独立更新时间，不能证明同步 |
| quality_flags | 字符串数组 | 求购高于在售时标 crossed_source_quotes；缺失、零价、过期与未来时间各自标记，保留原值 |
| single_item_depth_verified / attribute_comparability_verified | 布尔 | 本轮均 false，即使没有异常标记也不能升级为已验收盘口 |
| execution_eligible | 布尔 | 本轮始终 false，不据汇总差价构造交易净收益或套利标签 |

`ITEM.sellingPriceList.price` 与比较接口 sellPrice 是不同请求、不同快照字段，分别保留来源时间。本轮流金王朝二者曾为 257.00 和 257.38 元，不能无声覆盖为同一个“最新价”。比较行中的 trendList 原样保存；其聚合和历史修订语义未核验，不进入正式执行标签。

ITEM 的 `consignmentBest`、`purchaseBest`、`purchaseStable` 等比例指标不当作求购价格或深度；`transactionCount`、存世与持有人指标也不当作 UU 实际流动性。

### 求购条件与属性匹配（1.1 补充）

2026-10-14 用户截图中印花集崭新的四笔求购均限磨损 0–0.01。`crossed_source_quotes` 只表示来源汇总求购高于来源汇总在售，可由属性范围或更新时间不同造成，不代表抓取价格错误或可成交套利。截图的拍摄时间、订单 ID 未提供，不能逐单解释旧接口快照；详见 [修订证据](../research/SELECTION_REVISION_20261014.md)。

| 待取得字段 | 类型/状态 | 必要解释 |
| --- | --- | --- |
| bid_min_wear / bid_max_wear | 可空 Decimal 文本；当前 unavailable | 求购允许的 float 边界；缺失不等于不限磨损 |
| bid_attribute_constraints | 结构化条件；当前 unavailable | 模板、贴纸及其他条件，分别记录未知、有限制、明确不限 |
| eligible_bid_price_cny / eligible_bid_quantity | 可空 Decimal / 整数；当前 unavailable | 针对某件实际属性匹配后的有效求购及待购件数，不能从汇总价/数量推导 |
| bid_eligibility | matched / not_matched / unknown；当前 unknown | 需要同规格、实际属性、完整条件和有效时间；截图没有标签不自动 matched |

这些是新增字段需求，不是现有 CSV/SQLite 已提供的列。若没有完整条件，应继续保留汇总报价与 unknown；普通版同一标准磨损档也不能默认全体相互可比。

## 来源逐笔及属性

端点 `/item/trade/v1/list` 请求 `hasSteam=-1` 表示混合来源，不接受 YOUPIN K 线选择器的隐含归属。当前网页成交表将代码 1 显示为 Steam，其余已观察代码 0/2/3 显示为三方平台；没有代码到 UU 的证据。来源说明将三方记录描述为根据挂牌指纹、Steam 库存等推算，不能认定为真实 UU 订单或结算。

| 字段 | 类型/单位 | 解释与处理 |
| --- | --- | --- |
| source_trade_id | 字符串 | 来源记录 ID；窗口内去重。跨平台相同 ID 的冲突必须报错，不能自动合并 |
| platform_code / venue | 原始字符串/分类 | 1→STEAM 来源显示；0/2/3→third_party_unknown；新代码→unknown。均不能直接映射为 UU |
| trade_time | Unix 秒 | 来源标注事件时间，未证明是实际成交、收货或结算时点 |
| source_price_cny / source_trade_num | Decimal 文本/可空整数 | 来源价格和数量；不作为 UU 订单金额或完整成交总量 |
| paint_index / paint_seed | 可空整数 | 来源涂装编号/模板字段；0 是已提供的值，不因网页 truthy 展示逻辑而判为缺失 |
| wear_decimal ← wearFlot | 可空 Decimal 文本，范围 [0,1] | 沿用来源拼写；从原始 JSON 数字解析 Decimal，保留可得精度，不人为四舍五入 |
| stickers_state | missing/null/empty_array/populated | 缺字段、显式 null、空数组和有内容分别保留。空数组仅说明该来源返回空数组，不证明单件没有贴纸 |
| source_sticker_count | 可空整数 | 响应数组元素数；贴纸信息原样留在私有 raw，尚未逐项验证 ID、磨损、位置与溢价 |
| source_min_sell_price_cny | 可空 Decimal 文本，元 | 来源“成交时在售底价”；平台、同步性及属性可比性未核验，不是可靠基准买价 |
| record_semantics / execution_eligible | 字符串/布尔 | source_observation_not_verified_order / false |

来源最后一页 nextId=null 只代表本次来源分页结束；total=null 时真实市场覆盖未知。分页重叠按 ID 去重，保留原始每页响应与最后请求。旧库中的金额字符串可能省略来源多余的尾零，核对按数值等价进行，原始数字词法仍保留在哈希响应，新导出按 Decimal 解析。

## 尚不可用的执行字段与准入

`listing_id`、单件 UU ask/bid price/quantity、两侧独立更新时间、求购匹配条件、单件锁定/可卖状态、订单 ID、购买收货时间、实际出售时间、结算/资金复用/提现时间、撤销处理与实际费用均 unavailable 或 unverified。不能由来源汇总、当前规则估计或其他平台记录回填。

L1 至少需要可比单件报价、有效数量、平台归属、信息可得时间和经核实的执行/资金规则，且有清楚的模拟假设；L2 还需实际订单和现金账本。此次字段契约交付完成，L1/L2 准入未通过。

证据与具体数值见 [有限试跑报告](../research/P03_VERIFICATION_REPORT.md)，执行时间与费用范围见 [规则核验](UU_EXECUTION_RULES.md)。
