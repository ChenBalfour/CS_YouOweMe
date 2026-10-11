-- 已观察范围，不等于全市场完整覆盖。
SELECT market_hash_name,platform,period,style,count(*) AS source_rows,
 count(DISTINCT bucket_time) AS observed_buckets,
 datetime(min(source_time),'unixepoch','+8 hours') AS first_beijing,
 datetime(max(source_time),'unixepoch','+8 hours') AS last_beijing,
 sum(source_volume IS NULL) AS null_volume_rows,
 sum(source_turnover_cny IS NULL) AS null_turnover_rows
FROM bars GROUP BY market_hash_name,platform,period,style;

SELECT market_hash_name,count(*) AS source_records,
 datetime(min(trade_time),'unixepoch','+8 hours') AS first_beijing,
 datetime(max(trade_time),'unixepoch','+8 hours') AS last_beijing
FROM trades GROUP BY market_hash_name;

SELECT market_hash_name,kind,period,state,pages,inserted_rows,
 datetime(start_time,'unixepoch','+8 hours') AS requested_start_beijing,
 datetime(end_time,'unixepoch','+8 hours') AS requested_end_exclusive_beijing,
 finish_reason FROM jobs ORDER BY priority,job_id;
