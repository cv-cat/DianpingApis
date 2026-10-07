# DianpingApis

大众点评消费者端的实验性 Python 浏览器封装：登录入口、网页搜索与 Item 页面读取。保留探店笔记和店铺点评的方法签名，但当前 Web 页面没有已验证的发布入口，调用时会明确报错。

本项目沿用 `Spider_XHS`、`DouYin_Spider` 的「会话 + 读取 API + 发布 API」结构。大众点评消费者发布接口没有可核验的开放 HTTP 文档；已登录 Web 页也没有找到可用编辑器，因此暂不发起写入请求。

## 能力与验证状态

| 能力 | 入口 | 当前状态 |
| --- | --- | --- |
| 登录 | `DianpingAuth.login()` 打开官网登录页，由用户在浏览器扫码或输入；`from_cookie()` 导入自有 Cookie | 本人 Chrome 的[扫码请求链](docs/qr_login.md)已核对；用临时浏览器配置导入当前登录态，`require_login()` 实测通过，匿名配置被阻断。独立窗口里直接扫码的流程尚未复测 |
| 搜索 | `DianpingAPI.search()` 解析网站搜索页链接 | 登录态导入临时浏览器后，仓库方法实测返回 15 个店铺结果；匿名请求进入验证中心。`kind="note"` 仅过滤页面里的笔记链接，笔记搜索覆盖尚未验证 |
| Item | `get_shop()`、`get_item()` 读取店铺、笔记、点评页 | 上述搜索首个店铺由仓库 `get_item()` 实测读到匹配 ID、非空标题及描述；笔记和点评页尚缺可靠实测，部分页面跳登录或 App |
| 探店笔记 | `DianpingCreatorAPI.publish_note()` | `/note/create` 实为笔记详情路由，不是编辑器；方法抛 `PublishingUnavailable`。App 发布流程待对接 |
| 店铺点评 | `DianpingCreatorAPI.publish_review()` | 登录网页店铺页提示打开 App，没有写点评控件；方法抛 `PublishingUnavailable` |

读取方法会识别已知的登录/验证页并抛 `AccessRequired`。其他页面变体仍可能需要补充识别规则。发布方法在入口核实之前只校验参数并抛 `PublishingUnavailable`，不会导航或提交。

## 安装

```bash
python -m pip install -e .
```

使用可见 Chrome。首次登录时在浏览器窗口内完成官方扫码、短信或其他验证。传入 `user_data_dir` 时，Cookie 保存在该浏览器配置中，请把它放在仓库外。传入 `None` 时使用临时内存配置，关闭后丢弃登录态。

```python
from dianping_apis import DianpingAPI, DianpingAuth, DianpingCreatorAPI

with DianpingAuth("../dianping-browser-data") as auth:
    auth.login()
    api = DianpingAPI(auth)
    print(api.get_shop("563754"))

    creator = DianpingCreatorAPI(auth)
    # 当前网页没有笔记编辑器，以下调用会抛 PublishingUnavailable。
    # creator.publish_note("周末探店", "记录自己的真实体验")
```

店铺点评使用自己的消费体验和真实店铺 URL。当前网页店铺页没有“写点评”入口，以下调用会抛 `PublishingUnavailable`：

```python
creator.publish_review(
    "https://www.dianping.com/shop/563754",
    "记录自己的真实体验",
    rating=4,
    images=["/path/to/my-photo.jpg"],
    submit=False,
)
```

`from_cookie(cookie_header)` 可导入自己已有的 Cookie；不会把 Cookie 写进源代码或日志。导入后也需确认账号实际登录。`get_item()` 仅接受大众点评 HTTPS 店铺、笔记、点评链接；目标跳转到其他页面或其他 Item 时会报错，`/note/create` 不视为笔记 Item。

只需运行一次采集、不希望留下浏览器配置时，可以在临时内存配置中导入本人当前会话的 Cookie：

```python
with DianpingAuth(None, headless=True) as auth:
    auth.from_cookie(cookie_header)
    api = DianpingAPI(auth)
    results = api.search("咖啡", city_id=1)
    if results:
        print(api.get_item(results[0].url))
```

[登录到采集的实测记录](docs/login_collect_acceptance.md)只记录状态和字段是否存在，不含账号、Cookie 或页面正文。

## 现有证据与限制

- [大众点评帮助中心](https://kf.dianping.com/csCenter/app/questions/17373)列出 App 中写点评的三个官方入口。
- 网站的[移动首页](https://m.dianping.com/?cityId=1)显示搜索框；[店铺页](https://m.dianping.com/shop/563754)可显示部分详情，也可能提示使用 App。
- `https://www.dianping.com/note/create` 匿名访问会跳到 `account.dianping.com/pclogin`；扫码登录后仅显示“去查看/相关推荐”。页面数据把 `create` 当作笔记 ID，详见[网页发布入口核查](docs/web_publish_audit.md)。
- `https://www.dianping.com/search/keyword/1/0_咖啡` 匿名访问进入验证中心；在扫码登录的 Chrome 中返回店铺结果，源码按店名链接解析。
- 登录后的网页店铺页展示详情和评论，并提示打开 App；当前没有网页写点评控件。[官方帮助中心](https://kf.dianping.com/csCenter/app/questions/17373)将写点评入口列在 App 内。

## 测试

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

测试验证 URL 约束、搜索结果解析、验证墙检测、详情解析、临时配置不落盘，以及未验证发布入口时不触发写入。独立持久浏览器配置的扫码登录仍待端到端验证；测试套件不会发布内容。
