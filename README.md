# CS_YouOweMe

CS2 虚拟商品交易的数据提取与挖掘研究项目。第一代 `v0.1.0` 完成公开商品信息与跨平台报价的试采、数据追溯和质量检查，为后续历史数据、因子研究和决策系统积累基础。

当前提供采集工具和可复现样本。购买建议、预测模型和交易执行尚未实现。

## 第一代功能

- 读取 SteamDT 公开商品详情页中的真实数据，无需登录。
- 按精确英文市场名称区分武器、涂装、磨损档位及普通 / StatTrak / 纪念品版本。
- 分别导出商品信息、平台报价、关联规格，并保留来源时间、原始数据与 SHA-256。
- 对零值报价留空清洗价格，标记过期报价，记录失败请求。
- 将后续采集快照保存到本地 CSV 和 SQLite，保留历史批次。
- 预留官方 API 批量报价、基础目录缓存和 K 线原始响应采集。官方 API 路径尚未完成用户密钥的联网验证。

## 快速开始

需要 Python 3.11 或以上；采集器只使用标准库，无需安装第三方依赖。

```bash
git clone https://github.com/ChenBalfour/CS_YouOweMe.git
cd CS_YouOweMe
python collect.py --version
python -m unittest discover -s tests -v
python collect.py public --limit 20 --delay 2.5
```

公开页面采集按顺序发送请求，间隔至少 2 秒。遇到认证、拒绝访问或频率限制会停止；其他错误记录在本批 manifest 中，失败批次返回非零退出码。同一时间只运行一个采集进程。

通过 `config/seeds.json` 调整样本，名称必须与 Steam 官方 `marketHashName` 一致。

## 已收集的公开样本

样本位于 [`samples/pilot_20261011/`](samples/pilot_20261011/)。北京时间 2026-10-11 22:15 至 22:16，访问 20 个公开详情页得到：

| 数据 | 数量 | 说明 |
| --- | ---: | --- |
| 完整商品记录 | 20 | 7 类武器，普通版、久经沙场 |
| 平台报价记录 | 180 | 每种皮肤 9 条平台记录 |
| 正数在售报价 | 100 | 页面有正数挂牌价 |
| 零值且过期报价 | 80 | 同一组记录，清洗价格为空且标记过期 |
| 关联规格记录 | 267 | 同涂装的其他磨损与版本，字段较少 |

这是便利试采样本，不代表整个市场。当前样本是一次报价快照，没有历史日线和真实逐笔成交记录。

公开样本保留商品页面的 `__NUXT_DATA__` JSON，而不复制整页 HTML、网站脚本和样式。CSV 中的 `raw_path` / `raw_sha256` 指向分发的 JSON，`original_html_sha256` 保留原始页面校验值。全量 HTML 仍保存在最初的本地采集目录。样本的测试不需要联网或密钥。

## 本地配置官方 API

[官方接入文档](https://doc.steamdt.com/)要求在 SteamDT“个人中心 → API管理”申请密钥。复制空白模板到本地配置：

```bash
# macOS / Linux
cp .env.example .env
```

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

在本地 `.env` 中填写 `STEAMDT_API_KEY`，也可以使用同名环境变量。**真实密钥只能放在 `.env` 或环境变量，不能填进 `.env.example`。** 模板会进入公开仓库，本地 `.env`、采集结果和 API 缓存已被忽略。

```bash
python collect.py api --limit 20 --with-base
python collect.py kline --help
```

API 默认保留原始价格，币种未经核对时人民币清洗列为空；确认接口返回人民币后才指定 `--currency CNY`。K 线只保存原始 JSON，周期代码和返回列定义需用真实响应核实，不猜测 OHLCV。

[官方权限列表](https://doc.steamdt.com/6369437m0)规定基础信息每天 1 次、批量价格每分钟 1 次、饰品 K 线每分钟 120 次。脚本使用基础信息 24 小时缓存、批量请求至少 61 秒间隔，其他程序也可能消耗账号配额。

## 项目结构

```text
collect.py                  采集 CLI 与数据清洗
VERSION                     当前版本
config/seeds.json           试采商品列表
samples/pilot_20261011/      已验证的公开样本与原始 JSON
tests/                      离线解析与数据完整性测试
tools/check_secrets.py       提交内容与 Git 历史的密钥检查
.githooks/                  本地提交和推送检查
.github/workflows/ci.yml     自动测试和密钥检查
DATA_DICTIONARY.md           字段与来源口径
docs/                       数据来源、迭代方向和发布说明
data/                       本地运行输出，Git 忽略
.env                        本地密钥，Git 忽略
.env.example                无密钥的公开模板
```

## 开发与版本管理

`main` 保存通过检查的代码。日常迭代使用功能分支，并通过 pull request 合并；正式版本使用 `vMAJOR.MINOR.PATCH` 标签，同时维护 [`CHANGELOG.md`](CHANGELOG.md)。第一代标签为 `v0.1.0`。

克隆后启用本地检查：

```bash
git config core.hooksPath .githooks
python tools/check_secrets.py
python tools/check_secrets.py --history
python -m unittest discover -s tests -v
```

提交前检查暂存区，推送前检查已跟踪内容和可达 Git 历史。检查会从本地忽略的配置读取已知密钥进行比对，只输出文件位置与结果，不输出密钥值；CI 在不使用真实密钥的情况下检查配置模板和常见凭证格式。

建议新分支命名为 `feat/<feature>`、`fix/<issue>` 或 `docs/<topic>`，先验证再合并。详见 [`CONTRIBUTING.md`](CONTRIBUTING.md) 和 [`SECURITY.md`](SECURITY.md)。

## 数据口径

SteamDT 是饰品数据分析平台，本项目读取其公开展示和官方 API，并不拥有交易平台的成交账本。来源见 [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md)。

在售价格是挂牌报价，今日推算成交是平台估算值。磨损档位不是精确 float，存世量不是即时流通量。采集时间与来源更新时间分别保存；24 小时过期阈值是本项目的质量检查选择。公开页未返回的在售数量和求购数据留空。

字段定义详见 [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md)。CSV 为 UTF-8 BOM，商品 ID 应按文本导入，避免长编号被舍入。

## 后续方向

后续计划依次验证官方历史数据、扩大样本与时间范围、研究因子和回测，再构建可解释的饰品研究与决策辅助界面。设想的输入包括武器名称、磨损档位和版本，输出包括可用市场数据、数据更新时间、费用后的比较和风险说明。各阶段的计划与完成情况记录在 [`docs/ROADMAP.md`](docs/ROADMAP.md)。

## 许可

本项目原创代码和文档采用 [MIT License](LICENSE)。市场样本来自 SteamDT；第三方数据、商标及原站内容的权利归各自权利人，代码许可不改变它们的授权条件。
