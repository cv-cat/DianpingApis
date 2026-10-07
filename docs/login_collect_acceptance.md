# HTTP 登录与采集验收

## 已完成

- `DianpingAuth` 已改为 `requests.Session`，仓库无浏览器启动、页面控制或浏览器配置读取。
- `DianpingAuth.from_cookie()` 使用 `GET /note/create` 做登录态预检，并识别账号跳转、验证域名和验证页。
- 匿名 HTTP 访问 `https://www.dianping.com/discovery/` 可以解析 `window.__dx_dump__`，筛选精选笔记，再读取 `https://m.dianping.com/discovery/{id}` 的标题和正文。
- `DianpingAPI.search()`、`search_notes()`、`get_item()` 和 `get_shop()` 均通过 HTTP 响应解析。
- 二维码图片和轮询请求契约已按登录页真实路由封装；H5guard 指纹/签名仍由正常登录链路提供。

## 当前边界

- 没有把账号 Cookie、二维码、`qruuid`、`h5_fingerprint` 或 `mtgsig` 写入仓库。
- `getQrCodeImg`/`check` 的实际登录成功需要调用方传入当前有效的 H5guard 值并在官方 App 扫码。
- `/note/create` 不是已核实的消费者 Web 发笔记接口；店铺点评写入也未得到可独立复现的 HTTP 契约，所以发布方法明确抛 `PublishingUnavailable`。

## 测试

```text
python -m pytest -q   # 18 passed
```

测试使用本地假的 HTTP 响应，只验证请求参数、响应解析和状态判断，不触发真实账号写入。
