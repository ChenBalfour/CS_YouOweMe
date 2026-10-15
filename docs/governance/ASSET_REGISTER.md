# 既有资产登记

登记版本 asset-register-2.5，2026-10-16。当前成果和卡点统一见 [PROGRESS](../PROGRESS.md)，产品与实现分别见 [PRODUCT](../PRODUCT.md)、[ARCHITECTURE](../ARCHITECTURE.md)。本页只登记资产用途与保留/清理依据。

| 资产/位置 | 状态 | 用途与保留依据 | 后续部分 |
| --- | --- | --- | --- |
| scripts/steamdt_research.py、对应Notebook/初始清单、data/local/staging/steamdt/research_20261016_v1 | candidate / L0-research | 独立小时库、商品映射、分页回补/续采、近期增量复核与修订证据；按实际报告检查覆盖，不直接训练或执行 | P03 |
| UU_HISTORY_CHART、data/local/recon/user_uu_history_chart_20261014 | current / user-evidence-pending-verification | UU历史在售数量/成交价格与BUFF辅助入口可见；已取得用户价格附件与数量聊天投影；核验字段及本次间隔，身份/统计/其他窗口待验收，证据私有 | P03 |
| PRODUCT、ARCHITECTURE、PROGRESS | current / primary-documents | 产品、架构和进展的三个主入口；每次操作写入成果 | 持续 |
| collect_uu_charts.js、import_uu_chart_batch、uu_history_collect.ipynb、UU_HISTORY_COLLECT | delivered / offline-tested-live-pending | 已按截图修正为价格4窗口/数量3窗口；真实旧批次3成功/1失败/4待采、639点保留，恢复为正确7组中的3成功/4待采；新1.1完整七组1335条已离线入库，单轮基础质量通过，多轮稳定性待验收，没有训练 | P03 |
| collect_uu_direct.py、UU_DIRECT_COLLECT、私有direct运行及review_v1 | delivered / single-item-live-checked / L0 | 用户44828完整七组1360条窗口记录，原JSON/SQLite/CSV与冻结源码核验通过；保留962个不同指标/时间点及全部跨窗关系，时效/混合间隔已记录；多商品/多轮/身份/统计待验收，无训练 | P03 |
| review_uu_chart、UU_CHART_EXPORT、data/local/staging/uu_charts | current / offline-structure-checked | 纯离线工具与私有价格附件/数量投影，169/93点及实际间隔已核验；身份/统计/历史可得时间未验收，非正式训练资产 | P03 |
| PLAN、STATE、HANDOFF、私有CURRENT | retained / compatibility-entry | 旧路径保留导航，不维护重复正文；清理前全文有Git/私有恢复记录 | 持续 |
| 旧PROGRESS_20261013、UNIVERSE、三份release说明 | removed / recoverable-history | 已被当前进展/选品或CHANGELOG接管，从工作目录清理；Git babb125保留原文 | 持续 |
| P03_VERIFICATION_PLAN、P03_VERIFICATION_REPORT、UU_FIELD_CONTRACT、UU_EXECUTION_RULES | current / P03-delivered | 范围预算、字段口径、规则时效、有限结果与执行缺口 | P03 |
| scripts/notebooks/uu_observe_24h.ipynb、observe_uu_24h.py、history/observe.py | current / user-first-round-checked | 用户本地显式运行、固定截止与恢复入口；首轮已保存，用户输出保留，24 小时未验收 | P03 |
| SELECTION_REVISION_20261014、SELECTION_PLAN 1.2 | current / selection-rule-revision | 首批 [100,1000) 元、同档属性可比性及通用求购匹配，7 个旧百元主力待复核 | P02–P03 |
| data/local/recon/user_attribute_scope_20261014 | private / user-evidence | 用户两张求购截图及哈希，拍摄时间未知；仅可见行证据，不公开买家信息 | P02–P03 |
| data/local/staging/steamdt/p03_steamdt_observe_20261014T101536+0800_4f3ccd | private / L0-first-round-checked | 用户运行后中断，2/48 样本成功、5 次请求成功；保留独立库、原始响应与恢复窗口 | P03 |
| P03_OBSERVATION_PLAN、usage/OBSERVE_24H | current / user-run-guide | 连续观察预算、启动停止恢复、Notebook 输出和真实验收限制 | P03 |
| verify_public_evidence、verify_uu_fields、review_uu_verification、history/verification | retained / bounded-verification | 只读证据、来源比较、离线核对和保守解析；不自动重试受限入口 | P03 |
| data/local/staging/steamdt/p03_steamdt_uu_20261013* | validated / L0-scope-only | 两规格小时表和已核对的来源混合逐笔；UU 执行用途未通过 | P03 |
| data/local/staging/steamdt/p03_steamdt_fields_* | validated / L0-scope-only | 来源 UU 汇总价格与数量；单件深度未核验、交叉报价标异常 | P03 |
| data/local/recon/p03_20261013_evidence | private / traceable | 15 份完整公开脚本/规则响应和 UU 429 状态；不是订单数据 | P03 |
| scripts/src、collect.py | legacy / unreviewed-market | 解析、精度、分页、恢复和存储机制可复用 | P03 |
| scripts/tests | legacy / offline-regression | 机制回归；通过不代表市场数据合格 | P03–P05 |
| scripts/check_secrets.py、hooks | retained / engineering | 本地凭证隔离检查，仍暂停远程发布 | 持续 |
| scripts/select_uu_research.py、SELECTION_REPORT | retained / P02-historical | 原有限选品调查和名单；未实现新属性门槛，不据旧脚本自动重选 | P02 |
| data/local/universes/uu_research_selection_20261012T235228+0800_v1_1_b74608 | validated / original-P03-scope-only | 原 10 主力、6 候补不覆盖；百元/属性新规则待复核，训练及买入用途未批准 | P03 |
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
| docs/data、usage、releases/CHANGELOG | retained / specialized-documents | 当前字段/运行指南与旧接口参考、集中版本历史；不是第二套产品或进度 | 对应部分 |
| docs/local/progress、data/local/progress | private / historical | 当前文字交接和冻结 JSON 历史；不能自动恢复旧任务 | 持续 |
| data/local/manifests | private / current-management | 整理前基线、迁移删除明细与私有版本清单 | 持续 |
| scripts/config/.env、旧归档凭证 | private / protected | 仅供授权操作，未展示、转发或加入 Git | 持续 |
| GitHub v0.1–v0.3 | already-public / frozen | 既有事实；未变更远程历史或可见性 | P06 |

本次 11 项删除均列入私有 layout-1.0-changes.json，说明依据、哈希与 Git blob 或保留副本。重复 DESIGN/ROADMAP 索引由 PLAN/STATE 取代；旧单文件代码、旧测试及 VERSION 已有完全一致的 Git 历史，无需保留第二份。文件内容版本和各子目录说明详见 FILE_CATALOG 与私有清单。

旧记录曾报告 44,502 个目录规格、119,520 条小时行情、1,420 条成交；本次未查询旧库重新验证。原验证名单 **10**、候补 **6**，当前百元待复核主力线索 **7**，新版名单未冻结；已验收正式数据集与模型仍为 **0**。
