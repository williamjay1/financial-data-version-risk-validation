# 成稿依据与主张边界

日期：2026-09-21。文章类型：SCIE应用预测评价/测量研究；无因果识别或新算法优越性主张。候选读者：金融风险预测、财务数据构建与机器学习评价研究者。目标期刊类型以 Expert Systems with Applications 的应用研究范围为参照，未投稿。

## 一句话贡献

在保留原始可观测性、明确抽样权重和直接登记事件口径的配对队列中，展示财务版本选择对重新训练和固定模型评分产生不同评价结果，并用原始报表与事先指定的敏感性分析限制其解释。

## 实际证据

- 历史框架：2010—2021年、15,631个CIK、93,677个原始年度申报CIK记录；48季度齐全。
- 抽样：383个含直接登记CIK的共申报簇全纳入；其他14,546簇中固定种子简单随机抽取1,000簇；共1,518个CIK。
- 当前队列：5,502窗口、990个CIK、973共申报簇、188个正窗口和188个不同事件CIK。
- 数据核验：17项最终机械检查通过，包括3,032个可用SEC工作缓存哈希、全部30项版本特征重构、直接首事件标签与抽样元数据。
- 正式实验：主分析和两项敏感性各48个候选拟合、12个最终模型；主分析另有6个固定A模型的输入替换比较，两组各1,000次设计型重抽样。
- 主模型独立审计：297项通过，保存模型与预测可重演。保留早期调参训练仅3个正例、验证仅7个正例的告警。
- 原始来源：Nobilis已核实单位倍率差错；RCS同一控制下收购导致比较数据追溯纳入。二者不能合并称为财务错报。

## 结果对写作的约束

主分析LightGBM三块ΔAP为正，但Brier均变差；固定A模型首块ΔAP为负。排除12个10-KT窗口后最后一块ΔAP变为−3.90个百分点，必须进摘要与主表。没有LR/LightGBM的AP排名逆转；只有差距大小变化。不得宣称稳定增益、普遍乐观偏差或改善校准。

## 关键证据映射

| 稿件主张 | 可复核来源 |
|---|---|
| 样本形成、年度覆盖 | cohort_summary.json、cohort_flow.csv、cohort_annual_counts.csv |
| 同队列、同缺失mask、首事件与权重 | final_data_gate.json、sampling_frame_summary.json |
| 主评价、调参与时间划分 | final_run_index.json所列主models manifest/metrics/predictions |
| 条件不确定性 | 两个uncertainty manifest/summary/replicates |
| 单位修正与过渡报告敏感性 | sensitivity_design.json、两个指定sensitivity模型run |
| 图表分母与原始事实 | descriptive_*_feature_changes.csv、denominators.json、vintage_facts.parquet |
| 来源例证 | manuscript/source_examples.md及references.bib中的4份SEC原始报表 |
| 文献增量与范围 | manuscript/literature_map.md、venue_notes.md、final_interpretation_review.md |

## 正式判断

**成稿阶段：GO。投稿阶段：CONDITIONAL。** 可以交付一篇真实完成的研究稿；不能把该判断表述为保证SCIE录用。当前最关键限制是历史API真值不可完全恢复、登记库目标比所有破产窄、早期调参事件稀少、条件区间不含训练和案例组成不确定性。稿件如实报告这些限制与反向敏感性。是否投ESWA需要按当前真实贡献评估编辑门槛，并由作者完成署名、利益冲突、资金、AI使用认可及适用数据共享手续。

## 运行变更说明

正式分数读取前固定抽样、候选网格、时间划分、两项敏感性。完整数据门禁首次运行发现核验脚本两个MultiIndex的accession层名不同，造成错误join；将层名对齐并加one_to_one校验后通过。该修正不改变队列或数据值。全稿保留不利结果，不以测试成绩挑选报告块或改画图范围。
