# 采集与目录迁移

> 状态：legacy / unreviewed。此页描述旧技术试验，不代表已验收的 UU 研究能力；其中命令不作为本阶段执行任务。当前方向以 [主计划](../research/PLAN.md)与[资产登记](../governance/ASSET_REGISTER.md)为准。

## 公开页面

在仓库根目录运行，Python 3.11+，无第三方运行依赖：

```bash
python scripts/collect.py --version
python scripts/collect.py public --limit 20 --delay 2.5
```

`config/seeds.json` 是精确英文市场名列表。普通版、StatTrak、纪念品和不同磨损是不同规格。`--seeds` 可指定其他 JSON 文件；显式相对路径以当前工作目录为准，默认配置和输出以仓库目录为准。

公开页按顺序采集，间隔至少 2 秒。同一时间只运行一个进程。认证、拒绝访问或限流会停止本批请求；其他错误写入报告。退出码：0 完整成功，2 部分成功，1 参数、配置或运行错误。

## 官方接口配置

在 [SteamDT 官方平台](https://doc.steamdt.com/)申请密钥后，在本地复制模板：

```powershell
# Windows PowerShell；已有配置时不要覆盖它
Copy-Item config/.env.example config/.env
```

```bash
# macOS / Linux；已有配置时不要覆盖它
cp config/.env.example config/.env
```

真实值只填写在被 Git 忽略的 `config/.env`。`config/.env.example` 必须保持空白，它会公开。读取顺序：环境变量 `STEAMDT_API_KEY` → `config/.env` → 旧版根目录 `.env`（兼容）。配置读取不会打印值。

```bash
python scripts/collect.py api --limit 20 --with-base
python scripts/collect.py kline --help
```

官方基础目录已完成真实认证验证，并接入 `catalog sync`。旧批量报价模式仍默认保留原价，确认人民币口径后再使用 `--currency CNY`；旧官方 K 线命令仅归档响应。官方 [K 线说明](https://doc.steamdt.com/428124801e0)不包含成交数据；网页历史是独立来源，实测包含量额与成交。新增目录、小时行情与逐笔采集见 [历史采集](HISTORY.md)，不要将两种接口口径混用。

[官方权限列表](https://doc.steamdt.com/6369437m0)给出基础信息每天 1 次、批量价格每分钟 1 次、K 线每分钟 120 次。采集器使用基础信息 24 小时缓存、批量调用至少 61 秒间隔；账号配额也可能被其他程序消耗。

## 输出

```text
data/local/                       全部忽略，不进入 Git
├── runs/<run_id>/
│   ├── raw/                       完整 HTML / API 原始 JSON
│   ├── tables/                    items / quotes / related_variants.csv
│   └── reports/                   manifest.json、quality_report.md
├── api_cache/                     基础目录与配额状态
├── steamdt.sqlite                 多批次快照数据库
└── latest_run.json                最新公开页/API 快照指针
```

K 线模式只生成 `raw/` 和 `reports/manifest.json`，不更新快照数据库或最新报价指针。CSV 使用 UTF-8 BOM；导入时商品 ID 应视作文本。

`data/samples/` 只存经过核对、可公开分发的匿名样本，按同样的 raw / tables / reports 层级组织。样本的原始文件是网页提取的 Nuxt JSON；实时采集仍保存完整网页。字段见 [数据字典](../data/DATA_DICTIONARY.md)。

## 从 v0.1.0 迁移

| 旧位置 | 新位置 |
| --- | --- |
| `collect.py` | `scripts/collect.py`（入口），`src/cs_youoweme/`（实现） |
| `.env.example` / `.env` | `config/.env.example` / `config/.env` |
| `samples/pilot_20261011/*.csv` | `data/samples/pilot_20261011/tables/` |
| `samples/pilot_20261011/payloads/` | `data/samples/pilot_20261011/raw/` |
| `data/runs/`、数据库、缓存 | `data/local/` 下对应目录 |
| 根目录数据字典 | `docs/data/DATA_DICTIONARY.md` |
| `tools/check_secrets.py` | `scripts/check_secrets.py` |

已有运行输出需备份迁移，重命名后更新相对路径，不能只移动 CSV 而丢失 raw。最初试采的完整 HTML、数据库、清单与原始配置保存在 `data/local/archive/initial_collection/`，用于追溯；重复旧代码、测试与说明已清理。历史数据的旧路径保留原状，新采集使用上述新目录。

版本唯一来源为 `src/cs_youoweme/__init__.py` 的 `__version__`。`pyproject.toml` 使用同一版本；推荐直接运行源码入口，或在源码目录内进行 editable 安装。配置和本地数据均属于工作区，不打包分发。
