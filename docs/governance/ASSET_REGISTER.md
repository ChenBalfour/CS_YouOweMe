# 既有资产登记

登记版本 asset-register-1.1，2026-10-12。本次完成文件用途略审与工程整理；市场资产的来源、标签、执行能力仍需对应部分验收。

| 资产/位置 | 状态 | 用途与保留依据 | 后续部分 |
| --- | --- | --- | --- |
| docs/research/PLAN、governance/ 制度与状态 | current-plan | 当前方向、管理与停止点 | P01 |
| scripts/src、collect.py | legacy / unreviewed-market | 解析、精度、分页、恢复和存储机制可复用 | P03 |
| scripts/tests | legacy / offline-regression | 机制回归；通过不代表市场数据合格 | P03–P05 |
| scripts/check_secrets.py、hooks | retained / engineering | 本地凭证隔离检查，仍暂停远程发布 | 持续 |
| scripts/manage_assets.py、FILE_CATALOG | current-management | 每个文件及目录的版本、用途与完整性检查 | 持续 |
| scripts/config/seeds、watchlist | legacy / research-clue | 旧精确种子及用户举例线索，非正式名单 | P02 |
| scripts/sql、config/vscode.code-workspace | legacy / diagnostic | 旧库只读诊断参考 | P03–P04 |
| data/local/database、raw | legacy / unreviewed | 旧行情、成交与来源证据；保留原路径与内容 | P03–P04 |
| data/local/universes | legacy / unreviewed | 旧候选快照，不沿用旧数量或权重 | P02 |
| data/local/recon、archive、api_cache | legacy / reference | 接口、事件、初始采集与目录证据；已去除两份相同副本 | P03–P05 |
| data/samples/pilot_20261011 | already-public / frozen | 旧匿名快照与离线解析样本，非 UU 正式训练集 | P04、P06 |
| docs/data、usage、research/UNIVERSE、releases | legacy / documentation | 字段、接口限制、历史方法与公开版本追溯 | 对应部分 |
| docs/local/progress、data/local/progress | private / historical | 当前文字交接和冻结 JSON 历史；不能自动恢复旧任务 | 持续 |
| data/local/manifests | private / current-management | 整理前基线、迁移删除明细与私有版本清单 | 持续 |
| scripts/config/.env、旧归档凭证 | private / protected | 仅供授权操作，未展示、转发或加入 Git | 持续 |
| GitHub v0.1–v0.3 | already-public / frozen | 既有事实；未变更远程历史或可见性 | P06 |

本次 11 项删除均列入私有 layout-1.0-changes.json，说明依据、哈希与 Git blob 或保留副本。重复 DESIGN/ROADMAP 索引由 PLAN/STATE 取代；旧单文件代码、旧测试及 VERSION 已有完全一致的 Git 历史，无需保留第二份。文件内容版本和各子目录说明详见 FILE_CATALOG 与私有清单。

旧记录曾报告 44,502 个目录规格、119,520 条小时行情、1,420 条成交；本次未查询旧库重新验证。正式 UU 名单、已验收数据集、已验收模型均为 **0**。
