# A/B 抽样不确定性模块

状态：代码与合成有限总体检查已完成，**尚未运行正式预测结果**。真实 sampling_frame 只做了只读结构检查：383 个全取簇、14,546 个非案例总体簇、其中 1,000 个 SRS 簇。

## Python 接口

```python
result = paired_uncertainty(
    predictions,                 # 长表 pandas.DataFrame
    sampling_frame,              # 全部总体框，不能只传eligible或selected子集
    n_boot=1000,
    seed=20260921,
    models=("LR", "LGBM"),
    analysis_mode="refit_vintages",
)
```

返回 `summary`、`replicates`、`cell_audits` 三个 DataFrame，以及 `design` 字典。函数本身不写文件、不拟合模型。

预测表必需列：`row_id, cluster_id, cik, block, model, version, label, pred`。兼容 `registry_event_365` → `label`、`prediction` → `pred`；若两套别名均存在必须相同。`version` 为 A/B。`sample_weight`、`inclusion_probability`、`sampling_stratum`、`certainty` 若存在会与锁定总体框核对；权重最终以总体框为准。PREVALENCE/shared 行被明确排除并计数。

每个 block/model 的 A/B 必须为同一批 row_id、CIK、簇、标签和权重。row_id 不可跨测试时间块；每个出现的 block 必须有全部指定模型。

固定 A 模型、分别输入 A/B 数据的额外诊断必须单独调用：

```python
paired_uncertainty(frozen_predictions, sampling_frame,
                   analysis_mode="frozen_A_inputs")
```

其 `scenario` 必须分别为 `A_model_A_inputs` / `A_model_B_inputs`，并在所有结果写入独立 `analysis_mode`。这种表不允许被当作主 refit 对照，两个比较也不能拼成同一预测输入表。

## 抽样重权与指标

非案例簇采用无放回简单随机抽样。记总体簇数 N、原样本簇数 n、f=n/N；每次从全部 n 个已选非案例簇有放回抽 m=n−1 次，得到簇计数 M_i。原始设计权重 d_i=N/n，重复权重为：

`d_i* = d_i × [1 + sqrt(1−f) × (n×M_i/(n−1) − 1)]`

本数据 n=1000、N=14546、f=0.06874742197167606，`sqrt(1−f)=0.9650142890280557`。每次抽 999 个簇计数。确定性簇的权重固定为 1。一个簇全部企业、全部年度观测同时使用同一倍率。即使某个已抽簇没有任何合格测试观测，它仍在原 1000 个抽样簇中，贡献值为零而不是被删除。所有 block/model/A/B 使用同一套重复抽样倍率；当前分别给逐 block、逐 model 区间，不做“三个独立宏观实验”的汇总。

该权重形式见 [Rao–Wu 实现公式](https://cran.r-project.org/web/packages/surveysd/vignettes/raowu.html)。权重重标定适用于较广泛统计量，且需反映原抽样设计；方法沿革与局限见 [Statistics Canada 的 rescaled bootstrap 论文](https://www150.statcan.gc.ca/n1/pub/12-001-x/2009002/article/11044-eng.pdf)。本实现针对一层非案例簇 SRS，不是任意复杂抽样通用器。

指标都是同一有限总体合格 filing-window domain 的设计权重估计：

- `average_precision`：与 sklearn 加权 AP 一致，精确同分合组。
- `brier`：权重归一化后的平方误差均值，即 Hájek 比率形式。
- `roc_auc`：加权 ROC 曲线面积，正确处理同分。
- `retrospective_recall_at_5percent`：按预测分数排序，容量为本重复中合格观测总权重的 5%；边界同分组的所有成员使用同一 fractional 入选比例。每个重复重新计算阈值，不能直接复用原预测表的 selection_fraction。

Recall 的分母是正例申报窗口的权重，**不是不同公司或不同破产事件数**。这是跨两年异步提交记录的回顾性排序诊断，不代表同一日可部署的筛查政策。

## 区间和边界

主方向固定为 B−A。AP/ROC/Recall 正数表示 B 更高；Brier 负数表示 B 更低。输出逐指标、逐 block/model 的基本中心化 95% bootstrap 区间：`[2Δ̂−q*.975, 2Δ̂−q*.025]`，以及 bootstrap SE、偏差诊断、有效/无效重复数和有效率。

正式默认要求 **100% 重复对该指标有效**，否则不生成 CI。无事件时 AP/ROC/Recall 为 NaN；只有一种类别时 AP/ROC 为 NaN，Brier 仍可定义。不会把无事件重复删除后伪装成正常区间。区间是近似、逐项的，未作多重比较修正，稀疏非线性指标的有限样本覆盖率不由代码检查保证。

不确定性只反映**固定预测函数、固定确定性簇、固定已观测登记标签**下非案例簇抽样的变化，不包含重新训练/调参/校准、登记漏记、主体映射错误、未来经济环境或案例总体的不确定性。特征可获得性限定 domain，并未通过本权重自动作缺失响应校正。原样本也参与训练，因此这尤其不能表述成完整建模过程的重复抽样区间。

## 运行门禁

```powershell
python scripts/uncertainty_vintage.py --self-test

# 数据门禁通过、模型预测已冻结之后，由主代理明确启动：
python scripts/uncertainty_vintage.py --run --predictions results/models_test_predictions.parquet

# 固定A输入诊断须单独运行：
python scripts/uncertainty_vintage.py --run --analysis-mode frozen_A_inputs --predictions results/models_frozen_a_predictions.parquet
```

正式运行需要 `phase2_protocol.json` 的 `data_gate.training_allowed_now=true`，核对 sampling_frame 的锁定哈希、完整总体数量及预定测试时间块；seed 固定 20260921，默认 1000 次。输入只能读取 D 盘缓存，结果仅写 `results/uncertainty_<UTC时间>_*`，包括输入、脚本、协议和输出哈希。上述主预测文件名是示例，须传模型模块实际交付的文件。

## 已运行检查

`uncertainty_self_test.json` 明确标为 `SYNTHETIC_TEST_ONLY_NOT_RESEARCH_RESULTS`，不得写入论文主结果。12 项检查包括 sklearn 对照、整数权重展开、同分/行顺序不变、零 domain 簇、A=B 精确零区间、A/B 交换反号、census FPC 零方差、无事件 NaN、错误权重与行匹配拒绝、诊断模式隔离。

还使用完全已知的 N=8、n=4 有限总体：穷举 70 个 SRS 样本；每个样本穷举 64 个 n−1 次有放回抽样。验证 HT 总量估计的总体均值无偏、真实设计方差，以及 Rao–Wu 重复方差与常规 SRS 方差估计逐样本相等。含零贡献簇。这验证算法和权重恒等式，没有声称小样本 AP/Recall 的名义 95% 覆盖得到普遍保证。
