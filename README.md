# 招考雷达

一个零服务器成本的公开招考信息聚合站。它每天自动检查公务员、事业单位和央国企招聘来源，把可核验链接整理成可搜索、筛选和收藏的清单。

## 已实现

- 公务员、事业单位、央国企三类信息聚合
- 单位、岗位、专业、地区全文搜索
- 地区、招聘对象、发布时间和截止时间筛选/排序
- 浏览器本地收藏，不上传个人数据
- 编辑部、情报台、清爽三种阅读模式
- 官方域名白名单、标题去重、来源故障保留旧数据
- 每天北京时间 07:20 自动更新并重新部署

## 本地查看

不要直接双击 `index.html`，浏览器会阻止它读取本地 JSON。请在项目目录启动一个静态服务器：

```powershell
python -m http.server 4173
```

然后打开 `http://localhost:4173`。

如果系统没有全局 Python，也可以使用任意静态服务器。网站运行本身不需要安装 npm 包。

## 运行测试

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node --test tests/core.test.mjs
```

采集器联网试运行但不覆盖当前数据：

```powershell
python crawler/crawl.py --config crawler/sources.json --output data/jobs.json --dry-run
```

正式更新：

```powershell
python crawler/crawl.py --config crawler/sources.json --output data/jobs.json
```

## 免费上线到 GitHub Pages

1. 在 GitHub 新建一个仓库，把本目录提交并推送到 `main` 或 `master` 分支。
2. 打开仓库的 `Settings → Pages`。
3. 在 `Build and deployment → Source` 选择 `GitHub Actions`。
4. 打开 `Settings → Actions → General`，确认工作流允许申请写入权限；组织策略若限制写入，需要管理员放行 `contents: write`。
5. 打开 `Actions`，手动运行一次“更新招考信息并部署网站”。成功后，Pages 页面会显示网站地址。

工作流同时负责采集和部署。定时表达式为 `20 23 * * *`（UTC），对应北京时间次日 07:20。也可以随时在 Actions 页面手动运行。

## 添加或调整来源

来源配置位于 `crawler/sources.json`。支持三种类型：

- `html`：扫描官方栏目页中的招聘链接。
- `rss`：读取一个标准 RSS/Atom 地址。
- `rss_search`：用公开搜索 RSS 发现新链接，再经过 `allowedDomains` 白名单过滤。

示例：

```json
{
  "name": "某省人事考试网",
  "kind": "html",
  "url": "https://example.gov.cn/recruitment/",
  "category": "公务员",
  "allowedDomains": ["example.gov.cn"],
  "maxItems": 50,
  "timeout": 20
}
```

`allowedDomains` 是安全边界。不要为了增加数量而填写过宽的商业网站域名；培训广告和不可核验转载会降低信息质量。

## 数据格式

网站读取 `data/jobs.json`。每条公告包含：

- `title`、`url`、`source`、`official`
- `publishedAt`、`dateEstimated`、`deadline`
- `category`、`location`、`audience`
- `summary`、`collector`、`collectedAt`

日期无法从列表页可靠识别时，`dateEstimated` 会设为 `true`，前端显示“日期待核”，不会伪装成精确发布日期。

## 边界与排查

- 政府网站偶尔会限流、调整地址或临时不可访问。采集器会继续处理其他来源，并保留失败来源的上次数据。
- 搜索 RSS 只用于发现链接；最终链接仍须命中官方域名白名单。
- 静态站无法代替报名系统，也无法保证岗位在你查看时仍开放。报名资格、岗位表、截止时间、考试安排和录用结果均以原公告为准。
- 若 Actions 采集成功但页面未更新，检查 Pages 的 Source 是否选择了 `GitHub Actions`，并重新运行工作流。
