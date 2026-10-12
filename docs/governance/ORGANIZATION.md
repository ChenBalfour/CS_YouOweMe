# 文件整理与恢复记录

整理版本 layout-1.0，2026-10-12，北京时间；基线本地提交 `0ee7136`。用户明确要求略读、删除无用文件、按脚本/数据/文档归类，并为每个文件和文件夹登记版本与说明。本次为 P01 管理补充，完成后不自动进入 P02。

## 保留与迁移

| 原位置 | 当前位置 | 依据 |
| --- | --- | --- |
| src/、tests/、sql/、config/、.githooks/ | scripts/src/、tests/、sql/、config/、hooks/ | 实现、验证、查询及配置集中管理；原有凭证随 config 移动，仍被忽略 |
| CHANGELOG.md | docs/releases/CHANGELOG.md | 人类版本说明归入文档 |
| .github/CONTRIBUTING.md、SECURITY.md | docs/governance/ 同名文档 | 工程和安全说明归入文档；workflow 保留工具要求的位置 |
| data/local/progress/ 的两个 Markdown | docs/local/progress/ 同名文档 | 私有文字交接集中到文档；原 JSON 进度记录冻结保留 |

旧市场库、压缩响应、原始探测证据和已公开样本保持原路径与内容。最初试采的网页、质量报告、来源配置属于批次证据，随 data 保留；目录 README 是就近说明。根目录的 Git/Python 入口元数据有工具用途，已逐项登记。

## 清理依据

共删除 **11 个文件、12,196,772 字节（约 11.6 MiB）**，随后移除空目录。

| 类别 | 数量 | 删除依据与恢复 |
| --- | ---: | --- |
| DESIGN、ROADMAP 重复索引 | 2 | 已由 PLAN、STATE 提供相同入口；可从基线 Git 恢复 |
| Python .pyc 缓存 | 3 | 可由源代码再生成，无独有研究信息 |
| pre_refactor 的旧代码、测试、VERSION、重复 fixture | 4 | Git blob 完全一致，历史保存完整内容 |
| 官方目录和初始 seeds 的重复数据副本 | 2 | SHA-256 一致；分别保留 api_cache/base.json 与 scripts/config/seeds.json |

唯一历史证据不因“当前不训练”而删除。旧接口错误响应也用于识别失败口径；锁和配额状态未擅自清除。

## 每项版本与恢复

公开 [FILE_CATALOG](FILE_CATALOG.json) 记录每个 Git 管理文件及目录的用途、状态与内容版本。私有文件清单为 `data/local/manifests/workspace-layout-1.0.json`；整理前基线、逐项路径/理由/恢复映射及核对结果分别保存在该目录的 `layout-1.0-before.json`、`layout-1.0-changes.json`、`layout-1.0-verification.json`。

本地提交保存公开文件历史。恢复旧文件时从清理前提交或删除清单所列 Git blob 取回到独立恢复目录，核对哈希后再使用，不直接覆盖当前文件。重复数据按清单 retained_path 复制回原路径；缓存按需再生成。凭证没有内容快照或输出。

目录变动已同步 CLI 默认路径、测试、打包、工作区、CI 和本地 hooks，以及当前文档链接。39 项离线回归通过；491 份保留数据的 SHA-256 与整理前一致，另 1 份历史受保护配置仅确认保留、不读取或记录哈希。Markdown 本地链接与版本清单通过核对，打包版本为 0.3.1，暂存和历史凭证检查通过；没有调用市场接口或打开旧库。
