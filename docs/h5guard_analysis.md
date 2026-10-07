# H5guard / mtgsig 纯 HTTP 边界（2026-10-07）

## 已观察字段

在已登录页同一页面上下文调用官方公开 `H5guard.sign()`，请求 `https://accountapi.dianping.com/mlogin/dp/api/v1/qrlogin/getQrCodeImg` 得到 `mtgsig` 字段：`a1,a2,a3,a5,a6,a8,a9,a10,x0,d1`。本次浏览器版本中 `a1=3` 字符、`a3=56`、`a5=128`、`a6=476`、`a8=32`、`a9=11`、`a10=2`、`d1=32`；`a2/x0` 为数字。`getfp()` 返回约 3.6 KiB 的 `H5dfp_4.3.0_tttt_...` 指纹。

相同页面短时间重复签名时 `a1/a3/a6/a9/a10/x0` 稳定，`a2/a5/a8/d1` 变化；这说明 `a6` 是页面上下文的环境快照，不能按请求时间或固定常量猜测。

## 公开算法与当前缺口

公开逆向资料可以确认部分校验结构：自定义 Base64、RC4、AES-CBC/gzip、MD5/MurmurHash，以及 `c0/c1/c2/iv` 常量。但当前脚本为 4.3.0 版本，`a6` 生成依赖页面初始化后的完整环境状态（上游实现中为 66 项随机/环境种子和 VMP 计算）；`a5/a8/d1` 还依赖该状态、请求计数和当前时间。仅从已下载脚本静态提取常量，不能得到一个与当前 `H5guard.sign()` 相同的 `a6`。

用当前 Chrome 真实样本套用公开 4.2/1.2 解码公式，RC4 输出未形成 gzip/JSON；这证明版本/环境输入仍不齐，不能将旧公式伪装成可用 signer。仓库不加入猜测 signer，也不保存账号指纹、签名、Cookie 或二维码。

## 可验证结论

- `DianpingAuth.start_qr_login()` / `poll_qr_login()` 已是纯 `requests`，并显式接收调用方提供的短时 `h5_fingerprint`、`mtgsig`。
- 纯 Python 可以在拿到一次正常页面生成的完整动态值后重放同一会话的请求契约；纯 Python 从零生成 4.3.0 动态指纹/签名仍缺少完整浏览器环境种子和 VMP 输入。
- 要继续做纯算法 signer，最小新增证据是一组**脱敏**的浏览器 `H5guard.sign()` fixtures（字段值可哈希/占位，但必须保留长度、请求 URL、a2/a9、a6 解密前缀和对应解密明文），以及同一页面上下文的初始化种子/请求计数。没有这些输入时不要发布“可用”的签名实现。

## 验证

```text
python -m pytest -q  # 23 passed
```
