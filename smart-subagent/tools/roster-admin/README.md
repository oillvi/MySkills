# roster-admin — smart-subagent 花名册可视化管理

单页 HTML + 本地后端（Python 标准库，零第三方依赖），统一管：
模型别名/ref/kind/备注、自定义 provider 的 baseUrl/apiKey/模型名单、agent 名单、routing、on_out_of_roster。
页面上可对账（check-roster.py --menu）、校验、逐模型探活（GET /models 最小请求）。

## 用法

1. **一次性安装**：双击 `install.bat`（注册 `roster-admin://` 协议到 HKCU，免提权）。
   不想注册协议就直接双击 `start.bat`。
2. **日常入口**：双击 `花名册管理.html`。
   - 打开 = 自动唤起后端（浏览器首次会弹一次「打开外部程序?」，勾选记住即静默）。
   - 关闭最后一个页面 = 后端约 12 秒后自动退出（页面心跳保活）。
3. 编辑后点「保存全部」/「保存此 Provider」。写盘前自动备份：
   `roster.yml.bak.<时间戳>`、`settings.json.bak.<时间戳>`（各留最近 10 份）。

## 安全边界

- 后端只绑 `127.0.0.1:8765`，不对外。
- API key 页面默认打码，「显形」按钮按需回显；日志不打印明文 key。
- `settings.json` 里 provider 之外的字段原样保留；无 `isNew` 不会误建 provider。
- 钉桩（agents/*.md 的 frontmatter `model:`）只读展示，本工具不改 agent 定义文件。

## 测试（可复现）

```bash
python tools/roster-admin/test_edit_roster.py    # 编辑器单测：no-op 零字节差 / 增删改 / 字段删除还原
python tools/roster-admin/verify_ui.py           # 无头 Edge 验渲染（DOM 计数+截图，输出到 %TEMP%，不碰用户浏览器）
```

## 文件

| 文件 | 作用 |
|---|---|
| `花名册管理.html` | 双击入口；file:// 打开时唤起后端，同文件也由后端 `/` 提供 |
| `server.py` | 后端：state/check/ping/reveal/save-roster/save-provider/heartbeat/goodbye；`--install`/`--uninstall` 管协议 |
| `launcher.vbs` | `roster-admin://` 协议唤起器（静默起 server.py，已有实例则自退） |
| `install.bat` / `uninstall.bat` / `start.bat` | 协议注册 / 注销 / 手动兜底入口 |
| `test_edit_roster.py` | roster.yml 外科式编辑单测 |
| `verify_ui.py` | 无头 Edge 页面验收 |
