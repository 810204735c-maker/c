# 招考雷达

一个零服务器成本的公开招考信息聚合站。它每天自动检查公务员、事业单位和央国企招聘来源，把可核验链接整理成可搜索、筛选和收藏的清单。

## 已实现

- 公务员、事业单位、央国企三类信息聚合
- 单位、岗位、专业、地区全文搜索
- 地区、招聘对象、发布时间和截止时间筛选/排序
- 浏览器本地收藏，不上传个人数据
- 中文硕士本地求职画像，以及“专业相关、文字岗位、需要核对”可解释匹配
- 从官方详情页提取专业、文字职责、应届、学历、党员、证书和经历原文线索
- 编辑部、情报台、清爽三种阅读模式
- 官方域名白名单、标题去重、来源故障保留旧数据
- 公开健康快照、来源连续失败记录和异常质量门禁
- 每天北京时间 07:20 自动更新并重新部署

## 中文硕士个性化匹配

点击页头“我的画像”可以设置专业、研究方向、毕业年份、政治面貌、偏好地区、关注方向和已有证书。画像只保存在当前浏览器的 `localStorage['job-radar:profile']` 中，不会写入公开 JSON、Git 仓库或第三方服务；清除该网站的浏览器数据会同时删除画像。

采集器从允许访问的官方详情页提取原文线索，前端再区分：

- `专业相关`：官方详情页明确提到中国语言文学或其研究方向。
- `文字岗位`：官方详情页提到综合文字、宣传文化、编辑出版、新媒体、高校行政或中文教育职责。
- `需要核对`：详情页尚未提取到足够线索，或出现党员、工作经历、教师资格、毕业届别等需要人工确认的条件。

这些标签用于缩小阅读范围，不是报考资格审核，也不能替代职位表。一个公告可能包含多个岗位，最终必须核对具体岗位的专业代码、学历、政治面貌、届别和经历要求。

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
node --test tests/core.test.mjs tests/matching.test.mjs
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
- `profileHints`：`majorTags`、`roleTags`、`qualificationTags`、`graduateYears` 和对应 `evidence`

日期无法从列表页可靠识别时，`dateEstimated` 会设为 `true`，前端显示“日期待核”，不会伪装成精确发布日期。

`profileHints` 只保存官方详情页确实出现的固定词典标签和最长 120 字证据句。字段缺失表示尚未提取到可靠线索，不表示岗位不适合中文专业。

`data/health.json` 公开记录数据生成时间、当前公告数、最近 7 日新增数、截止日期覆盖率、来源成功率、连续失败次数和快照数量变化。它不包含令牌、Cookie 或完整失败响应正文。

采集完成后会运行质量门禁：公告总数为 0、相对上一版骤降超过 40%、启用来源成功率低于 60% 或数据超过 36 小时时停止部署，保留上一份稳定快照。部署完成后，工作流还会检查公网首页、`data/jobs.json` 和 `data/health.json` 均返回可解析内容。

## 边界与排查

- 政府网站偶尔会限流、调整地址或临时不可访问。采集器会继续处理其他来源，并保留失败来源的上次数据。
- 当前国家公务员局年度专题会要求执行反爬 Cookie 脚本，因此配置中保持禁用并公开记录原因；项目不会绕过该限制，待官方提供可直接读取入口后恢复。
- 搜索 RSS 只用于发现链接；最终链接仍须命中官方域名白名单。
- 静态站无法代替报名系统，也无法保证岗位在你查看时仍开放。报名资格、岗位表、截止时间、考试安排和录用结果均以原公告为准。
- 若 Actions 采集成功但页面未更新，检查 Pages 的 Source 是否选择了 `GitHub Actions`，并重新运行工作流。
