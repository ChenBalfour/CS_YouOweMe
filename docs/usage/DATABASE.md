# 数据库与 VS Code

历史库是 **SQLite 本地文件**，可以直接用 SQL 查询，不需要服务器、端口、账号或密码。

当前维护工作区的路径：

```text
F:\Codex\CS_YouOweMe\data\local\database\market.sqlite
```

其他机器对应仓库下的 `data/local/database/market.sqlite`。公开仓库不包含该库，克隆代码不会获得维护者的本地行情。

## 在 VS Code 连接

1. 安装 **SQLTools**（`mtxr.sqltools`）和 **SQLTools SQLite**（`mtxr.sqltools-driver-sqlite`）。
2. 驱动需要 Node.js 14+ 和 npm；将 `sqltools.useNodeRuntime` 设为 `true`。首次连接时驱动会提示安装 SQLite 运行依赖。采集程序仍只需要 Python。
3. 用“文件 → 从文件打开工作区”打开 `config/vscode.code-workspace`，其中已提供数据库相对路径和扩展推荐。
4. 左侧 SQLTools 面板连接 **CS_YouOweMe Local**，展开 Tables 查看表。手动创建连接时选择 SQLite，Database 填上面的完整文件路径。
5. 打开 `sql/` 中的文件，绑定该连接，通过 SQLTools 查询命令执行选中的语句；每条语句以分号结束。也可以在连接生成的 SQL 会话文件中粘贴执行。

步骤与驱动要求依据 [SQLTools 官方入门](https://vscode-sqltools.mteixeira.dev/)和 [SQLite 驱动说明](https://vscode-sqltools.mteixeira.dev/en/drivers/sq-lite.html)。Node 自动识别失败时，将设置改为本机 `node.exe` 完整路径；官方说明也列出 Windows 终端配置方法。

## 查哪些表

| 表 | 用途 |
| --- | --- |
| catalog / platform_ids | 中英文名称、磨损档、版本与平台编号 |
| universes / universe_members | 名单版本、入选／候补／排除、分数与观察时点 |
| trades | 成交 ID、事件时间、价格、精确磨损、模板、贴纸和相位 |
| bars | 网页行情、来源量额、周期与平台 |
| jobs / checkpoints | 回填窗口、已提交页数、分页游标和状态 |
| requests / snapshots | 请求来源与详情快照 |

```sql
SELECT name_zh, market_hash_name, exterior, quality
FROM catalog
WHERE category = 'weapon'
  AND (name_zh LIKE '%燃料喷射器%' OR name_zh LIKE '%流金王朝%')
ORDER BY market_hash_name;
```

```sql
SELECT datetime(trade_time, 'unixepoch', '+8 hours') AS 北京时间,
       price_cny AS 成交价, wear_decimal AS 精确磨损, paint_seed AS 模板
FROM trades
WHERE market_hash_name = 'M4A4 | Buzz Kill (Factory New)'
ORDER BY trade_time DESC LIMIT 20;
```

`sql/01_catalog.sql` 搜目录，`02_universe.sql` 查最新名单，`03_market.sql` 查成交与小时行情，`04_coverage.sql` 查已观察范围和任务进度。行情示例使用已有试采的 M4A4；新规格返回空行可能是尚未采集，不代表无成交。

## 时间、价格与备份

事件时间存为 UTC Unix 秒，展示北京时间用 `datetime(...,'unixepoch','+8 hours')`。日期过滤用明确的北京时间边界，左闭右开：

```sql
SELECT count(*) AS 来源记录数
FROM trades
WHERE market_hash_name = 'M4A4 | Buzz Kill (Factory New)'
  AND trade_time >= CAST(strftime('%s', '2026-09-01T00:00:00+08:00') AS INTEGER)
  AND trade_time < CAST(strftime('%s', '2026-10-12T00:00:00+08:00') AS INTEGER);
```

价格和精确磨损保留十进制 TEXT。展示读取原值；统计可 `CAST(price_cny AS REAL)`，精确金额计算使用 Python Decimal。磨损范围过滤用 `wear_value`，展示用 `wear_decimal`。

SQL 示例只读。查询导出留在 `data/local/`。SQLite 使用 WAL，读取可以并行，查询完及时结束事务。备份用 SQLite 备份功能或 Python `sqlite3.Connection.backup()`；正在写入时单独复制主文件可能漏掉 WAL 中的记录。

当前 schema 为 `user_version=2`。早期试采库迁移保留任务 ID、游标和检查点，将成交任务周期统一为 `event`，并增加名单表。见[历史库口径](../data/HISTORY_SCHEMA.md)。
