"""Rewrite the Chinese delivery notes for the final revision round."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'manuscript' / '第三轮修改交付说明.md'

TEXT = """# 第三轮修改交付说明（投稿定位：风险管理类期刊）

本目录是独立的新一轮成果，`manuscript/`、`revision_20260922/`、`revision_20260922_round2/` 三套旧成果全部原样保留，未被改写。

## 一、本轮改了什么

### 1. 叙事重构：从"数据版本评估"改为"模型验证中的输入版本风险"

- 新标题：**Financial data version risk in bankruptcy model validation: separating scoring, development and evaluation effects**
- 摘要按"问题 → 框架 → 应用 → 主结果 → 实践含义"重写，两个最抓人的数字直接进摘要：直接替换效应 −2.78/+1.37/+0.11，开发域把版本对比从 +2.85 变成 −16.01。
- 关键词换成检索入口词：Model validation; Model risk; Credit risk; Bankruptcy prediction; Data versioning; Backtesting。
- 引言明确三条新增贡献：交叉版本协议（在观测、标签、权重、初始缺失固定下定位差异来源）、两套信息时钟（拟合时点可用 vs 评分时点可得）、经验结论（直接替换的符号可与对角差异相反）。
- 全文语言换成风险管理口径：validation report、governance、data provenance、model development and maintenance、audit trail。
- 新增 **5.1 Implications for model validation practice**，给出 7 条可落地验证清单（冻结输入来源、分开重开发与重评分、分开两套时钟、不要用"有后期版本"筛样本、保留输入未变的观测、报告固定参数基准、把数值差异追到原始记录）。
- 新增 **5.2 Data versioning as a governance risk**，接入模型治理与监管披露要求（SR 11-7、巴塞尔 RCAP 手册、ECB 内部模型指引）。

### 2. 主线收敛：主文只留 6 表 5 图

| 主文显示 | 内容 |
| --- | --- |
| Table 1 | 样本形成过程 |
| Table 2 | 四格矩阵与 I/F/J 分解（主结果） |
| Table 3 | 规模域：开发域 vs 评价域分离（第二主结果） |
| Table 4 | 后期版本暴露与结果不均衡 |
| Table 5 | 拟合时点信息边界 |
| Table 6 | 来源支持调整与争议情形 |
| Figure 1 | 两套信息时钟与交叉设计 |
| Figure 2 | 四格表现与差异分解 |
| Figure 3 | 开发影响 vs 匹配普通删除 |
| Figure 4 | 开发域/评价域分离 |
| Figure 5 | 来源证据等级与模型后果 |

附加学习器、五种子、全部候选配置、匹配删除明细、可用期界明细、条件重采样区间等全部下沉到补充材料（保留 25 张 S 表）。

### 3. 逐条落实你给的 8 条硬标准

| 要求 | 落实方式 |
| --- | --- |
| 0 顶刊矢量绘图、≥900 dpi、无文字重叠/交叉 | 五张图全部重画，统一字体与紧凑字号；每张输出矢量 PDF + 矢量 SVG + 900 dpi PNG；脚本内置版式审计，逐字量测文本框边界，任何文字互撞、压轴框、超版心都会直接报错中止，五张图均为 0 碰撞 |
| 1 防御性写作不得散布全文 | 全部"不能证明/并不意味着/不应被解读为"式句子集中到最后一个边界小节；正文改为直接陈述证据强度 |
| 2 禁破折号 | 全文 0 个 em dash、0 个 en dash（连字符仅剩 SEC 表单名 10-K/10-KT） |
| 3 无写作过程语言 | 删除"本文结构如下""评审材料""作者签核台账""提交前必须确认"等；脚本带黑名单门控（journal/reviewer/submission/revision/pending 等） |
| 4 正文不出现刊名 | 正文无任何期刊名（参考文献表按规范保留刊名，属引用信息，非正文） |
| 5 引用顺序 1,2,3… | 43 条引用按首次出现重新编号，脚本自动重排并校验"首次出现顺序严格递增" |
| 6 图表须按序在正文提到 | 脚本校验表 1-6、图 1-5 的首次提及顺序与标题先后关系，全部通过 |
| 7 AI 声明 | 使用你给的那一句，逐字使用；全文再无任何 pending 措辞 |
| 8 不介绍文章结构 | 已删除结构性预告段 |

### 4. 合规与状态

- **数据与代码可用性**：正文已写入公开仓库地址（见第六节），Word、LaTeX 与投稿 PDF 三处一致。
- **人工审核**：按你确认的结果，全文删除"待人工会计确认"类表述。
- 正文（含摘要、结论，不含参考文献）**7,446 词**，加参考文献约 8,900 词。

## 二、主要交付文件

路径：`revision_20260923_jrmv/`

- `delivery/Financial_Data_Version_Risk_Manuscript.pdf` — 阅读版 PDF，16 页，A4，正文可检索可复制，5 张图按 900 dpi 原始分辨率嵌入
- `delivery/Financial_Data_Version_Risk_Manuscript.docx` — 可编辑 Word 版，含 25 个原生 Word 公式，6 表 5 图
- `delivery/Financial_Data_Version_Risk_Supplement.pdf` / `.docx` — 补充材料，25 张 S 表
- `delivery/Risk_Journals_submission_pack.zip` — 投稿整包（PDF 四件套 + 可编辑图表文件 + LaTeX 源）
- `manuscript/manuscript.md` — 主文 Markdown（图表已注入）
- `manuscript/main_template.md` — 带表占位的模板，便于下一次重建
- `manuscript/figures/` — 五张图的 PDF / SVG / PNG 三格式
- `results/` — 构建与校验报告（`manuscript_build.json`、`pdf_qa.json`、`submission_final_check.json` 等）
- `scripts/` — 全部可复跑脚本

## 三、按投稿平台要求做的上传包

平台只收 PDF，且要求图、表"主 PDF 里要有 + 另交可编辑文件"，因此另做了一整套投稿包，位于 `revision_20260923_jrmv/submission/`。

| 上传文件 | 用途 | 规格 |
| --- | --- | --- |
| `submission/pdf/main_manuscript_anonymised.pdf` | 匿名正文：题名、作者块、摘要、关键词、Key messages、图表 legend、6 表 5 图、声明、参考文献 | 13 页，A4 双栏 |
| `submission/pdf/title_page.pdf` | 单独标题页：作者姓名（中英）、两个单位、通信地址、邮箱、ORCID、通信作者、短标题、词数、图表数 | 1 页 |
| `submission/pdf/supplementary_material.pdf` | 补充材料（25 张 S 表） | 17 页 |
| `submission/pdf/cover_letter.pdf` | 投稿信，单作者口径 | 1 页 |
| `submission/figures/figure1..5.svg` + `.pdf` | 按图表号命名的可编辑矢量图 | SVG + 矢量 PDF |
| `submission/tables/table1..6.csv` + `.docx` | 按表格号命名的可编辑表格 | CSV + DOCX |
| `submission/latex/financial_data_version_risk.tex` | 录稿用 LaTeX 源（作者—年引用、APA 文献表、booktabs 表、缩放图表） | 两次 pdflatex 通过 |

作者信息已按 `0 张俊杰 独立作者.docx` 填入，并全文改为单作者口径：

- 姓名 Junjie Zhang（张俊杰），ORCID 0009-0004-8821-4018，通信邮箱 junjiezhang2024@shisu.edu.cn
- 单位 1：Shanghai Academy of Global Governance and Area Studies, Shanghai International Studies University, Shanghai 201620, China
- 单位 2：School of Economics and Finance, Shanghai International Studies University, Shanghai 201620, China
- 通信地址：Shanghai International Studies University, 1550 Wenxiang Road, Songjiang District, Shanghai 201620, China
- 声明改为单人表述：无基金支持、无利益冲突、作者独自负责论文内容与写作
- 投稿信署名 Junjie Zhang 并附单位与邮箱

逐条对照平台要求（脚本自动核验，结果见 `submission/requirement_checklist.json`）：

| 平台要求 | 落实情况 |
| --- | --- |
| 只收 PDF | 四个交付件均为 PDF |
| 正文 PDF 不得含作者姓名与单位 | 正文以匿名稿为底，作者信息集中在标题页；校验无其他身份信息泄漏 |
| 标题页单独提交 | `title_page.pdf` / `.docx`，字段齐全 |
| 短标题不超过 50 字符 | 47 字符 |
| 图、表 legend 放在摘要之前 | 首页依次为题名、短标题、摘要、关键词、Key messages、表 legend、图 legend |
| 摘要 150–200 词、单段、不含引用 | 180 词 |
| 关键词 4–6 个 | 6 个 |
| Key messages 3–4 条、每条 ≤85 字符 | 4 条，最长 79 字符 |
| 正文匿名且含结论章节 | 7 章：引言、文献、数据、方法、结果、讨论、结论 |
| Declarations of Interest 与 Acknowledgements | 已按模板给出单人声明 |
| AI 使用需说明工具与用途 | 已写明 OpenAI Codex 的有限用途 |
| 引用用作者—年制，参考文献 APA 按字母排序 | 全文作者—年引用；43 条按字母排序，均带 DOI 或 URL |
| 正文字数上限 10,000 词 | 7,446 词（不含参考文献） |
| 图表必须在正文 PDF 内 | 6 表 5 图均已嵌入 |
| 图表另交独立可编辑文件并按号命名 | 见图表目录 |
| 录用后提供 TeX 源文件 | 已附可编译 `.tex` |
| 可提交补充材料 | `supplementary_material.pdf` |

一点取舍需要你知道：双栏排版下只有图 1 通栏，图 2–5 排在单栏宽度，其中图 3、图 5 的面板内小字在纸面上偏小。要改成全部通栏，或退回单栏大图，改一个参数即可重排。

## 四、复现方式（含投稿包）

```powershell
# 1) 重画五张图（含版式审计；任何文字重叠会直接失败）
python revision_20260922_round2/scripts/build_figures_publication.py

# 2) 从冻结结果重建全部表格并生成主文；同时执行合规门控
python revision_20260923_jrmv/scripts/assemble_manuscript.py

# 3) Word 交付件与阅读版 PDF
python revision_20260923_jrmv/scripts/build_deliverables.py
python revision_20260923_jrmv/scripts/build_pdf_reading_copy.py
python revision_20260923_jrmv/scripts/pdf_qa.py

# 4) 投稿包（LaTeX + PDF + 图表可编辑文件）
python revision_20260923_jrmv/scripts/build_submission_pack.py
python revision_20260923_jrmv/scripts/build_title_page.py
python revision_20260923_jrmv/scripts/build_submission_supplement.py
python revision_20260923_jrmv/scripts/build_submission_readme.py
python revision_20260923_jrmv/scripts/submission_final_check.py

# 5) 复现包打包与发布校验
python revision_20260923_jrmv/scripts/build_repo_stage.py
python revision_20260923_jrmv/scripts/build_repo_content.py
python revision_20260923_jrmv/scripts/build_repo_docs.py
python revision_20260923_jrmv/scripts/verify_repo_push.py
```

说明：本机 Word 2007 导出的 PDF 文字层会丢失词间空格，检索与复制异常，因此阅读版与投稿版 PDF 分别用 pandoc + 无头 Chrome、LaTeX(pdflatex) 生成；Word 作为可编辑交付件，LaTeX 作为录稿源文件。

## 五、复现包与 DOI

复现包已发布到公共仓库并完成归档：

- 仓库地址：https://github.com/williamjay1/financial-data-version-risk-validation
- 归档 DOI（concept DOI，始终指向最新版本）：https://doi.org/10.5281/zenodo.22977363
- 本次 release 的版本 DOI：https://doi.org/10.5281/zenodo.22977542
- Zenodo 元数据：题名与论文一致，作者 Zhang, Junjie（ORCID 0009-0004-8821-4018），资源类型 software，许可 MIT，关联标识符指向 GitHub v1.0.1 归档
- 可见性：public；文件 533 个，62.8 MB；五个提交；正文 Data and code availability 只引用归档 DOI，不再重复写仓库地址（按作者要求）
- 内容：`manuscript/`（正文 PDF/Word、补充材料、投稿四件套、五张图 SVG+矢量 PDF、六张表 CSV、LaTeX 源）、`code/`（数据集与四轮脚本）、`results/`（三轮冻结结果、预测、审计）、`docs/`（数据字典、环境锁定、可移植复现脚本、构建与合规报告、Zenodo 记录）、`README.md`、`CITATION.cff`、`LICENSE`（代码 MIT，文本与派生数据 CC BY 4.0）
- 隐私处理：剔除本地缓存、原始下载文件与中间打包压缩包；血缘文件里的本机绝对路径已替换为占位符；未发现任何凭据类字符串
- 后续更新版本时在 GitHub 新建 release 即可，Zenodo 会为新版本铸造新 DOI，concept DOI 始终指向最新版本

## 六、仍需你本人完成的一件事

上传时按平台下拉菜单选择目标期刊；匿名正文用 `main_manuscript_anonymised.pdf`，标题页、投稿信、补充材料与图表可编辑文件按 README 清单作为 supporting files 一并上传。
"""

TARGET.write_text(TEXT, encoding='utf-8', newline='\n')
print('wrote', TARGET, len(TEXT), 'chars')
check = TARGET.read_text(encoding='utf-8')
print('roundtrip ok:', check == TEXT)
print('sections:', [line for line in check.split('\n') if line.startswith('## ')])
