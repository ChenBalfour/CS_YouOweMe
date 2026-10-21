# 参与开发

工程说明版本 engineering-1.3，目录 layout-1.0。Python 3.11+，冻结采集核心无第三方依赖，研究图表/完整离线测试需要Matplotlib。

```powershell
git config core.hooksPath scripts/hooks
python -m pip install ".[test]"
python -B -m unittest discover -s scripts/tests -v
python -B scripts/collect.py --version
python -B scripts/manage_assets.py --write
python -B scripts/manage_assets.py --check
python -B scripts/check_secrets.py --staged
```

冻结核心源码在scripts/src/cs_youoweme，核心版本来自其__init__.py，pyproject使用相同版本；新研究代码按scripts/research下data/models/evaluation/visualization分包，各组件与产物独立版本化。每次操作更新 [主进展](../PROGRESS.md)，涉及产品/架构的变化同步 [产品](../PRODUCT.md)与 [架构](../ARCHITECTURE.md)。代码及配置变化执行相应检查，更新对应说明、[CHANGELOG](../releases/CHANGELOG.md)和文件清单。公开清单加入本地 Git，私有清单只留在忽略目录。

完成用户指定范围；2026-10-19已授权本轮公开分支push和迭代PR，不自动远程合并、强推或打release标签。提交时排除用户Notebook执行输出，并按暂存版本生成公开清单；提交后恢复工作副本清单，具体见文件制度。研究资产准入见 [资产登记](ASSET_REGISTER.md)，文件布局与版本规则见 [文件制度](FILE_MANAGEMENT.md)，研究范围见 [产品说明](../PRODUCT.md)。离线测试不调用真实接口，不需要真实凭证，也不证明 UU 数据合格。
