-- 已有历史试采规格；替换为新名单规格可能尚无历史。
SELECT datetime(trade_time,'unixepoch','+8 hours') AS time_beijing,
 source_trade_id,platform_code,price_cny,wear_decimal,paint_seed,trade_num
FROM trades
WHERE market_hash_name='M4A4 | Buzz Kill (Factory New)'
 AND trade_time >= CAST(strftime('%s','2026-09-01T00:00:00+08:00') AS INTEGER)
 AND trade_time < CAST(strftime('%s','2026-10-12T00:00:00+08:00') AS INTEGER)
ORDER BY trade_time DESC LIMIT 50;

-- 同桶多次观察优先展示最近请求；原表保留所有来源时间。
WITH observed AS (
 SELECT *,row_number() OVER (
  PARTITION BY market_hash_name,platform,period,style,bucket_time
  ORDER BY source_request DESC,source_time DESC
 ) AS observation_order
 FROM bars
 WHERE market_hash_name='M4A4 | Buzz Kill (Factory New)'
  AND platform='ALL' AND period='1h' AND style=''
  AND source_time >= CAST(strftime('%s','2025-10-20T00:00:00+08:00') AS INTEGER)
  AND source_time < CAST(strftime('%s','2025-10-31T00:00:00+08:00') AS INTEGER)
)
SELECT datetime(source_time,'unixepoch','+8 hours') AS source_time_beijing,
 datetime(bucket_time,'unixepoch','+8 hours') AS hour_beijing,
 open_cny,close_cny,high_cny,low_cny,source_volume,source_turnover_cny
FROM observed WHERE observation_order=1 ORDER BY bucket_time;
