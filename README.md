# DianpingApis

大众点评消费者端的实验性 Python 浏览器封装：登录入口、网页搜索、Item 页面读取、探店笔记和店铺点评的填表与提交流程。

本项目沿用 `Spider_XHS`、`DouYin_Spider` 的「会话 + 读取 API + 发布 API」结构。大众点评消费者发布接口没有可核验的开放 HTTP 文档，因此发布模块操作账号本人登录的 Chrome 页面，不猜测私有请求地址。

## 能力与验证状态

| 能力 | 入口 | 当前状态 |
| --- | --- | --- |
| 登录 | `DianpingAuth.login()` 打开官网登录页，由用户在浏览器扫码或输入；`from_cookie()` 导入自有 Cookie | 方法等待离开登录/验证域名，尚未核对登录后账号状态；需本人确认 |
| 搜索 | `DianpingAPI.search()` 解析网站搜索页链接 | 现用 `/search/keyword/...` 店铺搜索路由；当前匿名请求进入验证中心。`kind="note"` 仅过滤页面里的笔记链接，笔记搜索覆盖尚未验证 |
| Item | `get_shop()`、`get_item()` 读取店铺、笔记、点评页 | 公开店铺页样本可解析；笔记和点评页尚缺可靠实测，部分页面跳登录或 App |
| 探店笔记 | `DianpingCreatorAPI.publish_note()` | `/note/create` 匿名访问跳官方登录页；登录后表单选择器待账号实测，默认只填表 |
| 店铺点评 | `DianpingCreatorAPI.publish_review()` | 官方帮助确认 App 内入口；网页“写点评”表单待账号实测，默认只填表 |

读取方法会识别已知的登录/验证页并抛 `AccessRequired`。其他页面变体仍可能需要补充识别规则。发布方法找不到当前账号的表单控件时抛 `ElementMissing`；显式传入 `submit=True` 后，只有看到可见的成功文案才返回确认结果，否则抛 `SubmissionUnconfirmed`。默认 `submit=False` 只填当前页面，**不会点击保存或提交**。

## 安装

```bash
python -m pip install -e .
```

使用可见 Chrome。首次登录时在浏览器窗口内完成官方扫码、短信或其他验证。Cookie 保存在传入的 `user_data_dir`，请把它放在仓库外。

```python
from dianping_apis import DianpingAPI, DianpingAuth, DianpingCreatorAPI

with DianpingAuth("../dianping-browser-data") as auth:
    auth.login()
    api = DianpingAPI(auth)
    print(api.get_shop("563754"))

    creator = DianpingCreatorAPI(auth)
    # 登录后的编辑器选择器仍待账号实测；可能抛 ElementMissing。
    # creator.publish_note("周末探店", "记录自己的真实体验")
```

店铺点评使用自己的消费体验和真实店铺 URL。网页“写点评”入口待账号实测：

```python
creator.publish_review(
    "https://www.dianping.com/shop/563754",
    "记录自己的真实体验",
    rating=4,
    images=["/path/to/my-photo.jpg"],
    submit=False,  # 只填表，不保证平台保存草稿
)
```

`from_cookie(cookie_header)` 可导入自己已有的 Cookie；不会把 Cookie 写进源代码或日志。导入后也需确认账号实际登录。`get_item()` 仅接受大众点评 HTTPS 店铺、笔记、点评链接。

## 现有证据与限制

- [大众点评帮助中心](https://kf.dianping.com/csCenter/app/questions/17373)列出 App 中写点评的三个官方入口。
- 网站的[移动首页](https://m.dianping.com/?cityId=1)显示搜索框；[店铺页](https://m.dianping.com/shop/563754)可显示部分详情，也可能提示使用 App。
- `https://www.dianping.com/note/create` 目前匿名访问会跳到 `account.dianping.com/pclogin`。这证明登录门槛和网页入口，不证明发布表单的字段和成功响应。
- `https://www.dianping.com/search/keyword/1/0_咖啡` 匿名访问进入验证中心。浏览器搜索和发布需要账号现场复测，尤其是网页店铺点评入口。代码在这些条件不满足时给出明确错误。

## 测试

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

测试验证 URL 约束、搜索结果解析、验证墙检测、详情解析、隐藏控件选择与提交确认边界。真实登录和发布尚待账号本人现场验证；测试套件不会发布内容。
