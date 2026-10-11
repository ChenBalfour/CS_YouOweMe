# 凭证与发布

真实 SteamDT 密钥只使用本地 `config/.env` 或环境变量。公开 `config/.env.example` 必须为空白模板；不要把真实值写入示例、文档、提交消息或 issue。

`.gitignore` 排除本地配置、数据库、API 缓存和采集目录。首次发布前，本项目使用已知本地密钥检查全部待发布文件和 Git 历史，结果只显示文件位置和检查状态，不显示密钥值。

启用本地提交与推送检查：

```bash
git config core.hooksPath .githooks
python scripts/check_secrets.py --staged
python scripts/check_secrets.py --history
```

检查覆盖已知本地密钥及常见编码形式、非空 SteamDT 配置赋值、意外加入 Git 的凭证文件和常见 GitHub/云凭证格式。静态检查不能识别所有自定义凭证；发布前也应确认文件范围。

若凭证已经公开，应先在发行方撤销或轮换，再清理公开内容与 Git 历史。删除最新版本中的文件不能清除旧提交。报告安全问题时只描述位置和行为，不公开凭证值。
