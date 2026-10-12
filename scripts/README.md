# 脚本与工程配套

目录版本 layout-1.0，代码版本 0.3.1（本地未发布）。每个文件和子目录的用途、SHA-256 内容版本见 [统一清单](../docs/governance/FILE_CATALOG.json)。

| 位置 | 用途与保留依据 |
| --- | --- |
| collect.py | 旧 CLI 入口，保留解析、存储和任务机制参考 |
| check_secrets.py | 提交和历史凭证检查，仅输出位置与结果 |
| manage_assets.py | 生成或检查文件、目录版本清单 |
| src/cs_youoweme/ | 分层源码；UU 口径适配尚未验收 |
| tests/ | 离线回归，检验解析、精度、恢复及凭证隔离 |
| sql/ | 旧历史库只读诊断查询 |
| config/ | 种子、观察线索、空白模板、可选工作区和私有凭证 |
| hooks/ | 本地提交与推送凭证检查 |

从项目根运行 `python -B -m unittest discover -s scripts/tests -v`。`collect.py --version` 不调用市场接口；其他旧采集命令仍需对应部分的明确范围。

修改文件后先检查，再运行 `python -B scripts/manage_assets.py --write` 更新清单，随后 `--check` 核对。本地 hooks 路径为 `scripts/hooks`。不要把生成缓存、原始数据或模型产物放入此目录。
