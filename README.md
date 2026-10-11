# CS_YouOweMe

CS2 枪皮市场研究与数据基础设施。当前版本 **v0.3.0**：可查询的商品目录、精确磨损成交、小时行情、可恢复的采集任务与版本化研究名单。

研究集中于**千百战枪皮**：百元和千元价位的普通武器皮肤。先完成主力筛选和数据质量验证，再进行事件研究、论文复现与预测评估。

## 开始使用

Python 3.11+；采集与查询使用标准库，无第三方运行依赖。

```bash
git clone https://github.com/ChenBalfour/CS_YouOweMe.git
cd CS_YouOweMe
python scripts/collect.py --version
python scripts/collect.py catalog sync
python scripts/collect.py catalog search --query "燃料喷射器"
python scripts/collect.py universe scan --output data/local/universes/qianbaizhan.json
```

官方目录读取本地 `config/.env`；公开模板 `config/.env.example` 保持空白。网页历史使用实测的匿名接口。新名单不会自动启动历史回填；审阅后再指定名单和日期窗口。

- [在 VS Code 连接数据库、运行 SQL](docs/usage/DATABASE.md)
- [筛选、回填、续跑与覆盖检查](docs/usage/HISTORY.md)
- [研究范围、假设、事件与方向](docs/research/DESIGN.md)
- [第一版千百战名单与依据](docs/research/UNIVERSE.md)

## 项目结构

```text
src/cs_youoweme/
├── collectors/      公开页面、官方接口、网页历史客户端
└── history/         目录、名单、SQLite、任务、查询与聚合
scripts/             CLI 入口、密钥检查
config/              试采种子、观察名单、空白模板、VS Code 工作区
sql/                 可直接执行的只读查询
data/
├── samples/         经核对的匿名公开试采样本
└── local/           私有数据库、原始响应、名单和运行记录
docs/
├── usage/           使用方法
├── data/            字段、来源与口径
├── research/        研究设计、名单与方向
└── releases/        发布记录
tests/               离线验证
.github/             CI、贡献与安全说明
.githooks/           提交与推送检查
```

默认历史库：`data/local/database/market.sqlite`。目录、成交、行情、名单和任务分表保存；原始响应采用 gzip 压缩并保留 SHA-256。

## 已验证的范围

截至 2026-10-12，本地目录有 **44,502 个来源当前规格**；历史试采有 **119,520 条小时行情、1,420 条成交**。10 个试采行情序列的小时桶覆盖北京时间 **2025-06-01 至 2026-10-11**，包含早期刀／手套及相位验证数据。部分来源量额缺失，逐笔成交尚未回填到目标起点。第一版千百战名单入选 11 个规格，其完整历史回填尚未开始。

这些是本地验证结果，数据库不随代码分发。小时桶齐全不代表全市场成交完整，也不代表新入选规格已有历史。保留完整轻量目录，仅回填已选样本。

[公开试采样本](data/samples/pilot_20261011/)保留 20 条商品、180 条报价和 267 条关联规格，供解析与追溯验证。报价是挂牌价，不能作为真实成交。见[数据字典](docs/data/DATA_DICTIONARY.md)、[历史库口径](docs/data/HISTORY_SCHEMA.md)和[数据来源](docs/data/DATA_SOURCES.md)。

## 开发

```bash
git config core.hooksPath .githooks
python -m unittest discover -s tests -v
python scripts/check_secrets.py --history
```

`main` 保存通过检查的代码，正式版本使用标签和 [Changelog](CHANGELOG.md)。密钥检查只报告路径和状态，不打印真实值；CI 使用合成数据。版本唯一来源为 `src/cs_youoweme/__init__.py`。

原创代码与文档采用 [MIT](LICENSE)。第三方数据与商标的权利归各自权利人。
