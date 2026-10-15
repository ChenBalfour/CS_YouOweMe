# SteamDT 小时数据库：VS Code 本地采集

版本 **steamdt-research-guide-1.0**，2026-10-16（北京时间）。独立组件 **steamdt-research-1.0**；沿用冻结核心 0.3.5，未改旧运行。采集 SteamDT 网页明确选择悠悠平台的小时 OHLC 与来源量额；当前只有 L0 研究观察，未训练或交易。

## 打开与运行

1. 在 VS Code 打开项目根目录，打开 [steamdt_research.ipynb](../../scripts/notebooks/steamdt_research.ipynb)，选择 Python 3.11+ 内核。Notebook 所需 Jupyter 扩展和 ipykernel 由本机 VS Code 提示安装；采集代码仅用标准库。
2. 运行配置、清单单元格。默认工作区 `research_20261016_v1`；已有工作区继续使用，不覆盖、不清空。没有工作区时先离线初始化。
3. 打开该单元格输出的 `registry.json`，确认商品和历史起点。
4. 将采集单元格 `RUN_COLLECTION=False` 改成 `True`，运行该单元格。一轮结束后运行报告单元格。预算暂停时再次运行采集单元格，使用相同工作区继续。

交付 Notebook 没有执行输出；默认“运行全部”不发市场请求。输出摘要在单元格，数据、检查点和报告在磁盘。无需登录 SteamDT 或填写 Cookie、authorization、deviceid；本入口不读取 UU 认证配置。

CLI 与 Notebook 共用同一程序，任选一个运行，避免并发：

```powershell
Set-Location F:\Codex\CS_YouOweMe
# 只有全新工作区才执行 init；已经存在就跳过
python -B scripts/steamdt_research.py init --workspace research_20261016_v1
python -B scripts/steamdt_research.py sync --workspace research_20261016_v1 --max-requests 80 --delay 5
python -B scripts/steamdt_research.py status --workspace research_20261016_v1
```

`status` 只读最近一次落盘的报告。初次初始化但尚无报告时返回 initialized；运行中报告不会逐页刷新，实时进度打印在采集单元格，游标存于数据库 jobs 表。

## 商品登记与扩展

工作清单位于 `data/local/staging/steamdt/research_20261016_v1/registry.json`。公开 [初始模板](../../scripts/config/steamdt_research_items.json) 仅在创建新工作区时复制；之后修改工作区清单。

每个条目必须包含以下字段：

| 字段 | 填法与含义 |
| --- | --- |
| market_hash_name | 准确英文规格名，包含标准磨损；程序核对响应名称 |
| name_zh | 中文显示名 |
| steamdt_item_id | SteamDT 数字编号字符串；未知填 null，按英文名查询 |
| uu_template_id | UU 数字模板编号字符串；未知填 null，解析 SteamDT 明确悠悠比较行的 UU 链接 |
| history_start | `"2025-06-01"` 等北京时间日期；null 尝试来源可提供的最早历史 |
| enabled | true 启用、false 暂停；暂停不删除旧数据 |

复制现有条目添加商品即可，留意 JSON 数组与逗号。上限 50 个普通武器精确规格；不混入 StatTrak、纪念品或同名不同磨损。不能只换数字编号而保留错误英文名。已填编号与来源不一致时停止。解析出的两个编号存入 catalog/platform_ids，并导出到每轮报告目录的 `resolved_items.csv`；不会无声改写你维护的清单。

现有七个只是待核验候选。采集报价满足百元范围，不代表 float、模板、贴纸与通用求购条件已核验；当前全部 execution_eligible=false。

## 首采、续采与去重

- 新商品创建初始回补任务，从最新已过小时向历史分页，直到配置起点或来源返回空页。`history_start=null` 仅表示尝试全部可得历史；不保证从商品发行日开始，也不保证网站无限提供。
- 每页数据库事务保存数据和 cursor。预算到达或正常中断后，已提交页保留，下次继续 pending 任务；进程突然退出时，最多重新请求未提交的一页。原始响应可能已归档而数据页未提交，重取仍按主键去重。
- 旧商品增加近期任务。daily 从现有末点前 7 天开始重查，weekly 回看 35 天，补最新数据并发现修订；之后继续较旧的未完成回补。不能承诺永远只请求从未见过的时间点，否则无法发现修订。
- `bars` 按精确规格、平台、周期、样式、原始时间唯一；同键更新。`research_hourly_latest` 再按小时桶选最近来源记录，避免源端秒偏移产生两个研究小时。原始秒时间仍保留。
- `research_bar_versions` 保留首次值和变化值，完全相同的重复请求不增加值版本；A→B→A 都留证据。raw 使用内容 SHA-256 gzip 归档；请求日志、清单快照和源码随每轮保留。

任务状态：pending 待续采；done 本次任务处理结束；blocked 等待处理停止原因。paused_budget 是运行预算暂停，不是网络失败。completed 也不保证所请求起点有完整覆盖：结合首末时间、内部缺口、requested_start_observed 和 finish_reason 检查。source_history_exhausted 表示来源已返回空页，不能据此声称拥有起点以来全部历史。已禁用商品的任务保留 blocked/registry_disabled，重新启用后继续。

## 文件位置与表

工作区整体保持私有，不提交 Git：

```text
data/local/staging/steamdt/research_20261016_v1/
  registry.json                   用户维护的商品清单
  workspace.json                  组件版本与冻结核心哈希
  research.sqlite                 商品、小时数据、任务、检查点与来源版本
  raw/                            按内容哈希归档的压缩响应
  runs/<invocation>/              每轮清单、配置、源码及结束状态
  reports/<invocation>/           report.json / report.md / resolved_items.csv
                                  每规格 1h / 4h / 1d / 1w CSV
  latest_report.json              指向具体历史报告
```

| 表/视图 | 用途 |
| --- | --- |
| catalog、platform_ids | 核对后的英文身份、SteamDT 编号、UU 模板编号 |
| jobs、checkpoints | 每规格的请求范围、分页游标、成功页数和停止原因 |
| bars | 当前来源记录，保留原始时间、小时桶、OHLC、可空量额和 request_id |
| research_hourly_latest | 每规格/小时的最新来源记录，导出使用此视图 |
| research_bar_versions | 首次值与数值变化历史，引用原始请求 |
| research_quotes | 每轮 SteamDT 悠悠比较行报价及异常/范围标记，不认定可执行 |
| requests、research_receipts | 请求开始时间、响应接收时间、参数与原始哈希 |
| research_job_generations | 已完成近期任务再次复核前的任务与检查点快照 |

检查数据库用 mode=ro。备份先停止采集，使用 SQLite backup 或完整处理 WAL，保留整个工作区及旁边共享 `research_control` 目录；不要只复制活动数据库主文件，不要删库“重新开始”。

## 时间、量额与跨周期

请求强制 platform=YOUPIN、type=1，核对英文身份和显式悠悠比较行。原始时间与归一小时分别存储；导出只包含本轮开始时已经过小时边界的桶，不能推定来源此后永不修订。历史 available_at 未知，当前 request/received_at 不能冒充当时已可见时间。

4 小时、日、周 CSV **由小时数据派生**，不是额外抓取网页对应周期。按北京时间分桶，周一开始；首开、最高、最低、末收。覆盖应分别有 4/24/168 个小时，complete_hours 标记不完整；量额在覆盖不足或任何子小时空值时保留 null，不补零、不插值、不制造波动。部分窗口 OHLC 只代表已观察子小时，使用时必须过滤完整标记。

来源 volume/turnover 存为 source_volume/source_turnover_cny，不等于已确认 UU 真实订单数量与结算额。成交价格、来源收盘、当前在售/求购与自己的成交价用途不同；正式多源特征、训练和执行判断尚未实现。

## 请求预算与停止

默认串行间隔 5 秒，允许 3–60 秒；一轮默认最多 80、可设 1–120 次 HTTP（包括时钟与身份核验），最长 15 分钟。程序共享滚动 24 小时 300 次尝试上限，单次响应 2 MiB、库与压缩 raw 软上限 128 MiB。软上限在下次请求前检查，最后一条响应可能造成小幅越界。首次多品回补通常需要多轮，不能用新工作区清除共享配额。

每轮先核对所有启用商品的元数据，再取历史；预算过小可能只完成身份核验。预算至少要容纳每品两次身份请求、时钟请求和历史分页：七品建议默认80，超过约35品时需设120或先禁用部分条目分批；反复用不足以完成身份阶段的小预算不会推进历史。当前单请求超时30秒。

401/403/429、网络、业务或结构错误停止，不自动重试。429 保留 Retry-After（无法读取则至少 15 分钟）及全局停止。先在网站确认正常访问恢复、处理停止原因，且等待冷却结束后才显式使用 Notebook 的 NORMAL_ACCESS_CONFIRMED=True 或 CLI `--normal-access-confirmed`；确认不能跳过冷却、配额或结构校验。不要循环确认、换工作区或换账户冲掉停止记录。

## 后续运行频率

本次只交付手动有限采集，没有后台进程、服务或定时任务。建议日常 daily 至少每天运行一轮、每周 weekly 深入复核；若每周才更新一次，无法支撑每日新信息决策。实际买入前仍需取得新鲜、属性匹配的 UU 报价；来源趋势训练与七日预测属于后续阶段。

已做针对性离线测试：分页与预算恢复、去重与修订、清单校验、429 停止和冷却、只读状态、不完整聚合、初始化防覆盖。真实运行的请求数、范围和缺失见 [PROGRESS](../PROGRESS.md) 及私有每轮报告；单次有限读取不能替代跨日稳定性验收。
