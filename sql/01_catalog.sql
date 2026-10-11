-- 版本和磨损独立，平台 ID 不代替 SteamDT ID。
SELECT name_zh,market_hash_name,weapon,skin,exterior,quality,steamdt_item_id,active
FROM catalog
WHERE category = 'weapon'
  AND (name_zh LIKE '%燃料喷射器%' OR name_zh LIKE '%流金王朝%')
ORDER BY market_hash_name;

SELECT category,count(*) AS specifications FROM catalog GROUP BY category;
