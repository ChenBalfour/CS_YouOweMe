# CS_YouOweMe

CS2 武器皮肤的数据采集与挖掘课程项目。当前版本 `v0.2.0` 整理了工程目录和课程建模方案，保留第一代已验证的采集功能与公开样本。历史接口实测、模型训练和购买决策仍待后续完成。

## 目录按用途分开

```text
CS_YouOweMe/
├── src/cs_youoweme/         实现：采集、解析、清洗、存储、CLI
│   └── collectors/         公开页面与官方 API 两条采集流程
├── scripts/                命令入口、提交前密钥检查
├── config/                 商品列表、空白配置模板、本地私有配置
├── data/
│   ├── samples/            可公开样本，每批分 raw / tables / reports
│   └── local/              新采集、数据库、缓存、旧项目归档，全部忽略
├── docs/
│   ├── usage/              采集使用与版本迁移
│   ├── data/               数据字典与来源
│   ├── research/           因子建模方案与迭代计划
│   └── releases/           各版本发布说明
├── tests/                  离线解析、样本完整性与采集流程测试
├── .github/                CI、贡献与安全说明
└── .githooks/              本地提交 / 推送检查
```

根目录保留项目入口文档、许可、更新日志和工程配置。版本由 `src/cs_youoweme/__init__.py` 管理。

## 快速开始

Python 3.11+；采集运行只使用标准库，无需安装第三方依赖。

```bash
git clone https://github.com/ChenBalfour/CS_YouOweMe.git
cd CS_YouOweMe
python scripts/collect.py --version
python -m unittest discover -s tests -v
python scripts/collect.py public --limit 20 --delay 2.5
```

修改 `config/seeds.json` 可以调整精确商品规格。公开页逐个请求，间隔至少 2 秒；同一时间只运行一个采集进程。新结果写入 `data/local/runs/<run_id>/`，其中原始资料、CSV 和报告分别进入 `raw/`、`tables/`、`reports/`。

官方 API 使用本地 `config/.env` 或环境变量。**真实密钥不能填进公开模板 `config/.env.example`。** 已有密钥配置无需重新复制；本地配置、数据库和缓存均被 Git 忽略。完整命令、配额处理、退出码和旧版路径迁移见 [采集指南](docs/usage/COLLECTION.md)。

## 已有数据

[公开样本](data/samples/pilot_20261011/)采集于北京时间 2026-10-11 22:15–22:16：

| 表 / 检查 | 数量 | 口径 |
| --- | ---: | --- |
| 商品信息 | 20 | 7 类武器，普通版、久经沙场 |
| 平台报价 | 180 | 每个商品 9 条平台记录 |
| 正数在售报价 | 100 | 挂牌价，不是实际成交价 |
| 零值且过期报价 | 80 | 清洗价格为空，并保留质量标记 |
| 关联规格 | 267 | 同涂装的其他版本 / 磨损，字段不完整 |

这是一批便利试采快照，不代表全市场，也没有可用于收益验证的历史序列。分发的原始 JSON 来自匿名页面 Nuxt payload；CSV 保存来源、时间、相对路径与 SHA-256，另保留整页 HTML 校验值。本地初次采集的完整网页已归档到 `data/local/archive/initial_collection/`。

[数据字典](docs/data/DATA_DICTIONARY.md)解释字段与缺失值；[数据来源](docs/data/DATA_SOURCES.md)列出官方接口和分发口径。官方认证调用、币种和 K 线数组定义尚未实测确认；K 线文档明确不包含成交数据，不能假定已有真实成交量。

## 因子与课程建模

建议以“未来 14 日同平台报价收益”为第一阶段研究目标：Ridge 回归预测收益，逻辑回归预测上涨概率，KMeans 探索价格 / 波动 / 流动性分组。按日期验证，训练期内拟合预处理，考虑标签重叠、数据过期、交易限制和费用。

候选因子、目标公式、验证方法、算法评估和数据要求见 [建模方案](docs/research/FACTOR_MODELING.md)。该文档是研究设计，当前未训练模型或得到回测表现。后续阶段见 [迭代计划](docs/research/ROADMAP.md)。

## 开发与版本管理

`main` 保存通过检查的代码；迭代使用功能分支和 pull request，正式版本使用标签与 [更新日志](CHANGELOG.md)。第一代保留为 `v0.1.0`。

```bash
git config core.hooksPath .githooks
python scripts/check_secrets.py --history
python -m unittest discover -s tests -v
```

密钥检查覆盖待发布文件和可达 Git 历史，从本地配置读取已知值进行比对，只报告路径和状态。GitHub Actions 的离线测试不使用真实密钥。详见 [贡献说明](.github/CONTRIBUTING.md)和[凭证说明](.github/SECURITY.md)。

原创代码与文档采用 [MIT License](LICENSE)。第三方市场数据、商标与原站内容的权利仍归各自权利人。
