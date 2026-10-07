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

## 内容精选笔记读取

另用公开 HTTP（无 Cookie）访问官方 `https://www.dianping.com/discovery/`，从页面内 `window.__dx_dump__` 读取当前精选流条目；用仓库 `DianpingAPI.search("咖啡", kind="note")` 筛选标题，得到 2 条。取首条 `https://m.dianping.com/discovery/{id}`，仓库 `get_item()` 读到相同 ID、`kind=note`、20 字标题和 283 字正文。该实测使用只读 HTTP 页面适配器调用仓库 API；没有测试带登录态的 Playwright 浏览器笔记流程，也不是全站关键词检索。脚本位于任务工作目录 `dianping_content_gap/live_discovery_probe.py`。

`/review/{id}` 的公开 HTTP 请求重定向至 `verify.meituan.com`，`/note/{id}` 当前返回 403，因此店铺点评 Item 和原生笔记详情仍未完成在线闭环。通用“发现好去处”页面现在会被识别为 `ElementMissing`，避免误判为内容详情。

## 精选流分页补测

公开 HTTP 的官方精选页可以按分类和页码读取：`/discovery/a/10` 与 `/discovery/a/10/p2` 均返回包含 `window.__dx_dump__` 的 80 条 feed 数据；仓库 `search_notes("咖啡", category_id=10, page=1/2)` 分别筛得 3 条和 4 条。根路径 `/discovery/p2` 在本次请求返回 403，因此客户端不把它当作可用的全站分页接口。该能力仍是分类精选流标题筛选，不是全站笔记关键词搜索。
