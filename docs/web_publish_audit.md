# 消费者 Web 发布入口核查

2026-10-07 在已登录的 Chrome 中检查了大众点评首页、笔记页、店铺页、个人评价页和旧 H5 写点评页。仅浏览页面与网络请求，没有发表内容。

- `https://www.dianping.com/note/create` 的 `__NEXT_DATA__` 显示 `page: "/note"`、`id: "create"`。页面请求 `recfeeds.bin?feedid=create`，仅显示相关推荐，没有标题、正文、图片上传或发布控件。此路由把 `create` 当成笔记 ID。
- 已登录店铺页只有评价列表与打开 App 提示。点击“查看全部”出现“移步至大众点评App”扫码层，没有写点评控件。读评价请求是 `outsideshopreviewlist.bin`，没有观察到写入请求。
- 旧 H5 写点评地址 `https://h5.dianping.com/app/app-home-design-peon/cp/cp1608review/?shopid=563754` 明确提示在 App 内写点评。
- [大众点评帮助中心](https://kf.dianping.com/csCenter/app/questions/17140)说明的写点评路径均在 App 内。

本次没有可确认的消费者笔记或店铺点评发布 POST、请求体或成功响应。因此 `DianpingCreatorAPI` 保留方法签名并抛 `PublishingUnavailable`，等待有证据的 App 实现；不会把读取或推荐接口当作发布接口。

