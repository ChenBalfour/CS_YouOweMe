# 脚本与工程配套

目录版本 layout-1.0，代码版本 0.3.5（本地未发布）。每个文件和子目录的用途、SHA-256 内容版本见 [统一清单](../docs/governance/FILE_CATALOG.json)。

| 位置 | 用途与保留依据 |
| --- | --- |
| collect.py | 旧 CLI 入口，保留解析、存储和任务机制参考 |
| check_secrets.py | 提交和历史凭证检查，仅输出位置与结果 |
| select_uu_research.py | 有预算 P02 调查、身份修订与版本化研究名单，不创建历史队列 |
| local/selection_sources/ | 按运行保存实际 P02 采集源码，保持私有 |
| pilot_uu_day.py | 单品单日有限采集、独立试跑库、CSV 导出与离线核验 |
| verify_public_evidence.py | 有预算公开页面/规则和三类已发现 UU 只读入口核验；本轮 UU 主机受限已停止 |
| verify_uu_fields.py | 两规格 UU 汇总比较字段补查，独立库；不自动执行 |
| review_uu_verification.py | 指定冻结运行的只读复核与私有观察导出，不采集市场 |
| notebooks/uu_observe_24h.ipynb | 用户在 VS Code 手动运行的连续观察入口，交付时未执行 |
| observe_uu_24h.py | 用户显式新建/恢复/只读状态 CLI，与 Notebook 共用同一机制 |
| local/pilot_sources/ | 私有实际运行源码版本，哈希与采集/核验清单对应 |
| manage_assets.py | 生成或检查文件、目录版本清单 |
| src/cs_youoweme/ | 分层源码；新增 verification 的 L0 字段解释，UU 执行口径尚未验收 |
| tests/ | 离线回归，检验解析、精度、恢复及凭证隔离 |
| sql/ | 旧历史库只读诊断查询 |
| config/ | 种子、观察线索、空白模板、可选工作区和私有凭证 |
| hooks/ | 本地提交与推送凭证检查 |

从项目根运行 `python -B -m unittest discover -s scripts/tests -v`。`collect.py --version` 不调用市场接口；其他旧采集命令仍需对应部分的明确范围。

每次操作完成更新 [主进展](../docs/PROGRESS.md)，实现变化同步 [产品架构](../docs/ARCHITECTURE.md)。修改文件后先检查，再运行 `python -B scripts/manage_assets.py --write` 更新清单，随后 `--check` 核对。本地 hooks 路径为 `scripts/hooks`。不要把生成缓存、原始数据或模型产物放入此目录。
