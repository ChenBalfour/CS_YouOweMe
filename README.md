# CS_YouOweMe

面向悠悠有品（UU）的 CS2 普通枪皮决策研究，研究可执行净收益与退出能力。第一批按用户最新要求只选百元（100 ≤ 价格 < 1000 元），优先同档属性较可比、普通件容易匹配通用求购的规格。原 P02 的 10 主力+6 候补保留历史版本，需按新规则复核；P03 仅通过 L0 来源观察，正式数据集与模型仍为 0。

本地工程版本 **0.3.5（未发布）**，目录版本 **layout-1.0**，研究计划 **plan-1.5**，文件制度 **management-1.2**。[选品修订](docs/research/SELECTION_REVISION_20261014.md)已记录百元范围和求购条件证据。用户已自行运行[Notebook](scripts/notebooks/uu_observe_24h.ipynb)首轮并中断，2 个快照保存成功；24 小时稳定性尚未验收，后续由用户按[运行说明](docs/usage/OBSERVE_24H.md)操作。

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
