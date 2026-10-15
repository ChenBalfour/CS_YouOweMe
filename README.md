# CS_YouOweMe

面向悠悠有品的 CS2 普通百元枪皮研究 demo，评估七日 CD 实际解锁后退出的价格、净收益风险和可成交性。当前只有 L0 来源观察；正式数据集、训练模型和完整决策 demo 尚未实现。

## 三个主文档

| 文档 | 用途 |
| --- | --- |
| [产品说明](docs/PRODUCT.md) | 目标、用户流程、选品与退出策略、建议输出和验收要求 |
| [产品架构](docs/ARCHITECTURE.md) | 当前实现、数据流、存储恢复、后续模型与执行边界 |
| [当前进展与卡点](docs/PROGRESS.md) | 已完成成果、实际运行、卡点、下一步和每次操作记录 |

先读这三份文档。每次操作完成后更新进展；目标或实现变化同步对应主文档。专项依据和操作指南见 [文档索引](docs/README.md)。

UU历史新入口：[采集与入库步骤](docs/usage/UU_HISTORY_COLLECT.md)、[用户Notebook](scripts/notebooks/uu_history_collect.ipynb)。浏览器正常登录后由用户显式采集，真实稳定性待验收；当前没有训练模型。

新增[纯脚本有限试用入口](docs/usage/UU_DIRECT_COLLECT.md)：运行时不打开网页，登录信息仅在本机私有配置；先尝试一组，再显式继续。44828纯脚本七组已完整成功，共1360条窗口记录，原始JSON/SQLite/CSV一致；多轮、多商品与统计口径仍待验收，旧受限入口保持原记录。

新增 [SteamDT 本地小时数据库 Notebook](scripts/notebooks/steamdt_research.ipynb) 与[使用说明](docs/usage/STEAMDT_RESEARCH.md)：集中维护商品名称/编号，首次回补、保存分页检查点、再次启动续采，近期增量去重并保留来源修订。默认关闭联网，由用户手动运行；实际覆盖见进展和私有报告。

研究方案新增[SteamDT主序列与UU补充对齐](docs/data/SOURCE_ALIGNMENT_PLAN.md)：保留小时原始数据、按决策时点使用过去已知值，不人为制造细粒度波动；尚未构建正式特征或训练。

| 目录 | 内容 |
| --- | --- |
| [scripts](scripts/README.md) | Notebook、CLI、源码、配置、测试、SQL 与 hooks |
| [data](data/README.md) | 私有数据库、原始证据和冻结公开样本 |
| [docs](docs/README.md) | 三大主文档与字段、运行、管理、版本附件 |

运行代码 **0.3.5（本地未发布）**，目录 **layout-1.0**，制度 **management-1.3**。全部文件和目录的用途、内容版本见 [索引](docs/governance/FILE_INDEX.md)与 [SHA-256 清单](docs/governance/FILE_CATALOG.json)。

离线检查：

```powershell
python -B -m unittest discover -s scripts/tests -v
python -B scripts/manage_assets.py --check
```

采集由用户自己本地显式启动，见 [Notebook 说明](docs/usage/OBSERVE_24H.md)。已有运行和输出保留，agent 不代运行连续采集或后台任务。当前停止新增 GitHub push、PR、合并与 release。本地 Git 记录版本，原始数据和凭证留在忽略目录。

原创代码与文档采用 [MIT](LICENSE)。第三方数据及商标权利归其权利人。
