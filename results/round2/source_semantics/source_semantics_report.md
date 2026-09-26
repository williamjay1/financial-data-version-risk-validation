# 第二轮来源语义与影响链复核

## 最重要的判断

**22 项单位倍率差异有显示报表支持，4 项符号替换仍有语义/原始上下文缺口。应保留原 API 主结果，将前26键方案改称争议敏感性。** 新的22键单独重跑中，LightGBM 的 tuned/fixed 全部四格测试预测均与原方案精确一致；LR最大单条预测差分别为0.002534和0.001826。由本代理只读比对保存的预测得出，没有训练或变动模型。[Nobilis原文件](https://www.sec.gov/Archives/edgar/data/1409916/000106299316008351/form10k.htm)

两条关键 changed transition 开发观察均找到发行人披露的实质解释：Rentech 的所得税负债历史修订、Silver Stream 反向收购后会计前身更换。因此，不能把开发阶段敏感性概括成几个 API 低质量输入造成；与此同时，这两个例子不能单独证明总体会计范围变化发生率。[Rentech](https://www.sec.gov/Archives/edgar/data/868725/000119312513112558/d444778d10k.htm)，[Silver Stream](https://www.sec.gov/Archives/edgar/data/1310497/000100201414000402/agsm10ka1-03312014.htm)

## 1. 符号证据的边界

已读取SEC Negative Values官方正文。页面实际标示日期为2017-07-20，不据URL里的07142017改为7月14日。该文要求结合元素定义和借贷语义决定数值符号，并说明展示层可使用negated labels。因此，credit属性本身不等于实例数字应为负，括号也不等于原始实例必须为负。[SEC](https://www.sec.gov/structureddata/announcement/osd_announcement07142017-data-quality-reminder-negative-values)

成功取得并解析FASB官方2012/2013 XSD：NetIncomeLoss为monetary/duration/credit；RetainedEarningsAccumulatedDeficit为monetary/instant/credit；NetCashProvidedByUsedInOperatingActivities为monetary/duration且**没有balance属性**。该结果存于 `canonical_taxonomy_attributes.csv`。这是官方概念定义属性的证据，尚未建立每个发行人当次文件的schemaRef链，尤其不把2012/2013 schema当作2023文件已验证版本。[2012 XSD](https://xbrl.fasb.org/us-gaap/2012/elts/us-gaap-2012-01-31.xsd)，[2013 XSD](https://xbrl.fasb.org/us-gaap/2013/elts/us-gaap-2013-01-31.xsd)

| 公司与原键 | API→前轮显示替换 | 当前判断 | 缺的证据 |
|---|---:|---|---|
| International Shipholding，2011经营现金净额；0000278041-12-000012 | −46,273,000→+46,273,000 | 行名确为现金provided，正值有经济语义支持；仍不能宣称原XBRL符号错误 | 原实例context/entity/unit、presentation role |
| Peabody，2012留存收益比较列；0001064728-14-000015 | −3,066,400,000→+3,066,400,000 | 余额表与权益表均支持正留存收益；credit不是合法负号的充分理由 | 已知确切实例URL但HTTP403；实际context/label未认证 |
| Future FinTech，2020净收益比较列；0001213900-23-022083 | −88,930,311→+88,930,311 | 终止业务处置收益使总净收益为正；不能以营业亏损代替总净收益 | 原实例/上下文、概念及子公司范围、presentation role |
| Majesco，2012累计亏损；0001144204-13-002186 | +90,888,000→−90,888,000 | 展示的accumulated deficit支持负经济余额，但括号不足以认证实例符号 | 原实例context与negated label实际使用 |

每条原文件URL、精确标签/期间/USD、原始与展示值、页内locator、缓存SHA和空白作者签核栏在 `author_pending_sign_confirmation.csv`。四项目前一律sign-unresolved；没有声称人的复核已经完成。严格说，“没有认证”既不证明API值正确，也不证明建议替换错误。[IHC](https://www.sec.gov/Archives/edgar/data/278041/000027804112000012/form10k123111.htm)，[Peabody](https://www.sec.gov/Archives/edgar/data/1064728/000106472814000015/btu-2013123110k.htm)，[Future FinTech](https://www.sec.gov/Archives/edgar/data/1066923/000121390023022083/f10k2021a1_futurefin.htm)，[Majesco](https://www.sec.gov/Archives/edgar/data/1076682/000114420413002186/v327423_10k.htm)

## 2. 来源键到主要输入与阶段

26来源键仅对应6个A/B数值特征单元/6个landmark；其中22 scale键对应2个log_assets单元，4 sign键分别对应4个比率单元。22 scale-only实际应用于28个arm-fact cells；A/B共22，C另6。C是逐标签来源构造，不属于主要预测比较。旧26方案的C数值变化为8格，不能沿用为22方案的C计数。

| 特征单元 | 主要值改变 | 原实验实际阶段 |
|---|---|---|
| Nobilis FY2015 A log_assets | 12.396805→19.304560 | 2016–17 test；2018–19/2020–21 refit |
| Nobilis FY2014 B log_assets | 11.564873→18.472628 | 2018–19 validation/refit；2020–21 tuning/refit |
| IHC A operating_cash/assets | −0.069523→+0.069523（争议） | 2016–17 refit；2018–19/2020–21 tuning/refit |
| Majesco A retained/assets | +1.843645→−1.843645（争议） | 2016–17 validation/refit；2018–19/2020–21 tuning/refit |
| Peabody B retained/assets | −0.193965→+0.193965（争议） | 2016–17 validation/refit；2018–19/2020–21 tuning/refit |
| Future FinTech B net_income/assets | −5.581968→+5.581968（争议） | 2020–21 test |

阶段来自最初正式实验的完整split-membership parquet，未用只有测试记录的简略审计表代替。`source_keys_to_components_features_stages.csv`逐来源组件映射；`six_feature_cells_stage_trace.csv`为六格汇总。统一×1000倍率在对应的A/B比率里抵消，仅留下log资产增加ln(1000)。C混合多来源，部分比率不会抵消。[Nobilis单位标题与各年列](https://www.sec.gov/Archives/edgar/data/1409916/000106299316008351/form10k.htm)

保存预测比对在 `scale22_prediction_effect_summary.csv` 和 `scale22_nobilis_test_prediction_trace.csv`。旧26键对照在 `joint_26_context_prediction_effect_summary.csv`，必须标成联合争议替换；不能将其全局重拟合影响分配给某一单键。此次没有模型训练，没有测试后改进策略。

## 3. 关键开发/事件来源针对性检查

这轮新增21项显示金额检查，覆盖Rentech、Silver Stream、Gymboree；另对RCS/AHR/RTW复用12项已冻结显示审计，并重读范围解释。它们是目的抽查，不添加到原24随机样本，不计算发生率。21项均为display-supported，original-XBRL上下文认证仍为0；这一计数不意味着只凭API互证。[新旧文件来源见下表]

| 对象 | 原/后组件与机制 | 对主要解释的意义 |
|---|---|---|
| Rentech：2011-12-31，2012提交10-KT | A/B资产360.528m一致；负债105.200→112.255m，流动负债51.725→58.780m，权益215.903→208.848m。后报Note3给出前后对照，原因是出售RNP相关权益增加的所得税应付少计；发行人称不重大。另0.468m流动资产变化未在本审计中确定机制 | 三个正式块的开发阶段均出现；是真实修订，不能概括为抽取错误 |
| Silver Stream/W.S. Industries：FY2013，2014提交10-KT | A资产22,245、负债1,178,561、净亏损298,977；B资产1,413,856、负债3,258,886、净亏损1,311,915，现金也均对应原显示。A Note10和B Note1说明2013-05-14 RTO，Rio Plata为持续会计主体 | 原/后年度相同，经济主体历史不同；前两块refit、最后块tuning/refit |
| Gymboree：2016-07-30 | 原报告26周transition；A/B七个instant组件均不变。复核资产1,178.512m、负债1,451.785m、累计亏损792.851m两侧显示一致 | 唯一阳性transition；2016–17 test、2020–21 refit。去除它是评价/开发样本变化，不是去除该行的A/B版本差 |
| RTW：2020-02-01 | A=B；资产411.984m、负债396.027m与显示一致 | 该事件簇影响排名，不能把影响大反推为数据错误 |
| RCS：FY2013 | First Allied与母集团共同控制，后报历史成本追溯合并；资产111.127→336.525m | common-control recast，不等于简单财务纠错 |
| AHR：FY2020 | GAHR IV法律收购方，GAHR III会计收购方；后报历史前身切换；资产1,092.773→3,234.937m | 与Silver Stream同属会计范围变化，但不是同一交易/同一阶段证据 |

来源： [Rentech A](https://www.sec.gov/Archives/edgar/data/868725/000119312512117369/d286883d10kt.htm)、[Rentech B Note3 p88](https://www.sec.gov/Archives/edgar/data/868725/000119312513112558/d444778d10k.htm)、[Silver A](https://www.sec.gov/Archives/edgar/data/1310497/000100201414000290/ssmc10kt-3312013.htm)、[Silver B](https://www.sec.gov/Archives/edgar/data/1310497/000100201414000402/agsm10ka1-03312014.htm)、[Gymboree A p38](https://www.sec.gov/Archives/edgar/data/786110/000119312516751374/d231280d10kt.htm)、[Gymboree B p5](https://www.sec.gov/Archives/edgar/data/786110/000119312517082009/d268566d10q.htm)、[RTW](https://www.sec.gov/Archives/edgar/data/1211351/000104746920003464/a2241712z10-k.htm)、[RCS](https://www.sec.gov/Archives/edgar/data/1568832/000156883215000014/rcap-20141231x10ka.htm)、[AHR](https://www.sec.gov/Archives/edgar/data/1632970/000163297022000020/ahr-20211231.htm)。

## 4. 获取状态与可复核性

- Exa主检索按agent-reach执行；本轮SEC指导页成功读取后，后端报告免费额度限制。随后使用官方URL的web读取、直接HTTP和Jina公开网页清洁文本。未绕过付费或登录。
- FASB两份XSD与SSE原始PDF直接HTTP200下载到E，保存后只读。Silver Stream两侧、Gymboree A为Jina清洁文本，显式不是原始HTML副本。
- Peabody官方index确认原始实例文件名 `btu-20131231.xml`，但直接请求403，web也不可读。其他三项index读取失败，没有虚构instance链接或context。
- 所有旧项目文件只读。新CSV/报告/Python在D；新原件只写独一文件名到E后设只读。没有改写旧26键表或旧模型结果。
- 归档元数据记录真实URL/返回状态/哈希，不把403错误响应计作已取得实例。

## 5. 文献与结论接口

Hashemi与Jonsson2017全文是直接原报/重述破产概率比较先例，应恢复引用并明确硕士论文身份。它否定“首次比较财务输入版本”的表述；不能据其文献级别低而抹去先行思想。见 `literature/hashemi2017_recheck.md` 和 `literature/manuscript_source_notes.md`。[官方全文](https://arc.hhs.se/download.aspx?MediumId=3871)

来源层结论：**证据足以支持区分不同来源变更机制、展示开发/评分输入选择的受限实验；不足以支持原始XBRL全面认证、26项确定错误、或已认证纠错改变LightGBM的一般命题。** 稿件是否达到目标期刊水平仍取决于中心比较的结果及精度；本来源审计不宣布投稿GO。
