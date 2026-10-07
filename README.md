# DianpingApis

大众点评消费者端的 Python HTTP 客户端。仓库只使用 `requests` 和页面公开数据，不启动浏览器、不读取浏览器配置、不保存 Cookie 到磁盘。

## 当前能力

| 能力 | 入口 | 状态 |
| --- | --- | --- |
| Cookie 登录态 | `DianpingAuth.from_cookie()` | 通过 `GET /note/create` 检查跳转、验证墙和状态码 |
| 二维码登录 | `start_qr_login()`、`poll_qr_login()` | 已对齐二维码图片与轮询路由；调用方必须提供正常登录链路产生的 `h5_fingerprint`、`mtgsig`，扫码由用户在官方 App 完成 |
| 店铺搜索 | `DianpingAPI.search()` | HTTP 解析店铺结果；遇到登录、验证或 App 落地页抛出明确异常 |
| 精选笔记采集 | `search_notes()`、`get_item()` | 读取官方 discovery feed 和笔记详情；这是精选流筛选，不是全站关键词接口 |
| 店铺/点评 Item | `get_shop()`、`get_item()` | 依赖页面返回可解析详情；验证墙会抛 `AccessRequired` |
| 探店笔记发布 | `DianpingCreatorAPI.publish_note()` | 当前没有已验证的消费者 Web 写入契约，抛 `PublishingUnavailable` |
| 店铺点评发布 | `DianpingCreatorAPI.publish_review()` | 当前网页没有已验证的写入契约，抛 `PublishingUnavailable` |

## 安装

```bash
python -m pip install -e .
```

依赖只有 `requests` 和 `beautifulsoup4`。

## Cookie 会话

从本人已登录请求中复制完整 `Cookie` 请求头，只在内存中使用：

```python
from dianping_apis import DianpingAPI, DianpingAuth

auth = DianpingAuth.from_cookie(cookie_header)
api = DianpingAPI(auth)
shops = api.search("咖啡", city_id=1)
print(shops)
if shops:
    print(api.get_item(shops[0].url))
```

`from_cookie()` 不跟随登录重定向。状态码为 401/403/429、跳到账号/验证域名，或页面出现验证标记时，统一抛 `AccessRequired`。

## 纯 HTTP 二维码登录

登录页的二维码接口由 Meituan H5guard 保护。仓库不会猜测或伪造指纹、签名，也不会绕过滑块；调用方需要从本人正常登录链路获得当前短时 `h5_fingerprint` 与 `mtgsig`：

```python
auth = DianpingAuth()
challenge = auth.start_qr_login(
    h5_fingerprint=current_fingerprint,
    mtgsig=current_signature,
)
# challenge.image 是 JPEG 字节，challenge.image_data_url 可交给调用方自己的 UI
# 用户使用大众点评 App 扫码后：
result = auth.poll_qr_login(
    challenge,
    h5_fingerprint=current_fingerprint,
    mtgsig=current_signature,
)
auth.require_login()
```

若每次轮询都需要新签名，可传入 `mtgsig(qruuid) -> str` 回调。二维码和轮询响应只保存在内存中；不会自动扫描、代填短信或处理人机验证。

## 采集

```python
notes = api.search_notes("咖啡", category_id=10, page=1)
if notes:
    note = api.get_item(notes[0].url)
    print(note.title, note.content)
```

`search_notes()` 解析页面中的 `window.__dx_dump__`。详情页必须仍然指向同一条目，通用下载页、首页和验证页不会被当作 Item。

## 发布边界

```python
from dianping_apis import DianpingCreatorAPI

creator = DianpingCreatorAPI(auth)
creator.publish_note("周末探店", "记录真实体验")
```

上述调用会在参数校验后抛 `PublishingUnavailable`。当前证据只确认 App 内存在写点评入口，尚未得到可独立复现的消费者 Web HTTP 写入请求，因此客户端不提交猜测请求。

## 测试

```bash
python -m pytest -q
```

测试覆盖 Cookie 解析、登录/验证墙识别、二维码请求契约、店铺搜索、精选流分页、笔记详情及 URL 约束；测试使用假的 HTTP 响应，不启动外部程序、不发布内容。

更多观察记录见 [`docs/qr_login.md`](docs/qr_login.md) 和 [`docs/login_collect_acceptance.md`](docs/login_collect_acceptance.md)。
