"""Generate or verify file/folder version catalogs without running collectors."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = "layout-1.0"
PUBLIC = "docs/governance/FILE_CATALOG.json"
PRIVATE = "data/local/manifests/workspace-layout-1.0.json"
INDEX = "docs/governance/FILE_INDEX.md"
CATALOGS = {PUBLIC, PRIVATE, INDEX}

PURPOSES = {
    "README.md": "项目入口、当前状态与三类目录索引",
    "AGENTS.md": "协作者的执行、阶段、凭证及发布约束",
    "LICENSE": "原创代码与文档的 MIT 授权",
    "pyproject.toml": "Python 打包配置及单一源码版本入口",
    ".gitignore": "私有数据、文档、凭证与生成缓存的 Git 排除规则",
    ".gitattributes": "跨平台文本换行规则",
    ".github/workflows/ci.yml": "既有远程离线检查工作流，根目录位置由 GitHub 约定",
    "scripts/README.md": "代码、配置、测试、SQL 和检查入口说明",
    "scripts/collect.py": "旧采集 CLI 的薄入口，当前不恢复采集",
    "scripts/check_secrets.py": "暂存区及 Git 历史的凭证隔离检查，不打印真实值",
    "scripts/manage_assets.py": "生成及校验逐文件、逐目录版本和用途清单",
    "scripts/config/seeds.json": "旧试采精确英文规格种子，不是正式 UU 名单",
    "scripts/config/watchlist.json": "流金王朝、燃料喷射器等旧调查线索",
    "scripts/config/.env.example": "公开的空白凭证配置模板",
    "scripts/config/vscode.code-workspace": "旧库可选 SQLTools 工作区配置",
    "scripts/hooks/pre-commit": "本地提交前的暂存凭证检查",
    "scripts/hooks/pre-push": "历史凭证检查；新增远程推送仍暂停",
    "docs/README.md": "当前计划、制度、历史参考和整理说明索引",
    "data/README.md": "私有数据与已公开冻结样本的生命周期说明",
    "docs/research/PLAN.md": "唯一研究主计划 plan-1.0",
    "docs/research/UNIVERSE.md": "旧筛选方法和候选说明，仅作历史参考",
    "docs/governance/STATE.md": "当前阶段、版本和停止点",
    "docs/governance/HANDOFF.md": "人类与 agent 交接，以及本地与远程版本差异",
    "docs/governance/FILE_MANAGEMENT.md": "文件布局、资产生命周期、版本、迁移及发布制度",
    "docs/governance/ASSET_REGISTER.md": "旧资产保留依据及按用途准入状态",
    "docs/governance/ORGANIZATION.md": "layout-1.0 整理结果、迁移、清理及恢复方法",
    "docs/governance/CONTRIBUTING.md": "本地工程修改与检查方法",
    "docs/governance/SECURITY.md": "凭证隔离与安全问题处理说明",
    PUBLIC: "公开文件及目录的用途、版本和内容哈希索引",
    INDEX: "逐文件与逐目录用途和内容版本的可读索引，由 manage_assets 生成",
    "docs/data/DATA_DICTIONARY.md": "旧公开快照表的字段字典",
    "docs/data/DATA_SOURCES.md": "旧来源、采集证据及口径限制",
    "docs/data/HISTORY_SCHEMA.md": "旧历史库 schema v2、时间与字段口径",
    "docs/usage/COLLECTION.md": "旧采集器的接口、配置和输出说明",
    "docs/usage/HISTORY.md": "旧目录、候选、历史任务及查询命令参考",
    "docs/usage/DATABASE.md": "旧库的可选查询、时间精度与备份方法",
    "docs/releases/CHANGELOG.md": "代码历史变更及未发布本地版本说明",
}

SOURCE_PURPOSES = {
    "__init__.py": "模块身份及包版本或职责说明",
    "__main__.py": "Python 模块形式的 CLI 入口",
    "cleaning.py": "规格、价格、数量、币种与时间标准化",
    "cli.py": "命令注册、参数与工作流调度",
    "config.py": "旧种子与受保护本地凭证读取",
    "errors.py": "安全可展示的采集异常类型",
    "parsing.py": "Nuxt 响应解析及精确商品匹配",
    "paths.py": "独立于工作目录的项目、配置与数据路径",
    "storage.py": "原始证据、快照表、报告与本地 SQLite 存储",
    "transport.py": "HTTP 传输及凭证重定向限制",
    "official.py": "旧官方 API 客户端、缓存与配额节奏",
    "public.py": "旧公开页面采集流程",
    "website.py": "旧匿名网页接口客户端、时钟同步与访问停止",
    "aggregate.py": "行情聚合，保留缺失和覆盖语义",
    "catalog.py": "目录身份、来源平台编号及搜索映射",
    "jobs.py": "有预算的分页任务、恢复与原子检查点",
    "normalize.py": "逐笔及行情精度、时间和空值验证",
    "query.py": "旧库覆盖、状态、参数化查询和导出",
    "store.py": "旧库 schema、事务、压缩归档和 worker 锁",
    "universe.py": "旧候选筛选实现，仅机制参考，不沿用为新选品规则",
    "schema.sql": "旧历史库表、索引与任务结构 schema v2",
}

FOLDERS = {
    ".": "项目根及 Git/Python 所需入口元数据",
    ".github": "GitHub 工具约定的根目录配置",
    ".github/workflows": "既有自动检查配置",
    "scripts": "所有可执行代码及其工程配套",
    "scripts/src": "Python 包源码",
    "scripts/src/cs_youoweme": "旧技术实现，可按对应用途审查复用",
    "scripts/src/cs_youoweme/collectors": "旧公开页面、官方和匿名接口采集机制",
    "scripts/src/cs_youoweme/history": "旧目录、分页任务、SQLite、查询和候选机制",
    "scripts/tests": "离线与合成回归测试",
    "scripts/sql": "旧历史库只读诊断查询",
    "scripts/config": "脚本配置、空白模板与受保护本地凭证",
    "scripts/hooks": "本地 Git 凭证检查 hooks",
    "data": "来源数据及其伴随元数据",
    "data/samples": "已公开、冻结待复审的旧匿名样本",
    "data/local": "私有历史证据与本地运行产物，不加入 Git",
    "data/local/manifests": "私有文件清单、整理前基线及逐项迁移删除记录",
    "data/local/database": "旧 SteamDT 试采库及其伴随原始证据",
    "data/local/database/raw": "旧来源内容寻址压缩响应",
    "data/local/api_cache": "旧官方目录与配额状态缓存，不自动刷新",
    "data/local/archive": "最初试采历史证据与受保护旧配置",
    "data/local/recon": "按日期保存的接口与事件探测证据",
    "data/local/universes": "旧候选快照，不是正式 UU 名单",
    "data/local/progress": "旧进度 JSON 记录，当前文字交接迁入 docs/local/progress",
    "docs": "计划、制度、使用说明和交接记录",
    "docs/governance": "管理、阶段、资产登记与版本索引",
    "docs/research": "唯一主计划与旧研究参考",
    "docs/data": "来源、schema 与字段说明",
    "docs/usage": "旧实现使用参考，非执行授权",
    "docs/releases": "历史发布与本地版本变更说明",
    "docs/local": "私有交接文档，不加入 Git",
    "docs/local/progress": "当前本地交接与旧历史交接文档",
}

def protected(path):
    name = path.name.lower()
    return ((name.startswith(".env") and name != ".env.example")
            or name.endswith((".key", ".pem")) or name.startswith("credentials"))

def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

def code_version():
    tree = ast.parse((ROOT / "scripts/src/cs_youoweme/__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("Missing source package version")

def git_public_paths():
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT, capture_output=True, check=True)
    paths = {name.decode("utf-8") for name in result.stdout.split(b"\0") if name}
    return {p for p in paths if (ROOT / p).is_file() and not p.startswith(("data/local/", "docs/local/")) and not protected(ROOT / p)} | {PUBLIC, INDEX}

def purpose(path):
    if path in PURPOSES:
        return PURPOSES[path]
    name = Path(path).name
    if protected(Path(path)):
        return "受保护本地凭证，仅登记配置版本，不读取、复制或记录内容及哈希"
    if path.startswith("scripts/src/"):
        return SOURCE_PURPOSES[name]
    if path.startswith("scripts/tests/"):
        return "离线测试辅助与共享样本路径" if name == "_support.py" else f"{name[5:-3]} 模块的离线行为回归测试"
    if path.startswith("scripts/sql/"):
        return {"01_catalog.sql": "旧库目录搜索与身份查询", "02_universe.sql": "旧候选名单查询", "03_market.sql": "旧逐笔与行情查询", "04_coverage.sql": "旧覆盖和分页进度诊断"}[name]
    if path.startswith("docs/releases/v"):
        return f"{Path(name).stem} 已发布版本的历史说明"
    if path.startswith("data/samples/"):
        return "旧匿名公开样本的" + ({".csv": "派生表", ".md": "质量说明"}.get(Path(name).suffix, "来源响应或来源清单")) + "，冻结待 UU 用途复审"
    if path.startswith("data/local/database/raw/"):
        return "旧来源的内容寻址压缩响应，保留数据库请求追溯"
    if path.startswith("data/local/database/"):
        return "旧 SteamDT 试采库，非正式 UU 数据集" if name.endswith(".sqlite") else "旧库 worker 锁状态文件，保留原状"
    if path.startswith("data/local/api_cache/"):
        return "旧官方目录缓存，重复 recon 目录文件的保留副本" if name == "base.json" else "旧来源配额时间状态，不自动刷新"
    if path.startswith("data/local/recon/"):
        return f"{Path(name).stem} 接口或事件探测的原始历史证据，保留待核验"
    if path.startswith("data/local/universes/"):
        return f"{Path(name).stem} 旧候选快照，不是正式 UU 名单"
    if path.startswith("data/local/archive/"):
        return "最初试采的原始响应、表、报告或配置证据，保留来源追溯"
    if path.startswith("data/local/manifests/"):
        return {"layout-1.0-before.json": "整理前逐文件大小与哈希基线，凭证不记录哈希", "layout-1.0-changes.json": "逐项迁移、删除依据与 Git/保留副本恢复路径", "layout-1.0-verification.json": "迁移后保留数据哈希核对与检查结果", Path(PRIVATE).name: "私有文件和目录的版本及用途清单"}.get(name, "本地版本及检查元数据")
    if path.startswith(("data/local/progress/", "docs/local/progress/")):
        return "当前本地交接入口" if name == "CURRENT.md" else "旧进度历史记录，不能据此恢复采集"
    if path == "data/local/README.md":
        return "私有历史数据的本地用途与管理索引"
    raise ValueError(f"Missing purpose for {path}")

def folder_purpose(path):
    if path in FOLDERS:
        return FOLDERS[path]
    for prefix, label in (("data/local/database/raw/", "旧压缩响应的哈希分桶"), ("data/local/archive/", "最初试采历史证据的分组"), ("data/local/recon/", "按日期保存的来源探测证据"), ("data/local/api_cache/", "按本地凭证标识隔离的旧缓存，不公开标识"), ("data/samples/", "旧匿名样本批次及原始/表/报告分组")):
        if path.startswith(prefix):
            return label
    if path.startswith("data/local/"):
        return purpose(path + "/_directory.json").replace("_directory 接口或事件探测", "接口或事件探测")
    raise ValueError(f"Missing folder purpose for {path}")

def catalog(paths, private=False):
    rows = []
    for path in sorted(paths):
        item = ROOT / path
        hidden = protected(item)
        checksum = None if hidden or path in CATALOGS else digest(item)
        rows.append({"path": path, "purpose": purpose(path), "status": "private-protected" if hidden else "private-legacy-or-metadata" if private else "legacy-unreviewed" if path.startswith(("scripts/src/", "scripts/tests/", "data/samples/")) else "current-or-reference", "version": "protected-local-1" if hidden else LAYOUT + ".catalog" if path in CATALOGS else "sha256:" + checksum, "sha256": checksum, "bytes": None if path in CATALOGS or hidden else item.stat().st_size})
    folders = {"."}
    for row in rows:
        folders.update(p.as_posix() for p in Path(row["path"]).parents if p.as_posix() != ".")
    if private:
        folders.update(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_dir() and ".git" not in p.relative_to(ROOT).parts and p.relative_to(ROOT).as_posix().startswith(("data/local", "docs/local")))
    directories = []
    for folder in sorted(folders):
        members = [(r["path"], r["version"]) for r in rows if folder == "." or r["path"].startswith(folder + "/")]
        version = hashlib.sha256(json.dumps(members, ensure_ascii=False).encode()).hexdigest()
        directories.append({"path": folder, "purpose": folder_purpose(folder), "layout_version": LAYOUT, "version": "sha256:" + version})
    return {"schema_version": 1, "layout_version": LAYOUT, "code_version": code_version() + "-local-unreleased", "scope": "private-ignored-files" if private else "git-managed-files", "hash_policy": "SHA-256; generated catalogs exclude their own bytes to avoid circular hashes; protected credentials have no content/hash snapshot", "directories": directories, "files": rows}

def serialize(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"

def readable_index(public):
    lines = ["# 文件与目录说明", "", f"自动生成，目录版本 {LAYOUT}，代码 {code_version()}（本地未发布）。完整 SHA-256 见 [机器清单](FILE_CATALOG.json)。私有逐项清单只在 data/local/manifests/workspace-layout-1.0.json；Git 内部对象由 Git 管理。生成清单使用固定目录版本，不计算自身哈希以避免循环。", "", "## 目录", "", "| 路径 | 用途 | 内容版本（摘要） |", "| --- | --- | --- |"]
    for row in public["directories"]:
        link = "../.." if row["path"] == "." else "../../" + row["path"]
        lines.append(f"| [{row['path']}]({link}) | {row['purpose']} | {row['version'][:19]} |")
    lines += ["", "## 文件", "", "| 路径 | 用途 | 内容版本（摘要） |", "| --- | --- | --- |"]
    for row in public["files"]:
        lines.append(f"| [{row['path']}](../../{row['path']}) | {row['purpose']} | {row['version'][:19]} |")
    return "\n".join(lines) + "\n"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    public_paths = git_public_paths()
    all_paths = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.relative_to(ROOT).parts}
    private_paths = (all_paths - public_paths) | {PRIVATE}
    # Generated cache files are not research assets and must not enter catalogs.
    private_paths = {p for p in private_paths if not p.endswith(".pyc") and "__pycache__" not in Path(p).parts}
    public_catalog = catalog(public_paths)
    expected = {PUBLIC: serialize(public_catalog), PRIVATE: serialize(catalog(private_paths, private=True)), INDEX: readable_index(public_catalog)}
    for path, content in expected.items():
        destination = ROOT / path
        if args.write:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="\n")
        elif not destination.exists() or destination.read_text(encoding="utf-8") != content:
            print("Catalog differs; regenerate with --write after reviewing the change.")
            return 1
    print(f"Catalog {'written' if args.write else 'verified'}: {len(public_paths)} public files, {len(private_paths)} private files; no private paths or values printed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
