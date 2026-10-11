# Dianping 滑块请求契约（2026-10-11）

这份记录来自 Chrome DevTools 的一次真实游客搜索流程。只保留路由、字段名、字段长度和静态脚本结论，不保存 Cookie、挑战码、图片、`_token`、`mtgsig` 或行为轨迹。

## 验证中心

- `POST /v2/ext_api/page_data`
  - `Content-Type: application/x-www-form-urlencoded`
  - 表单字段：`requestCode`、`feVersion`、`source`、`layer`
  - 返回风险等级、验证方法版本、动作和回调信息。
- `POST /v2/ext_api/spiderindefence/info`
  - `Content-Type: application/x-www-form-urlencoded`
  - 表单字段：`action`、`id`、`request_code`、`appletsfp`、`_token`、`listIndex`、`source`
  - 本次 `_token` 是动态长字段；响应中的滑块图片和参数只在浏览器内存中使用。
- `POST /v2/ext_api/{action}/verify`
  - 滑块脚本先生成 `behavior`（起点、移动轨迹、终点、时间和环境尺寸）。
  - 然后调用 `cypher(token.reload())` 生成 `_token`，并加入 `timestamp`、`listIndex`、`source`。
  - 成功后由 `onVerifySuccess` 处理 `succCallbackUrl`，再回到原始点评页面。

脚本会加载 `puzzleSlider.2d2283aa18.js`，并通过 `postInfo`、`postVerify`、`callHandle` 分离信息上报、验证提交和回调处理。滑块轨迹由页面事件监听器实时收集，不能使用固定轨迹或固定 token 复现。

## H5guard 初始化

`package-1.2.0.js` 的静态字符串和调用链显示：

- 读取 `localStorage.localId`、页面 URL、`sessionId`、`dfpId`、`loId`、`mVer`；
- 通过 `POST /v1/i/osake/junmai`、`POST /v1/i/osake/ginjo` 交换 `data` + `ver=1.0` 的 H5guard 环境数据；
- 通过 `GET /horn/v1/modules/H5guardTrack/prod` 拉取配置，查询字段：`appKey`、`dfpId`、`utm_medium`、`ver`、`host`、`ref`、`i18n`、`pVer`、`sso`；
- 详情页指纹上报字段：`encryptVersion`、`fingerPrintData`、`src`、`index`。

因此客户端只接受当前正常页面生成的 `h5_fingerprint` 与 `mtgsig`，缺少时抛出 `H5GuardRequired`；`from_cookie()` 仍是可用的纯 HTTP 登录态入口。

## 验收边界

- 已在登录态浏览器完成搜索 → 商户详情只读闭环。
- 游客 Python 请求在验证中心前停止并抛出 `AccessRequired`。
- 手动完成一次滑块后，继续记录 verify 请求的脱敏字段和成功回调，再评估可由 Python 重算的部分；当前不自动解题、不伪造风险控制结果。

