# 参与开发

工程说明版本 engineering-1.1，目录 layout-1.0。Python 3.11+，运行代码无第三方依赖。

```powershell
git config core.hooksPath scripts/hooks
python -B -m unittest discover -s scripts/tests -v
python -B scripts/collect.py --version
python -B scripts/manage_assets.py --write
python -B scripts/manage_assets.py --check
python -B scripts/check_secrets.py --staged
```

源码集中在 scripts/src/cs_youoweme，版本唯一来源为其 __init__.py；pyproject 使用相同版本。代码及配置变化同步测试、对应说明、STATE、[CHANGELOG](../releases/CHANGELOG.md)和文件清单。公开清单加入本地 Git，私有清单只留在忽略目录。

当前一次完成指定部分，新增 push、PR、release 暂停。研究资产准入见 [资产登记](ASSET_REGISTER.md)，文件布局与版本规则见 [文件制度](FILE_MANAGEMENT.md)，研究范围见 [主计划](../research/PLAN.md)。离线测试不调用真实接口，不需要真实凭证，也不证明 UU 数据合格。
