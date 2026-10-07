# Web 扫码登录链路

在本人 Chrome 中通过开发者工具观察到以下请求。仓库的 `DianpingAuth.login()` 使用可见浏览器完成这一流程，避免缓存本次会话的动态指纹、签名和二维码标识。

1. `GET https://account.dianping.com/pclogin?redir=...` 加载登录页；页面调用 `POST https://m.dianping.com/account/ajax/checkLogin` 检查现有会话。
2. `GET https://accountapi.dianping.com/mlogin/dp/api/v1/qrlogin/getQrCodeImg` 取得二维码图片，响应设置 `qruuid` Cookie。
3. 页面轮询 `GET https://accountapi.dianping.com/mlogin/dp/api/v1/qrlogin/check`，查询参数包含 `qruuid`。两类请求还带 `risk_app`、`risk_partner`、`risk_platform`、`h5_fingerprint`、`yodaReady`、`csecplatform`、`csecversion` 等参数。
4. 完成扫码后，最后一次轮询响应设置登录 Cookie，浏览器跳转回 `redir` 页面。

本次 DevTools 保留了路由、状态和响应头，但二维码图片与轮询 JSON 响应体已不可用，故没有验证轮询的业务状态码。HTTP 200 不代表扫码完成。文档不含本人的二维码、Cookie 值、`qruuid`、指纹或签名值。

