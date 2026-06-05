# twtapi 信源接入坑

> 记录于 2026-06-05。用于避免后续把额度/端点问题误判成账号解析失败。

## 端点有新旧两套

- 新公开站点是 `https://twtapi.io/`，API base 为 `https://api.twtapi.io`，常用端点包括 `/user` 与 `/user_tweets`，鉴权头是 `X-API-Key`。
- 旧桥仍可能接受已发放的老 key，base 为 `https://api.twtapi.com/api/v1/twitter`，Augur 旧实现用过：
  - `UserResultByScreenName?username=<handle>`：用户名 → `rest_id`
  - `UserTweets?user_id=<rest_id>`：用户时间线
- 兼容策略：先试新版 `/user`，失败后试旧版 `UserResultByScreenName`；解析到 user id 后把该账号缓存为对应 mode，后续拉 tweets 走同一套端点。

## 错误形态

- 新版鉴权失败通常是 HTTP `401/403`，应直接提示 `TWTAPI_KEY 无效或无权限`。
- 真实 HTTP `429` 是频率或额度限制。
- 旧版额度用完可能是 **HTTP 200**，但 JSON 里是 `code=429`、`sub_code=42903`、`msg="Monthly call limit reached, please upgrade your plan"`。这必须提示“月度额度已用完”，不能继续往下解析 `rest_id` 后报“解析账号失败”。
- 只有两套端点都可达、且都没有返回 user id 时，才把问题归到账号不存在或接口未返回 user_id。

## 当前本机状态

- 当前配置的 `TWTAPI_KEY` 能被旧版端点识别，但旧版返回月度额度用完；新版 `api.twtapi.io` 对这把 key 返回未授权。
- 结论：X 适配器代码已接通，设置页测试应显示额度/鉴权错误；要真正继续拉官方号推文，需要等额度重置、升级套餐，或换成新版可用 key。
