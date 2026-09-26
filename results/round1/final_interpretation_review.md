# 正式结果的独立解释审查

审查日期：2026-09-21。审查者：finance_route。范围：已完成结果、近邻定位、贡献强度和投稿文字边界；不重新训练、不修改输入、不调整测试策略。本报告读取正式结果表及已完成的原始文献核验，未重新计算全部预测指标，也未进行新的全面文献检索。逐行数值及运行审计由另一独立代理负责。

## 1. 判断与路径卡

**判断：可以完成一篇范围明确的预测评价研究稿；ESWA 投稿状态仍为 CONDITIONAL，主线为 NEEDS STRENGTHENING，不能签发投稿 GO。** 当前结果确实支持“可追溯的财务版本选择会改变指定流程的评价”，但不支持“未来版本稳定提高预测能力”“普遍造成向上的回测偏差”或“本方法稳定泛化”。最有价值的证据是，来源含义、重新拟合和单纯更换输入回答不同问题，而既有设定的敏感性会改变结论方向；是否达到 ESWA 所需增量，须由完整稿中的比较和可复用成果证明，不能用透明或小样本本身替代。[主分析](models_20260921T093517075175Z_paired_differences.csv)；[冻结模型诊断](models_20260921T093517075175Z_frozen_a_paired_differences.csv)；[排除过渡年报](sensitivity_no_transition/models_20260921T093617432022Z_paired_differences.csv)

- **Route：SCI，预测评价与财务数据测量。** 核心不是新分类器，也不是会计行为的因果解释。
- **Primary standard：** 版本事实可追溯、抽样与观测域清晰、成对比较公平、时间划分正确、不确定性和失败完整报告。
- **Do not use：** 不另加经济学因果识别门槛；不以分类器领先排行榜为本研究贡献；不把数据缺陷审计自动视为可发表主线。
- **Next workflow：** sci-full-workflow；本轮应用 paper-verification、literature-review 和 quantitative-analysis。下述判断以[现行方法](../manuscript/front_methods.md)、[文献地图](../manuscript/literature_map.md)及[官方期刊核验](../manuscript/venue_notes.md)为范围。

**建议一句话贡献：** 与财务信息质量及标签时点研究相比，本研究在明确限定的历史报送观测域内，将逐事实来源匹配与同一队列的成对预测评价连接起来，量化当前 API 中原提交记录与后续比较记录的选择如何改变整套拟合流程和固定模型的评价，并展示两类变化不可互换解释。这里的增量是可验证的评价能力与具体证据；“首次”“普遍”“稳定”均不在支持范围。[匹配规则](../manuscript/front_methods.md)；[来源例证](../manuscript/source_examples.md)；[正式结果](models_20260921T093517075175Z_metrics.csv)

## 2. 正式证据支持到哪里

### 2.1 主分析、冻结模型与敏感性必须并列

以下均直接读取正式表。AP 差值以百分点表示；区间为本研究报告的条件性、点态 95% 区间，**不是包括模型选择和破产案例组成不确定性的总区间**。

| 测试期 | 主分析 LightGBM ΔAP | 条件区间 | 固定 A 模型，仅换 B 输入 ΔAP | 排除 10-KT 后重新拟合 ΔAP |
|---|---:|---:|---:|---:|
| 2016–2017 | +2.839 | [−0.663, +5.860] | −2.777 | +2.802 |
| 2018–2019 | +2.768 | [−2.719, +5.094] | +1.367 | +2.619 |
| 2020–2021 | +1.766 | [+0.603, +8.140] | +0.112 | −3.898 |

来源：[主差值](models_20260921T093517075175Z_paired_differences.csv)、[主区间](uncertainty_20260921T093555450801Z_summary.csv)、[冻结差值](models_20260921T093517075175Z_frozen_a_paired_differences.csv)、[S2 差值](sensitivity_no_transition/models_20260921T093617432022Z_paired_differences.csv)。本报告只作单位换算与解释，没有重新估计区间。

可以写“主分析三期 LightGBM 的 AP 点估计较高”。不能省略前两期区间跨零、固定模型首期为负、S2 最后一期方向反转。重新拟合对比包括训练数值、预处理、调参和模型参数变化；固定模型诊断只有测试输入变化。两者之差不是一个已识别的因果机制或可相加的效果分解。[两类比较定义](../manuscript/front_methods.md)；[冻结区间](uncertainty_20260921T093555459899Z_summary.csv)

S1 仅按已经核验的 accession 修正 Nobilis 倍率；与主分析相比，LightGBM 三期 AP、Brier、ROC 及召回差值在存储表中完全相同。因此可以说**这些主分析 LightGBM 差值没有由这一项已核验错误驱动**；不能说已排除所有单位、标签或会计范围问题。S2 删除全队列 12 条过渡年报窗口，其中 1 条阳性；它同时改变训练和评价观测域，2020–2021 的 ΔAP 转负、Δrecall 从 +11.36 变为 −11.36 个百分点。不可把这一反转归因于“12 个测试异常值”，也不能将 S2 写成同总体下的纯因果消融。[S1 差值](sensitivity_source_scale_corrected/models_20260921T093617431021Z_paired_differences.csv)；[敏感性定义及计数](sensitivity_design.json)；[S2 差值](sensitivity_no_transition/models_20260921T093617432022Z_paired_differences.csv)

### 2.2 排序能力、概率质量与模型名次不能混写

主分析 LightGBM 的 Brier 差值为 +0.000097、+0.000241、+0.001228，均为变差方向。后两个测试期，A 和 B 的 LightGBM Brier 都高于成熟样本频率构造的常数概率基准；较高 AP 并不支持可部署概率质量更好。Brier 不是纯校准指标，校准截距的正负变化也不是自动改善，必须看相对于 0 的距离及斜率相对于 1 的距离。不得统称“AP 和校准均改善”。[完整指标与常数基准](models_20260921T093517075175Z_metrics.csv)；[概率评价的文献用途](../manuscript/literature_map.md)

两种版本下 LightGBM 的 AP 都高于 LR；主分析及两项敏感性没有观察到这两个模型的 AP 名次翻转。可以说模型间的**差距大小**依赖版本，不可声称已证明“模型排名逆转”。此外，主分析 LR 在 2018–2019 的 AP 变化很小，却有 −10.71 个百分点的五百分位容量召回变化；因此“小 AP 差异”也不能概括成“LR 的所有决策都不受影响”。容量指标本身是异步年度报送窗口的事后排序，尚非真实动态筛查政策。[完整指标](models_20260921T093517075175Z_metrics.csv)；[成对差值](models_20260921T093517075175Z_paired_differences.csv)；[容量定义](../manuscript/front_methods.md)

### 2.3 样本量和区间的可信范围

冻结队列为 5,502 个窗口、990 个 CIK、973 个 cofiling cluster、188 个阳性窗口及 188 个事件关联 CIK。三期测试分别有 51、28、44 个阳性窗口；这些计数是本次观测域，不是所有美国破产公司或独立法律集团的数量。初始调参训练仅 3 个阳性，验证仅 7 个，最终重拟合 39 个；其后两期调参/验证/重拟合阳性为 27/24/95 和 64/20/124。需把开发计数放在正文关键表，不能让 5,502 总行数掩盖初始模型选择依据薄弱。[队列摘要](cohort_summary.json)；[正式 manifest 的 split_manifest](models_20260921T093517075175Z_manifest.json)

区间固定 certainty stratum 中的阳性案例与已拟合模型，只重抽被概率抽中的非案例簇；其狭窄程度不能回答“换一批破产案例或训练模型是否仍这样”。共同企业跨年、三个宏观区间以及只有两种诊断学习器，也不构成独立的跨总体验证。2020–2021 主 AP 区间虽不含零，仍不能跨过 S2 的反证或升级为稳定泛化。[不确定性定义](../manuscript/front_methods.md)；[主区间](uncertainty_20260921T093555450801Z_summary.csv)

## 3. 近邻已经做过什么，本稿还增加什么

这里复用已有原文审读，不因正式结果出来而重新制造“空白”。证据状态沿用文献地图：A 为相关原文已读；A-part 为原始正文关键片段已读；B 为摘要、元数据或综述转述。

| 近邻及证据 | 已占据的问题 | 本稿可保留的差别与限制 |
|---|---|---|
| Beaver, Correia & McNichols 2012；B；Correia 2025 正式全文 A | 财报属性、后来重述及会计信息预测作用。 | 不能说首次发现财报质量影响破产预测。可把当前 API 逐事实来源规则与固定队列、成熟时序、两类评价实验连接起来；不要将综述转述写成已独立复现 2012 原始试验。[2012](https://doi.org/10.1007/s11142-012-9186-7)；[2025](https://doi.org/10.1080/00014788.2025.2516273) |
| Yang & Zhu 2026；A-part；2025 在线先行 | 错报标签被发现的滞后如何改变预测评价。 | “真实可得时间重要”不是创新。本文审查预测输入版本，且自己的 BRD 历史收录时点仍未被实测；90 天缓冲只是固定假设。[正式文章](https://doi.org/10.2308/tar-2023-0073) |
| Mattos & Shasha 2024，ESWA；作者全文 A | 重整企业的低质量财报、缺失信息与恢复/失败预测，含拒判。 | 不同于历史报送框架内未来直接关联 BRD 事件的评价；仅以“低质量、小样本、缺失指示”立题会重复。应具体呈现成对来源与评价程序的贡献。[正式条目](https://doi.org/10.1016/j.eswa.2023.121418) |
| Zhang et al. 2026；预印本全文 A | 10-K 文本、财务基线、BRD 事件与报送日预测原点。 | 不能把报送日和 BRD 结合视为新任务；本稿披露可执行的 accession 匹配和风险集界定。但对方未披露某规则，不等于已经证明其发生泄漏。[v1 全文](https://arxiv.org/html/2606.05623v1) |
| Hashemi & Jonsson 2017；硕士论文 A-part | 原始/重述会计输入的经典破产概率成对比较。 | 不能说首次对比原始与后续财务输入。本稿新增时序训练评价、相同观测域与来源语义核验；该先例是灰文献，不抬高为同行评议强证据。[机构全文](http://arc.hhs.se/download.aspx?MediumId=3871) |
| Kozodoi et al. 2025；作者全文 A | 选择性标签与信用模型训练/评价偏差，使用另获真值的验证样本。 | BRD 未登记不能替换为已知健康；设计权重只处理规定抽样，不能恢复注册遗漏或不可观测财务的结局。[正式文章](https://doi.org/10.1016/j.ejor.2025.01.040) |

目前新证据最有希望支撑的是**金融数据重建与预测评价的连接**，不是新机器学习方法，也不是重述的因果效果。Nobilis 的单位倍率错误与 RCS 的同一控制下范围重编说明“同概念、同期间、同 accession 规则”仍不足以保证经济可比；这两例能说明不同变化机制，却没有估计各机制的总体频率，更没有将整项 ΔAP 分解给两例。[来源例证与正式 SEC 引用](../manuscript/source_examples.md)；[来源审计](../manuscript/extraction_audit.md)

**旧材料提醒：** 文献地图第 5 节的“相同真实信息预算”是设计阶段遗留措辞，最终稿不应照抄。B 明确使用后续材料，信息预算并不相同；公平的是两臂的观测对象、初始缺失模式及拟合规则。现行方法已写清 B 不能在原预测日使用，本轮未修改旧文献文件。[旧地图](../manuscript/literature_map.md)；[现行方法](../manuscript/front_methods.md)

## 4. 最易误述的句子与替代写法

| 不应写 | 可替换为 |
|---|---|
| We recover the financial data available to investors in real time. | We reconstruct values associated with the original accession in the retrieved companyfacts data; the reconstruction is not an authenticated historical API snapshot. |
| Restatements inflate bankruptcy prediction performance. | Later comparative values change the evaluation of the specified pipelines, with directions that depend on the learner, metric, and fitting protocol. |
| Later versions consistently improve prediction and calibration. | Main analysis AP point estimates increase for refitted LightGBM, while Brier scores worsen and the direction of the AP difference reverses in the final block when transition reports are excluded. |
| Our framework changes the ranking of competing models. | Version choice changes the observed AP gap between the two learners; their ordering does not reverse in these experiments. |
| The results generalize robustly across three periods. | The three chronological blocks reveal variation within this registry-defined observation domain; they do not establish generalization to new case populations or economic regimes. |
| We estimate the causal effect of financial restatement. | The paired design evaluates operational version rules while holding observations and initial missingness fixed; the rules combine changes with different accounting and extraction meanings. |
| A narrow bootstrap interval confirms that rare-event uncertainty is small. | The intervals quantify the stipulated sampling-design uncertainty conditional on observed cases and fitted models. |

这些替换分别由[版本方法](../manuscript/front_methods.md)、[主指标](models_20260921T093517075175Z_metrics.csv)、[S2](sensitivity_no_transition/models_20260921T093617432022Z_paired_differences.csv)、[区间](uncertainty_20260921T093555450801Z_summary.csv)和[SEC 例证](../manuscript/source_examples.md)支持，不构成结果以外的新推断。

**可用的英文结论段：**

> Financial version rules changed the evaluation of the specified bankruptcy prediction pipelines within the observed registry domain. Refitting LightGBM on later comparative values increased average precision in the main analysis, but did not improve Brier score. Replacing only the inputs to a fixed original-version model produced a different pattern, and excluding transition reports reversed the final block's AP contrast. These findings support explicit source matching and separate reporting of input substitution and complete pipeline refitting. They do not establish a general direction of version bias, a superior deployable model, or a causal effect of accounting restatement. The inference remains conditional on the accessible financial records, directly linked registry events, and fitted models, with particularly limited information for the earliest model-selection stage.

该段须与完整数字表及上述条件区间共同出现；不能用它替代证据呈现。[主结果](models_20260921T093517075175Z_metrics.csv)；[冻结结果](models_20260921T093517075175Z_frozen_a_paired_differences.csv)；[S2](sensitivity_no_transition/models_20260921T093617432022Z_paired_differences.csv)

## 5. ESWA 为什么仍为 CONDITIONAL

1. **范围适配，但贡献强度未由范围自动保证。** 官方范围包含 finance、accounting 和 risk assessment；2024 低质量财务论文是直接近邻。本稿若完成可复用的逐事实匹配、核验与评价流程，可以有应用智能系统评价价值；若只剩两个异常例子和三个不稳定差值，属于有限数据审计，不足以承诺研究稿录用。[官方作者指南及范围](https://www.sciencedirect.com/journal/expert-systems-with-applications/publish/guide-for-authors)；[直接近邻](https://doi.org/10.1016/j.eswa.2023.121418)
2. **文献增量必须体现在交付能力，而非新颖标签。** 必须在正文展示读者能复用的明确规则、来源错误的处置原则、匹配失败和适用边界，并使关键表足以独立读懂。最终结果只能证明本域中的评价敏感性；不能将“S1 无影响、S2 反转”包装为稳健优势或另换有利窗口。[来源例证](../manuscript/source_examples.md)；[敏感性设计](sensitivity_design.json)
3. **少事件与统计限制是主证据约束。** 首期 3/7 个开发阳性、条件性区间、有限学习器及无外部总体验证，需要直接进入摘要或讨论的关键限定。完成文字修改可以消除夸大，不能使这些设计限制消失；本轮不建议按测试成绩重新选超参、删除不利设定或发明新策略。[正式分割](models_20260921T093517075175Z_manifest.json)；[区间](uncertainty_20260921T093555450801Z_summary.csv)
4. **资源与投稿闭环仍须完成。** 需确认引用实际使用、数据和代码可供匿名复核、BRD 等输入许可与再发布边界、关键规则和样本计数留在正文、作者及 AI 声明真实。出版商页面已列 SCIE，但此前未完成 Clarivate MJL 独立核验；这与文章是否达到接收门槛是两回事。本轮不引用未经核实的分区、录用率或审稿速度。[期刊核验](../manuscript/venue_notes.md)；[官方 Insights](https://www.sciencedirect.com/journal/expert-systems-with-applications/about/insights)

## 6. 三个拒绝假设与最终门判断

| 拒绝假设 | 当前反证/未关闭部分 | 判定 |
|---|---|---|
| H1：所谓历史信息差异主要混合 API 尺度、会计范围、后续可观察性与注册覆盖选择。 | 正式 SEC 原文确认至少两种含义；A 不是历史 API 快照；S1 仅排除一个已核验错误驱动指定指标的解释，不能净化所有数值差异。 | **主要风险；通过收缩对象为 operational version rules 管理，不能宣称已全部排除。** [来源例证](../manuscript/source_examples.md) |
| H2：观察到的差异依赖稀少事件驱动的模型选择与训练域，而非普遍的输入版本作用。 | 首期开发案例极少；冻结 A 与 refit 不同；S2 最后一期反转。 | **反证已经出现，必须纳入中心结论。** [manifest](models_20260921T093517075175Z_manifest.json)；[S2](sensitivity_no_transition/models_20260921T093617432022Z_paired_differences.csv) |
| H3：高 AP 被误当作概率质量、真实筛查收益或可推广模型优越性。 | Brier 与 AP 方向不同；名次未翻转；容量为事后块内筛查；无完整实时系统验证。 | **可用多指标和收缩主张处理，不能改写为已部署价值。** [指标](models_20260921T093517075175Z_metrics.csv) |

**设计充分性：** 对固定、可观测注册域内的成对流程敏感性问题，具备可解释证据；对一般破产风险、历史真实可得快照或稳定泛化，不充分。**主线可发表状态：NEEDS STRENGTHENING。文献比较：主要重复边界已清楚，但不授予首次性。期刊匹配：范围中高，贡献与证据门条件性。决策：完成全稿和审计为 GO；立即正式提交为 CONDITIONAL。** 完稿不等于研究限制已消失，也不等于可以用低概率特殊路径保证成文。[方法](../manuscript/front_methods.md)；[文献地图](../manuscript/literature_map.md)；[期刊核验](../manuscript/venue_notes.md)

## 7. 本次审查输入记录

仅记录内部可追溯性，不复制到论文正文。审查时主 manifest 状态为 `completed`。以下 SHA-256 与本报告读取的版本对应；后续全稿审查仍需确认稿件引用同一版本。

| 文件 | SHA-256 |
|---|---|
| 主 manifest | `edbc6d675ee029580daba70ab50530cf456004fb20dc2a425df11cfb88b6c475` |
| 主 metrics | `6e0776bf96981159a5d20fd5059051cf478d891722e559860764d9747f7c1a54` |
| 主 paired differences | `54987acf3222ac43638d5df50ce0c992d47ced57a179d917685ab5a1dc2d6190` |
| frozen A paired differences | `64467834bcfaaef30b4dcb283e58b92bce04c695b3bff1992b854d61814ff81e` |
| 主 uncertainty summary | `957940b3347ccb1dd31430d63ba65c77527020c6ce48eaa84973beda60d9bab6` |
| frozen A uncertainty summary | `d45df253f2b461983286fe4ef5140649543dde47ed2fccf989b896715ea53cab` |
| S1 paired differences | `d74454644092306b4b324a418a37339f6de65043b335cb41cbbec173d7b611bd` |
| S2 paired differences | `a53c6411c46e39054bdb480acb5752e43043da6997a133ba0b01a62a7b423a0f` |
| front_methods.md | `f9a2930d0232f73ee9e64a3c01090abeb0943222d9e0fd49a36417ec92b36bd2` |

本轮只新增本审查文件。没有修改任何正式模型、结果、论文正文或文献库，没有根据测试结果设计追加策略。

## 8. 完整稿逐项审查追加

审查对象：[manuscript.md](../manuscript/manuscript.md)，本次快照 SHA-256 为 `86ae1bf887316a0501f0f9b591977625c43de99ea7ca59c8a8f1389227d906f5`，共 339 行。逐行读完摘要、正文、附录、表注和引用调用；没有修改稿件。以下行号仅指该快照。

**本次发现：新增致命问题 0，新增重大事实/引用/口径错误 0，新增结论夸张 0。可交付研究稿；可进入 Word 排版与视觉核验；正式投稿仍为 CONDITIONAL。** 这不是对未完成公开包、许可或作者确认的替代认证。[稿件](../manuscript/manuscript.md)；[正式主结果](models_20260921T093517075175Z_metrics.csv)；[期刊核验](../manuscript/venue_notes.md)

| 具体核查点及稿件位置 | 核查依据与结果 |
|---|---|
| 摘要 L8：5,502/990/188、23.8%、主及 frozen AP、S2 −3.90、API 快照边界 | 与队列摘要和指定主/敏感性表一致；已在摘要披露 Brier 变差、S2 反转及 CI 缺失的两类不确定性。没有把主分析的正向点估计称为稳定收益。[队列](cohort_summary.json)；[主差值](models_20260921T093517075175Z_paired_differences.csv)；[S2](sensitivity_no_transition/models_20260921T093617432022Z_paired_differences.csv) |
| 引言 L16–24：近邻的含义与贡献 | Mattos 的重整对象、Yang 的发现滞后、Zhang 的预印本及 Hashemi 的研究生论文身份均保持边界；没有以规则未披露指控对方泄漏，也未声称首次或新分类器。33 个实际引用键均存在于 Bib，未发现无法解析键。[文献地图](../manuscript/literature_map.md)；[引用库](../manuscript/references.bib) |
| 数据与方法 L32–60：总体、单位、标签、A/B/C | cofiling cluster 与法律集团分开；只用直接 CIK；零标签未写成健康；A 明确不是历史 API 快照；B 的同 accession 不等同经济范围。源数据门亦确认旧 C 计数遗漏已修复。[最终数据审计](final_data_gate.json) |
| 时序与区间 L66–86、L121–131、L174–176 | 90 天为假设；开发 3/7、最终39与后续折计数正确；CI 固定模型、已知案例与点态性质写清。Table 2 将小事件开发依据放在正文，原“仅补充材料”问题已关闭。[manifest](models_20260921T093517075175Z_manifest.json)；[区间](uncertainty_20260921T093555450801Z_summary.csv) |
| 样本流 L98–139 与 Table 1 | 流表的 9,789→8,398→7,426→5,502 及 CIK/阳性计数一致；48/628 年度窗口数吻合。独立读取冻结队列核得 B 可得4,128/加权75.4618%，B变化1,307/加权21.9113%，C变化2,245，C多来源5,115/加权93.0009%，中位后续报送间隔364天，均支持相应舍入文字。[流表](cohort_flow.csv)；[冻结队列](../datasets/model_cohort.parquet) |
| C 零资产 L139 | 对两个 C_log_assets 缺失窗口进一步读取原事实缓存：CIK0001554054、accession0001165527-13-000772 的 A/B/C assets=136/136/0；CIK0001581545、accession0001607062-14-000059 为9214/9214/0。支持“C 有两个零分母，A/B 为正”的具体说法；没有从其推断 C 模型性能。[事实缓存](../datasets/vintage_facts.parquet) |
| 两个来源例证 L147–155 | Nobilis 年份、filed 日期、单位、11字段与母公司/合并口径分开；RCS 的2013比较期、2014收购、2013 common-control 起点及2015修订文字纠错分开。沿用已实读 SEC 原文的核验，没有把所有差异叫 restatement。[来源例证](../manuscript/source_examples.md)；[原来源审计](../manuscript/extraction_audit.md) |
| 主模型及区间 Tables 3–4、L176–180、Appendix B | 关键 AP、百分点换算、舍入后的 CI、Brier、常数基准和主要选参均与已存表一致；没有名次逆转主张。校准截距与自由截距斜率的不同拟合定义在 Table B1 注释已解释，不误读成同一回归的截距斜率对。[主指标](models_20260921T093517075175Z_metrics.csv)；[冻结指标](models_20260921T093517075175Z_frozen_a_metrics.csv) |
| 敏感性 L201–216 与 Table 5 | S1 修正范围、S2 的12条/1阳性/5,490、最后期 AP 与 recall 双反转正确；明确训练和测试域同时变动，未作删除12个测试点的错误归因。未以敏感性挑选新主设定。[敏感性设计](sensitivity_design.json)；[S2 指标](sensitivity_no_transition/models_20260921T093617432022Z_metrics.csv) |
| 讨论与结论 L222–248 | 将程序敏感性作为证据，没有“稳定泛化”“一致乐观偏差”“校准改进”“因果重述效应”“交易获利”等越界结论；已说明原值可观察域、稀少案例、两学习器与外部有效性限制。[正文](../manuscript/manuscript.md) |
| 附录与交付 L258–334 | 精确标签层级、分母、完整不利主指标和选参在同一正文稿内，已解决先前依赖 Supplementary Table S1/S2 的问题。三个插图路径均存在；本轮只核路径/数据口径，视觉质量留给 Word 渲染核验。[稿件](../manuscript/manuscript.md) |

**一个非阻断的具体微修：** 摘要已经说明训练不确定性，但没有直接写首期 3/7 个开发阳性；该数字目前位于正文与 Table 2。若希望让摘要读者同样看见，可加入 “The earliest tuning and validation sets contain only three and seven event windows.”，仍可保持在250词限制内，由生成稿脚本最终计数。本条是提升可见性的建议，不是已发现事实错误。[摘要和 Table 2](../manuscript/manuscript.md)

**保留的投稿条件不是新发现的代码或文字漏洞：** 数据包尚未取得公共仓库标识；输入再发布权限不能由“公开可下载”推定；研究的适用域和不确定性限制已经如实呈现，但这种呈现本身不能保证达到 ESWA 的主线贡献门槛。可向用户交付诚实、完整的研究稿，并明确当前处于投稿前条件审查状态。[可用性声明 L250–252](../manuscript/manuscript.md)；[期刊范围与政策](../manuscript/venue_notes.md)
