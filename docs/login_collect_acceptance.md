# 登录到店铺采集验收

2026-10-07，使用本人已登录 Chrome 会话中的请求 Cookie，仅经隐藏输入传入一次性 Python 进程。仓库 `DianpingAuth(None, headless=True).from_cookie()` 在临时内存浏览器配置中验证登录；随后同一配置执行 `DianpingAPI.search("咖啡", city_id=1)` 与首个结果的 `get_item()`。进程结束时关闭浏览器配置，没有保存 Cookie 或账号资料。

| 检查 | 结果 |
| --- | --- |
| 登录检查 | `from_cookie()` 内部 `require_login()` 通过 |
| 匿名对照 | 无 Cookie 的临时配置调用 `require_login()` 抛 `AccessRequired` |
| 搜索 | 实际返回 15 条店铺结果 |
| Item | 首条搜索结果的店铺 ID 与详情 ID 一致，标题和描述均非空 |
| 测试套件 | `python -m pytest -q`：13 passed |

这验证了已有登录态导入后的“认证 → 店铺搜索 → 店铺 Item”只读闭环。独立持久窗口里的扫码登录、笔记搜索与笔记/点评 Item 未纳入本次实测；消费者 Web 发布入口仍未核实。
