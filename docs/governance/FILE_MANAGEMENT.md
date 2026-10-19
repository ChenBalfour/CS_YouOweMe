# 文件管理规范

版本 management-1.5，目录版本 layout-1.0，2026-10-19（北京时间）。2026-10-12 用户要求略读、清理、按脚本/数据/文档收拢并逐项管理版本；整理已完成，当前阶段以三大主文档为准。本次确定持续更新规则，并清理重复说明及可再生缓存。

## 目录职责

| 位置 | 职责 |
| --- | --- |
| scripts/src/cs_youoweme/ | 冻结0.3.5采集核心与历史实现，旧运行保持原版 |
| scripts/research/data、models、evaluation、visualization | 当前离线研究按数据、规则、验证、图表分包；Notebook调用而不复制实现 |
| scripts/collect.py、check_secrets.py、manage_assets.py | 薄命令入口、凭证检查、版本清单维护 |
| scripts/tests/、sql/、config/、hooks/ | 代码配套的离线验证、查询、配置与 hooks |
| data/local/ | 私有原始证据、旧资产及后续正式数据和实验产物 |
| data/samples/ | 已公开旧匿名样本，冻结待 P06 复审 |
| docs/PRODUCT.md、ARCHITECTURE.md、PROGRESS.md | 产品、架构、成果和卡点的三个主入口 |
| docs/research/ | 专项计划与调查证据 |
| docs/governance/ | 文件管理、阶段、资产、整理与版本索引 |
| docs/data/、usage/、releases/ | 字段、使用和版本历史文档 |
| docs/local/progress/ | 私有文字交接；JSON 运行日志仍在 data/local/progress/ |

根目录保留 Git 与 Python 所需的 README、AGENTS、LICENSE、pyproject、.gitignore、.gitattributes、.github/workflows；`.git/` 内部对象由 Git 维护。原始网页、来源配置、manifest 和质量报告属于批次数据证据，随数据保留；目录 README 是就近索引。

## 每个文件与目录的版本和说明

- `docs/governance/FILE_CATALOG.json` 登记 Git 管理文件和所有祖先目录：用途、状态、内容版本、SHA-256、大小。
- 私有 `data/local/manifests/workspace-layout-1.0.json` 登记全部忽略文件及目录，不把私有路径或摘要写入公开清单。
- 文件内容版本为 SHA-256；目录版本为成员路径和文件版本的聚合哈希，同时记录 layout-1.0。文件变更后版本随内容变化。
- 两份 JSON 清单与可读 FILE_INDEX.md 以 layout-1.0.catalog 记录自身，排除自身字节哈希以免循环。受保护凭证仅登记 protected-local-1，不读取内容、记录哈希或建立凭证快照；轮换后由维护者更新配置记录。
- Git 本地提交保存代码、说明和公开清单的可恢复历史；私有数据靠来源清单、哈希和冻结版本管理，不存入 Git。
- 修改后运行 `python -B scripts/manage_assets.py --write`，随后 `--check`。清单过期、缺说明、缺文件均应修正后再收尾。

三大主文档以各自页首版本为准；兼容计划 plan-1.7、选品计划 selection-plan-1.2、代码 0.3.5、目录 layout-1.0、制度 management-1.5、schema、数据集及模型版本分别记录，不能混为已发布版本。完整整理记录见 [ORGANIZATION](ORGANIZATION.md)，当前阶段见 PROGRESS。

scripts/notebooks 保存用户本地运行入口，交付的 Git 版本保持 execution_count=null、outputs=[]；实际观察写独立 data/local/staging/steamdt/p03_steamdt_observe_*，用户可能另外保存单元格输出。保留用户工作副本，不为提交自动清空或覆盖；提交仅纳入当前任务变更，不擅自提交用户执行输出。若需要修改已有入口，先私有保存准确执行版本，再处理仅供提交的空输出版本。私有恢复指针与首轮成功不能当作完成一天验收。

公开清单记录当前工作副本内容，因此用户保存 Notebook 输出会产生本地哈希变更。仅提交文档时，提交中的公开清单按 Notebook 原 Git 版本记录，提交后重新生成工作区清单，使工作副本输出仍有可检查的内容版本；用户输出及对应清单差异可以保持未提交。

新基准评估放data/local/artifacts/baseline_evaluations，每轮图放data/local/reports/baseline_charts。两者独立清单，图表不追加到已冻结评估。逐品价格和UU报价快照长期落盘，Notebook内存不替代数据层；准确源码依赖在每版产物中保存。

## 私有数据生命周期

新任务在对应部分确定范围后按需创建，不预建大量空目录：

```text
data/local/
  raw/<source>/<run_id>/           追加原始观察
  staging/<source>/<run_id>/       尚未验收的标准化候选
  datasets/<dataset_id>/           冻结 manifest、tables、reports
  artifacts/<experiment_id>/       特征、模型与运行产物
  reports/<experiment_id>/         评估、预测及配置摘要
  universes/<universe_id>/          正式名单版本
  manifests/                      运行及资产清单
  archive/                        有追溯价值的历史资料
```

旧库与原始资料保持原状；P03 用独立试跑位置，不直接追加到旧库。原始资料不清洗覆盖，冻结数据、名单和实验不复用旧 ID 无声覆盖。latest 只能指向具体版本。

运行 ID 使用北京时间且保留时区明确的 UTC；推荐 `p03_uu_YYYYMMDDTHHMMSS+0800_<短标识>`。数据集 ID 使用 `uu_<用途>_<窗口>_<版本>`，实验 ID 使用 `exp_<日期>_<短标识>`。精确金额、磨损、商品编号按字段契约保留类型与精度。

## 状态与准入

legacy / unreviewed、candidate 不可直接训练；validated 只用于验收通过的明确用途；frozen 固定输入与规则；rejected、archived 保留理由及追溯；release-approved 仅表示公开资格。解析成功、通过测试、旧公开或本次工程整理通过，均不能替代 UU 数据和模型验收。

运行清单至少记录来源、venue、阶段、时间、采样预算、schema、代码、配置摘要、请求/失败/重试和原始哈希。数据集另记录父运行、用途、可得时间、规格、单位、缺失/去重、行数覆盖、质量、变换和输入输出哈希。实验另记录数据集、名单、特征/标签/成本、时间划分、参数、随机种子、基准及所有尝试。

未知项标记 unknown 或 unavailable；不保存认证头、Cookie、真实密钥和无关个人资料。原始数据和备份均保持私有。

## 迁移、删除与收尾

删除或迁移前记录精确路径、状态、理由、保留副本或 Git 恢复依据，验证绝对路径位于项目内，核对变更前哈希，避免覆盖。用户已明确授权的清理直接执行。仅凭略读不能判定唯一历史数据无用；明确重复、生成缓存或已有 Git 历史的冗余旧副本可以清理。

迁移后检查引用、代码入口、链接与内容哈希。SQLite 备份使用备份接口，或停止写入并处理 WAL 后操作；不在活动写入时单独复制主文件。

每次操作完成必须更新 docs/PROGRESS.md，记录任务、成果/文件、验证、版本、剩余卡点和下一步；失败也记录。范围/策略变化同步 PRODUCT，实现/数据流变化同步 ARCHITECTURE，保持三文档一致。资产状态或文件布局变化再更新对应附件；PLAN/STATE/HANDOFF/CURRENT只保留兼容入口。执行相应检查并记录版本。2026-10-19用户已授权本轮公开代码/文档的分支推送和迭代PR，旧暂停条款不再阻止本轮上传；不自动合并、强推或打release标签。历史操作日志存docs/releases，当前路线只在PROGRESS维护。凭证在忽略的 `scripts/config/.env`，公开模板保持空白；私有数据、文档、模型产物不进入 Git。scripts/local/pilot_sources 和 selection_sources 保存实际运行源码的准确版本，仅为变更中代码补充追溯，保持私有并纳入私有清单。
