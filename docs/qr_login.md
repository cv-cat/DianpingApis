# 大众点评二维码 HTTP 链路

2026-10-07 从登录页观察到的请求顺序如下，原始指纹、签名、Cookie 和二维码内容不落盘：

1. `GET https://msp.meituan.com/web/cache-token` 与 `cache-token-p`。`DianpingAuth.bootstrap_guest()` 按此顺序建立匿名会话。
2. `POST https://msp.meituan.com/v1/webdfpid`，建立设备指纹上下文。
3. `POST https://msp.meituan.com/v1/i/osake/junmai` 与 `ginjo`，初始化风控上下文。
4. 页面完成 H5guard 初始化后，`POST https://m.dianping.com/account/ajax/checkLogin?yodaReady=h5&csecplatform=4&csecversion=4.3.0&mtgsig=...`，请求体为空。`mtgsig` 在这里位于查询参数。
5. `GET https://accountapi.dianping.com/mlogin/dp/api/v1/qrlogin/getQrCodeImg`，参数顺序为 `risk_app`、`risk_partner`、`risk_platform`、`h5_fingerprint`、`yodaReady`、`csecplatform`、`csecversion`，请求头含当前 `mtgsig`。响应为 JPEG，并设置 `qruuid` Cookie。
6. 用户在官方 App 扫码后，轮询 `GET https://accountapi.dianping.com/mlogin/dp/api/v1/qrlogin/check`，参数顺序为 `qruuid`、三项风险参数、`h5_fingerprint`、`yodaReady`、`csecplatform`、`csecversion`，签名仍在 `mtgsig` 请求头。

仓库已经把第 1、4、5、6 步封装为 `DianpingAuth.bootstrap_guest()`、`start_qr_login()` 和 `poll_qr_login()`。H5guard 生成的指纹和签名是短时动态值，代码要求调用方显式传入或刷新回调，不猜测、不伪造，也不自动处理滑块或短信。

## 当前验证

- 匿名 HTTP 请求能拿到登录页和二维码图片接口的真实路由。
- 没有保存本次账号的 `qruuid`、指纹、签名、Cookie 或二维码图像。
- 纯 Python 轮询契约已用假的 HTTP 响应测试；真实扫码是否成功取决于调用方传入的当前 H5guard 值。
