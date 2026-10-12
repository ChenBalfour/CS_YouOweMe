# 既有资产登记

登记版本 asset-register-1.3，2026-10-12。文件整理后新增用户授权的单品单日试跑，平台行情初步验证为 L0；市场资产的来源、标签、执行能力仍需对应部分验收。

| 资产/位置 | 状态 | 用途与保留依据 | 后续部分 |
| --- | --- | --- | --- |
| docs/research/PLAN、governance/ 制度与状态 | current-plan | 当前方向、管理与停止点 | P01 |
| scripts/src、collect.py | legacy / unreviewed-market | 解析、精度、分页、恢复和存储机制可复用 | P03 |
| scripts/tests | legacy / offline-regression | 机制回归；通过不代表市场数据合格 | P03–P05 |
| scripts/check_secrets.py、hooks | retained / engineering | 本地凭证隔离检查，仍暂停远程发布 | 持续 |
| scripts/select_uu_research.py、SELECTION_PLAN、SELECTION_REPORT | current / P02-delivered | 有限选品调查、原身份错误修订与名单说明，不运行旧评分 | P02 |
| data/local/universes/uu_research_selection_20261012T235228+0800_v1_1_b74608 | validated / P03-scope-only | 10 主力、6 候补；训练及买入用途未批准 | P03 |
| data/local/staging/steamdt/p02_*、scripts/local/selection_sources | candidate / private-traceable | 两个调查运行、48 请求、精确源码和原始证据，旧版本保留 | P02–P03 |
| scripts/pilot_uu_day.py | retained / engineering-pilot | 单品单日有预算试跑和离线核验，未完成完整爬虫验收 | P03 |
| data/local/staging/steamdt 单日试跑 | candidate / L0 | 24 个 UU 小时价格桶；量额有缺失、逐笔平台未确认，不用于训练 | P03 |
| docs/local/pilots、scripts/local/pilot_sources | private / traceable | 试跑质量报告与实际执行源码的准确内容版本 | 持续 |
| scripts/manage_assets.py、FILE_CATALOG | current-management | 每个文件及目录的版本、用途与完整性检查 | 持续 |
| scripts/config/seeds、watchlist | legacy / research-clue | 旧精确种子及用户举例线索，非正式名单 | P02 |
| scripts/sql、config/vscode.code-workspace | legacy / diagnostic | 旧库只读诊断参考 | P03–P04 |
| data/local/database、raw | legacy / unreviewed | 旧行情、成交与来源证据；保留原路径与内容 | P03–P04 |
| data/local/universes 根层旧 JSON | legacy / unreviewed | 旧候选快照，不沿用旧数量或权重；新版本目录按其明确批准用途管理 | P02 |
| data/local/recon、archive、api_cache | legacy / reference | 接口、事件、初始采集与目录证据；已去除两份相同副本 | P03–P05 |
| data/samples/pilot_20261011 | already-public / frozen | 旧匿名快照与离线解析样本，非 UU 正式训练集 | P04、P06 |
| docs/data、usage、research/UNIVERSE、releases | legacy / documentation | 字段、接口限制、历史方法与公开版本追溯 | 对应部分 |
| docs/local/progress、data/local/progress | private / historical | 当前文字交接和冻结 JSON 历史；不能自动恢复旧任务 | 持续 |
| data/local/manifests | private / current-management | 整理前基线、迁移删除明细与私有版本清单 | 持续 |
| scripts/config/.env、旧归档凭证 | private / protected | 仅供授权操作，未展示、转发或加入 Git | 持续 |
| GitHub v0.1–v0.3 | already-public / frozen | 既有事实；未变更远程历史或可见性 | P06 |

本次 11 项删除均列入私有 layout-1.0-changes.json，说明依据、哈希与 Git blob 或保留副本。重复 DESIGN/ROADMAP 索引由 PLAN/STATE 取代；旧单文件代码、旧测试及 VERSION 已有完全一致的 Git 历史，无需保留第二份。文件内容版本和各子目录说明详见 FILE_CATALOG 与私有清单。

旧记录曾报告 44,502 个目录规格、119,520 条小时行情、1,420 条成交；本次未查询旧库重新验证。主力验证名单 **10**、候补 **6**；已验收正式数据集与模型仍为 **0**。
