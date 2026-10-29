# Scarlett ApplyPilot v2

[English](README.md)

新岗位发现 → 真实招聘验证 → 职责能力匹配 → 已有 PDF 分流 → 官方 ATS 填写 → 有条件自动提交 → 确认 → 记录。保留原项目 MIT 许可与 Agent 引导式初始化。

自动提交默认关闭，必须完成私人配置并得到用户明确批准。测试和定时发现任务不会提交真实申请。

## 启动

Python 3.11+：

```sh
git clone https://github.com/scarlett-jiang-ai/applypilot.git
cd applypilot
python -m venv .venv
# 激活虚拟环境后：
python -m pip install -e ".[browser]"
python -m playwright install chromium
python -m applypilot init
python -m applypilot review-policy
python -m applypilot cycle --kind daily
python -m applypilot dashboard
```

私人数据默认在 ~/.applypilot，可用 --state 指定绝对路径。先配置 watchlist、能力、地点、职级、工作授权、已有 PDF 和精确 Answer Bank。空 watchlist 不会搜索任何公司。dashboard 是本地 HTML 和 CSV，不是公开网站。

## 功能

- 六类可扩展能力分类，分析职责，不靠职位名称。
- 原始发布时间、首次发现、重发、招聘信号和验证时间分开记录。P0：0–6 小时；P1：6–24 小时；P2：24–48 小时；P3：2–7 天。未知日期不会伪装成新岗位。
- Greenhouse/Ashby/Lever 公共接口和公司官网关联验证；社交招聘信号与 networking 导入；无法访问的来源明确记录。
- 先审查硬条件，再用 30/25/20/15/10 启发式排序，不代表录用概率。
- SQLite 跨运行去重、原子申请预留、确认后计数。点击提交不等于成功。
- 已有 PDF 校验、精确批准的答案、绑定配置内容的政策和撤销机制。
- Playwright 操作经过审查的单页原生表单，遇到未知字段、登录、人机验证或上传失败暂停。

## 边界

不使用 LinkedIn Easy Apply，不索取登录信息，不改写简历，不自动私信，不绕过 CAPTCHA/2FA/权限提示。法律、身份、当前或未来 sponsorship、薪资不清楚时交给用户。

这不是万能 ATS 适配器。Workday 登录、多页流程、自定义组件和 iframe 需要用户或额外测试的适配器。真实 ATS 尚未上线认证。能力匹配是关键词启发式，需要人工或 Agent 审查语义和资历要求。

定时监控默认未安装，通知目前是本地事件。见 [monitoring](references/monitoring.md)。社交平台需要授权的公共搜索/浏览器或导入，不声称已自动覆盖。

[初始化与批准](references/setup-workflow.md) · [官方投递流程](references/application-playbook.md) · [安全边界](references/safety-and-boundaries.md)

测试：`python -m unittest discover -s tests -v`。设置 APPLYPILOT_BROWSER_TESTS=1 可运行完全虚构且拦截网络的浏览器测试。
