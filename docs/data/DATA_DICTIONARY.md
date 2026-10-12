# 数据字典

> 状态：legacy / unreviewed。此页描述旧技术试验，不代表已验收的 UU 研究能力；其中命令不作为本阶段执行任务。当前方向以 [主计划](../research/PLAN.md)与[资产登记](../governance/ASSET_REGISTER.md)为准。

开源样本与运行输出使用相同字段。`data/samples/pilot_20261011/` 的 `raw_path` 指向提取的 `.nuxt.json`，`raw_sha256` 校验该分发文件；样本额外的 `original_html_sha256` 保留原始整页 HTML 校验值。运行采集器产生的 `data/local/` 仍归档完整 HTML，并被 Git 忽略。

所有快照时间均使用 ISO 8601，包含 `+08:00`。价格计算使用 Decimal，CSV 输出十进制文本，避免浮点二进制误差。空单元格表示缺失或尚未确认；0 只保留在有定义的原始字段和计数中。

## 公共追溯字段

| 导出字段 | 含义 |
| --- | --- |
| run_id | 本项目的采集批次标识 |
| collected_at | 完成该页面/接口请求的北京时间，与来源更新时间分开 |
| source | public_html 或 official_api |
| source_url | 公开页面或官方接口地址，无 API Key |
| raw_path | 相对项目根目录的原始 HTML/JSON 路径 |
| raw_sha256 | 对原始文件字节计算的 SHA-256 |

关联规格表只使用公共字段中的 run_id、collected_at、source_url、raw_path 和 raw_sha256。

## items.csv

每行是一个主动访问的完整商品规格。联合键为 `(run_id, market_hash_name)`。

来源为公开详情页 `__NUXT_DATA__` 中返回成功的商品对象；展示价格及商品更新时间来自同页关联规格中名称完全匹配的条目。

| 字段 | 来源字段/规则 | 说明 |
| --- | --- | --- |
| item_id | itemId | 平台内部商品类型 ID，按字符串保存，不是 asset ID |
| market_hash_name | marketHashName | 精确英文市场名，是跨来源连接的主标识 |
| name_zh | name | 平台中文名 |
| weapon | 英文名解析 | 武器名 |
| skin_en | 英文名解析 | 涂装英文名 |
| quality | 英文名前缀解析 | normal / stattrak / souvenir |
| exterior | 英文名括号后缀 | 磨损档位，不是精确 float |
| rarity | rarityName | 平台稀有度标签 |
| display_sell_price_cny | 关联规格 sellPrice | 页面展示人民币在售价，非正数留空；不人为取各平台最低值替代 |
| item_updated_at | 关联规格 updateTime | 来源更新时间 |
| survive_count | surviveNum | 来源统计的存世量，不称作可交易流通量 |
| holders_count | holdersNum | 来源统计持有人数 |
| added_count | addNum | 来源新增量；公开字段未明确计算窗口 |
| estimated_trade_count_today | transactionCount | 页面显示“今日推算成交”；不得当作真实逐笔成交量 |
| turnover_rate_raw | turnoverRate | 原始换手率值；量纲/窗口待核实 |
| volume_ratio_raw | volumeRatio | 原始量比值；计算公式待核实 |
| diff_1day_pct_raw | diff1Day | 来源一天涨跌幅原值 |
| diff_7day_pct_raw | diff7Day | 来源七天涨跌幅原值 |
| diff_30day_pct_raw | diff30Day | 来源三十天涨跌幅原值 |
| diff_6month_pct_raw | diff6Month | 来源六个月涨跌幅原值 |
| analysis_tags_json | analysisTags | 来源分析标签的完整 JSON 文本，不执行其中 HTML |

涨跌幅列的 `_pct_raw` 记录来源命名对应的原始数字，没有自动除以 100 或重新计算。它们不是一段已采集历史价格序列。

## quotes.csv

每行是一个商品在一个平台的一条报价快照。联合键为 `(run_id, market_hash_name, platform)`。

公开页面使用 `sellingPriceList`；[官方批量接口](https://doc.steamdt.com/278832831e0)使用 `data[].dataList[]`，必须检查响应 `success=true`，不能把文档里的示例值当成真实数据。

| 字段 | 公开页 / 官方 API 来源 | 说明 |
| --- | --- | --- |
| market_hash_name | 主商品 marketHashName / data[].marketHashName | 与商品表连接 |
| platform | platform | 平台键统一大写，不合并平台 |
| platform_name | platformName / 未提供 | 平台展示名称 |
| platform_item_id | 未提供 / platformItemId | 平台商品 ID，字符串；公开页留空 |
| currency | 页面人民币展示 / 待实测确认 | 公开页为 CNY；官方模式默认留空，确认后可显式指定 CNY |
| raw_sell_price | price / sellPrice | 原始在售报价，保留 0 |
| sell_price_cny | 清洗 | 币种确定为 CNY 且原价为正才填入，否则留空 |
| has_positive_sell_quote | 原始在售价 > 0 | 1 有正数报价，0 无正数报价，不等于数据一定新鲜 |
| sell_count | 未提供 / sellCount | 来源在售数量；公开页留空，不用存世量替代 |
| raw_bid_price | 未提供 / biddingPrice | 来源求购价；公开页留空 |
| bid_price_cny | 清洗 | 币种确定为 CNY 且求购价为正才填入 |
| bid_count | 未提供 / biddingCount | 来源求购数量；公开页留空 |
| source_update_time_raw | updateTime | 保留来源 Unix 时间戳原值 |
| source_updated_at | updateTime 转换 | 支持秒及毫秒，0/无效时间戳留空 |
| quote_age_hours | collected_at - source_updated_at | 数据年龄，小时，保留 4 位小数 |
| is_stale_24h | 数据年龄 > 24 | 1 过期，0 未过期，无法算年龄时留空 |
| market_url | link / 未提供 | 来源给出的交易平台链接，只保存，不下单 |

后续若过滤可用报价，至少同时检查 `has_positive_sell_quote=1`、`is_stale_24h=0`、币种确认和来源时间有效。更新时间相差仍可能影响平台间比较。

## related_variants.csv

来源为每个主样本页面关联对象的 `all[]`。不同页面返回重复规格时，在本批只保留第一次观察，来源页面及时间保留，联合键为 `(run_id, market_hash_name)`。

| 字段 | 来源 | 说明 |
| --- | --- | --- |
| item_id | itemId | 内部商品类型 ID |
| market_hash_name | marketHashName | 精确商品规格名 |
| name_zh | name | 中文名；来源若只给英文，原样保留 |
| weapon / skin_en / quality / exterior | 英文名解析 | 与主表同规则 |
| raw_sell_price | sellPrice | 原始展示价格 |
| sell_price_cny | 清洗 sellPrice | 原值为正才填入 |
| survive_count | surviveNum | 来源存世量 |
| source_updated_at | updateTime | 来源更新时间 |

本表不含完整报价、持有人数、成交估算等字段，不能补到主商品表后宣称采集了 267 个完整商品。

## SQLite 和运行说明

`runs` 表保留每批 manifest。`items` / `quotes` / `variants` 表保留主键和完整 `payload_json`。同一商品在后续采集会产生新的 run_id，不覆盖旧快照。`data/local/latest_run.json` 只是一条最近运行指针，不代表历史全部数据。

原始资料仍是事实核对的依据。CSV、数据库和 manifest 的统计来自同批数据，保留失败信息。当前没有历史 OHLCV 表，K 线模式只归档原始响应，不猜测数组字段顺序。

导出表位于每批的 `tables/`，原始证据位于 `raw/`，manifest 和质量报告位于 `reports/`。完整目录与迁移说明见 [采集指南](../usage/COLLECTION.md)。
