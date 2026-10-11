# 参与开发

需要 Python 3.11 或以上与 Git。无需安装 Python 依赖。

```bash
git config core.hooksPath .githooks
python -m unittest discover -s tests -v
python scripts/check_secrets.py
```

使用功能分支提交改动，说明具体问题、最终行为和验证结果。数据字段变更同步更新 `docs/data/DATA_DICTIONARY.md`；功能与修复同步更新 `CHANGELOG.md`。

采集输出保留在 Git 忽略的 `data/local/`。如果需要更新公开样本，先挑选匿名公开资料，保留来源与校验值，再运行完整测试及密钥检查；不得直接复制带认证信息的日志或本地配置。

测试默认离线，不调用付费或限额接口，不需要 `config/.env`。官方接口的真实验证需由维护者在本地运行，不把个人密钥放入 CI、测试代码、截图或 issue。

版本号采用 `MAJOR.MINOR.PATCH`，正式标签形如 `v0.1.0`。第一代处于 0.x 阶段，数据口径与接口仍会迭代，破坏性变更需记录迁移说明。

源码位于 `src/cs_youoweme/`，入口脚本位于 `scripts/`。公开样本放在 `data/samples/`，每批分别保存 raw / tables / reports。版本以 `src/cs_youoweme/__init__.py` 为唯一来源。
