# 外企校招来源覆盖与合规记录

更新日期：2026-08-23

本频道只发布已登记外企在中国大陆开展、明确包含 2027 届、正式全职的公司级校园招聘活动。官网优先；第三方只用于发现或官网不可用时的回退。来源页面要求登录、验证码、个人 Cookie，或条款不允许自动访问时，保持禁用或仅人工核验，不尝试绕过。

## 当前来源

`checkedAt` 均为 2026-08-23。`最近状态` 同时记录公开页面复核与 2026-08-23 首轮正式采集结果；持续机器状态以 `data/foreign-health.json` 为准。

| source ID | tier | URL | robots URL | terms URL | enabled | 最近状态 | 限制与处理 |
|---|---|---|---|---|---|---|---|
| `deloitte-china-graduate` | `official_verified` | [德勤中国 Graduate Program](https://www.deloitte.com/cn/en/careers/explore-your-fit/students/graduate-program.html) | [robots.txt](https://www.deloitte.com/robots.txt) | [使用条款](https://www.deloitte.com/cn/zh/legal/legal.html?icid=bn_legal) | 是 | 页面明确显示 2027 Graduate Recruitment 已开放；首轮 `ok`，发布 1 场 | 只保存公司级活动标题、公开筛选字段和原链接；不复制页面长文、商标或岗位详情。申请跳转至企业招聘系统后由用户自行选择岗位。 |
| `pwc-china-students` | `official_verified` | [普华永道中国学生招聘](https://www.pwccn.com/en/careers/students.html) | [robots.txt](https://www.pwccn.com/robots.txt) | [Legal Disclaimer](https://www.pwccn.com/en/legal.html?icid=footer) | 是 | General graduates 明确接收 2027 届；首轮 `ok`，发布 1 场 | 同页含实习、港澳台和其他项目；采集只生成中国大陆正式 Graduate 公司级活动，不把整页其他项目混入卡片。 |
| `deutsche-bank-apac-graduates` | `official_verified` | [德意志银行申请时间](https://careers.db.com/students-graduates/your-application/) | [robots.txt](https://careers.db.com/robots.txt) | [Legal Resources](https://www.db.com/legal-resources/index?language_id=1&kid=legal-resources.redirect-en.shortcut) | 是 | China 2027 Graduate Programme 申请期为 2026-09-07 至 2026-10-18；首轮 `ok`，发布 1 场 | 同页含全球项目与实习；以最接近 `China + 2027` 的证据窗口提取正式 Graduate 活动，港澳台和海外活动不发布。 |
| `roche-china-startup-2027` | `official_verified` | [StartUp 罗氏制药中国人才发展项目](https://careers.roche.com/cn/zh/startup-china-pharma) | [robots.txt](https://careers.roche.com/robots.txt) | [招聘隐私声明](https://careers.roche.com/global/en/privacy-policy) | 是 | 页面明确写明 2027 届、中国大陆学校、正式 offer 与三方协议；连续两次 dry-run 均为 `ok`，发布 1 场 | 同页也说明港澳台及海外院校毕业时间，但岗位地点在中国大陆；卡片只记录 2027 届大陆正式项目和大陆城市，不扩展为海外岗位。 |
| `shell-graduate-programme-2027-china` | `official_verified` | [Shell Graduate Programme 2027 - China](https://shell.wd3.myworkdayjobs.com/ShellCareers/job/Shell-Graduate-Programme-2027---China_R205121) | [robots.txt](https://shell.wd3.myworkdayjobs.com/robots.txt) | [Shell Terms of Use](https://www.shell.com/terms-of-use.html) | 是 | 公开页面元数据明确显示 China、2027、Worker Type: Regular、北京与上海；连续两次 dry-run 均为 `ok`，发布 1 场 | Workday 是共享域；只允许 Shell 租户的精确 HTTPS 路径，并只读取公开的 Open Graph 摘要元数据，不登录、不调用隐藏接口、不放行整个 `myworkdayjobs.com`。 |
| `official-company-search` | `official_job_feed` | 按企业注册表的 `officialDomains` 生成公开搜索查询 | 按每个目标官网根域检查 | 按每个目标官网条款检查 | 是 | 已登记 51 家可发布企业；正式采集为 `empty`，0 场新增 | 搜索只作官网链接发现。候选链接必须命中企业白名单，且标题或摘要自身出现 2027、正式校招和中国大陆证据；未知企业只进入人工复核，不公开。 |
| `nowcoder-campus-schedule` | `third_party_only` | [牛客校招日程](https://www.nowcoder.com/jobs/school/schedule) | [robots.txt](https://www.nowcoder.com/robots.txt) | [免责声明](https://www.nowcoder.com/html/disclaimer) | 否 | 校招日程公开可读且含 27 届、外企分类，但现行授权边界不足 | robots 与条款需要再次联合复核并获得足够授权后才可启用；不访问受限搜索路径，不登录，不调用隐藏接口。 |
| `yingjiesheng-public-discovery` | `third_party_only` | 公开搜索：`site:yingjiesheng.com 2027 校园招聘 外企 全职` | [robots.txt](https://www.yingjiesheng.com/robots.txt) | [用户协议 PDF](https://www.yingjiesheng.com/about/service/user-agreement202108.pdf) | 是 | 仅启用搜索 RSS 发现；首轮 `empty`，0 场合规回退 | 只把公开转载作为线索；企业必须已登记，且官网无法使用时才可作为回退卡片，并显示“第三方信息，请核验”。 |
| `shixiseng-manual` | `manual_only` | [实习僧校招入口](https://www.shixiseng.com/interns?city=%E5%85%A8%E5%9B%BD&type=school) | [robots.txt](https://www.shixiseng.com/robots.txt) | [用户协议](https://www.shixiseng.com/rule) | 否 | 保持人工核验 | 用户协议明确禁止机器人、脚本自动访问，以及未经许可的爬虫、抓取和批量检索；不会自动访问、登录或收集。 |

## 首轮正式快照

2026-08-23 01:09（北京时间）完成正式采集：发布 5 场公司级活动，均来自企业官网；7 个启用来源全部为 `ok` 或 `empty`，来源成功率 100%，官网来源比例 100%，待人工复核 0。德意志银行活动已提取 2026-10-18 截止日，其余 4 场因官网未给出明确截止日而保留“日期待核”。首份摘要以 3 场建立基线；罗氏与 Shell 在基线建立后接入，因此如实记为今日随后新增 2 场。

## 企业注册表

`crawler/foreign_companies.json` 当前登记 51 家企业。每项包含中英文名称、别名、所有权类别、国家或地区、行业、所有权证据 URL、核验日期、官网域名和可委托招聘链接前缀。只有 `publishable=true` 且来源能解析到登记企业的候选活动才可进入公开快照。

企业口径包括外资独资、外资控股、外资品牌独立招聘的合资企业和港澳台企业；不把中国企业发布的海外岗位视为外企校招。注册只证明企业属于本频道范围，不代表当前一定有符合条件的 2027 届活动。

## 分阶段扩展

1. 当前交付：51 家已核验注册企业；5 个直接官网活动页、按企业注册表进行的官网发现、应届生公开搜索发现；牛客保持禁用待条款复核；实习僧为 `manual_only`。
2. 后续覆盖：扩至 150–250 家已核验企业，优先增加 employer-linked ATS，以及 Lever Public Postings API、SmartRecruiters Public Posting API、Ashby public job board feed 等明确公开接口。
3. 长尾维护：高校就业网和允许使用的平台只作发现队列；每周核验新企业所有权与官网，并公开 `registeredCompanyCount`、健康来源数、`officialSourceRatio` 和 `pendingReviewCount`。

## 发布与保留规则

- 同一公司、届别、招聘类型、批次和申请窗口只发布一张公司级卡片；多来源命中时官网为主，其他链接记为备选来源。
- 今日新增按 `firstSeenAt` 计算，不按企业页面的发布日期；首次快照使用 `bootstrap=true`、`addedCount=0`。
- 已过期活动默认隐藏，保留 60 天供收藏复查；截止日期未知且连续 45 天未更新时标记为 `stale`。
- 任何实习、兼职、社会招聘、海外/港澳台工作地点、非 2027 届或未知企业候选均不得进入公开 `campaigns`。
- 页面只展示必要的事实字段、短证据和原始链接，不镜像招聘正文，不代替企业报名系统。
