-- 最新保存的枪皮名单，观察时间与入库时间分别保存。
WITH latest AS (
 SELECT universe_id,observed_at FROM universes
 WHERE scope = 'weapon' ORDER BY saved_at DESC,universe_id DESC LIMIT 1
)
SELECT datetime(l.observed_at,'+8 hours') AS observed_beijing,
 m.rank_order,c.name_zh,m.market_hash_name,m.role,m.selection_score,
 m.price_cny,m.source_supply,m.known_7d_volume,m.source_heat_rank,
 json_extract(m.metrics_json,'$.price_band') AS price_band,
 json_extract(m.metrics_json,'$.missing_volume_hours') AS missing_volume_hours
FROM universe_members AS m
JOIN latest AS l ON m.universe_id=l.universe_id
JOIN catalog AS c ON c.market_hash_name=m.market_hash_name
WHERE m.role='selected' ORDER BY m.rank_order;
