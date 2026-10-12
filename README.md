# CS_YouOweMe

面向悠悠有品（UU）的 CS2 百元、千元普通枪皮决策研究，研究可执行净收益与退出能力。P01 完成；用户指定的单品单日数据试跑已完成，正式选品与爬虫完整验收尚未完成；正式 UU 名单、数据集、模型均为 0。

本地工程版本 **0.3.2（未发布）**，目录版本 **layout-1.0**，研究计划 **plan-1.1**，文件制度 **management-1.1**。本次按用户指示完成 SteamDT/YOUPIN 单品单日试跑：卡特尔战痕累累、北京时间 2026-10-11、24 个小时价格桶。成交平台及量额口径仍待核验。

| 主体目录 | 内容 | 入口 |
| --- | --- | --- |
| scripts/ | 源码、命令、配置、离线测试、SQL、Git hooks | [脚本说明](scripts/README.md) |
| data/ | 私有来源证据、旧库、旧名单及冻结公开样本 | [数据说明](data/README.md) |
| docs/ | 计划、制度、字段、使用、发布历史与交接文档 | [文档说明](docs/README.md) |

根目录仅另保留 README、AGENTS、LICENSE、pyproject、Git 配置和 `.github/workflows/` 等工具要求的入口。逐文件与逐目录说明、内容版本见 [逐项说明](docs/governance/FILE_INDEX.md)和[完整哈希清单](docs/governance/FILE_CATALOG.json)；私有文件的对应清单留在忽略目录，不进入 Git。

先读 [主计划](docs/research/PLAN.md)、[当前状态](docs/governance/STATE.md)和[交接](docs/governance/HANDOFF.md)。迁移与删除依据、恢复方法见 [整理记录](docs/governance/ORGANIZATION.md)。旧成果按用途审查后再复用。

离线检查在项目根目录运行：

```powershell
python -B -m unittest discover -s scripts/tests -v
python -B scripts/collect.py --version
python -B scripts/manage_assets.py --check
```

一次完成用户指定的一部分。当前暂停新增 GitHub push、PR、远程合并及 release，最后 P06 再审查开源。真实凭证只在忽略的 `scripts/config/.env` 或环境变量；空白模板不填写真实值。

原创代码与文档采用 [MIT](LICENSE)。第三方数据及商标权利归各自权利人。
