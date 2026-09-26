# 投稿图表接口

`scripts/build_vintage_figures.py` 已实现，当前只通过内存辅助测试，尚未生成正式图。模型训练、队列修改和数据下载均不在此脚本中。

## 执行条件

- `phase2_protocol.json` 的 `data_gate.training_allowed_now` 必须为 `true`。
- `results/cohort_summary.json` 必须含 `status: FINAL_COHORT_FROZEN`、`source_collection_complete: true`、与输入文件一致的 `cohort_sha256` 和 `fact_table_sha256`。队列记录数、CIK 数、抽样簇数和正窗口数也会复核。
- 指定完成的主模型 run-id manifest（正式 `mode=run`、`status=completed`、12 个最终拟合），所有模型/不确定性输入的队列、协议、预测文件和抽样设计必须一致。
- 主分析及 frozen-A 分别需要完成的不确定性 summary 和 manifest；必须保留完整 1,000 个 noncase 抽样簇，包括零贡献簇。支持无可估计 CI 的显式标记，但不允许静默删除无效重抽样后画常规 CI。
- 主模型和 frozen-A 的 CSV 各应包含 6 组 A/B、共 12 个指标行。脚本核对各组 AP 和权重/正窗口分母。不读取 canonical latest 别名替代 run-id 文件。

## 命令

在项目 D 盘目录运行。以下大括号是需要替换的真实 run-id 文件名；它们不是示例数据。

```powershell
python -X utf8 scripts/build_vintage_figures.py `
  --model-manifest results/models_{model_run}_manifest.json `
  --main-metrics results/models_{model_run}_metrics.csv `
  --main-uncertainty-summary results/uncertainty_{main_run}_summary.csv `
  --main-uncertainty-manifest results/uncertainty_{main_run}_manifest.json `
  --frozen-metrics results/models_{model_run}_frozen_a_metrics.csv `
  --frozen-uncertainty-summary results/uncertainty_{frozen_run}_summary.csv `
  --frozen-uncertainty-manifest results/uncertainty_{frozen_run}_manifest.json
```

不加 `--run` 时仅验证输入，不写产物。验证完成后在同一命令加 `--run` 才生成图。可加 `--include-c` 使图 2 增加明确标为 per-tag hybrid diagnostic 的 C 版本；否则只画 A/B。默认原始 A/B/API 值，不自动应用任何后续单位更正敏感性。PNG 默认 900 dpi，只能提高。

默认输入为 `datasets/model_cohort.parquet`、`datasets/vintage_facts.parquet`、`results/cohort_summary.json`、`phase2_protocol.json`；可通过同名 CLI 参数显式替换，但仍须一致通过 manifest 门禁。

```powershell
python -X utf8 scripts/build_vintage_figures.py --self-test
```

此命令仅执行内存数值辅助检查，不写文件、不生成假图、不产生研究结果。

## 产物与口径

每次正式运行新建 `results/figures/{model_run}_figures_{UTC}/`，不覆盖旧图。三图均输出 PDF、SVG 和 900 dpi PNG，图题及完整图注独立保存为 `captions.md`。字体优先 Arial，然后 Times New Roman；选中字体写入 manifest。PNG 和矢量图生成后仍需独立目视检查，生成状态明确为 `GENERATED_REQUIRES_VISUAL_INSPECTION`。

- 图 1：年度加权 eligible filing landmarks；另一个面板绘制未加权 positive filing windows 与 distinct positive CIKs。无双 y 轴。不把重复正窗口或 CIK 数称为独立破产事件。
- 图 2：十个模型输入的加权数值改变比例。主要分母为该输入在 A 中有限可观测的权重和；另外导出全队列分母。缺失值保持同一 mask，变化定义为 `abs(A-B) > 1e-12 * max(1, abs(A), abs(B))`。逐项从事实表重构 A/B（可选 C）核验比率，不把原始财务项改变数与模型输入改变数混用。
- 图 3：主 6 对模型和 frozen-A 6 对输入诊断并列；共用横轴，以百分点显示 B−A AP 和 pointwise conditional 95% CI。CI 来自固定模型的 Rao–Wu–Yue SRS/FPC 评价设计不确定性，不含训练估计、模型选择、registry 漏记、案例总体或未来经济不确定性，不把三块视为独立宏观实验。

详细 CSV/JSON 位于 `results/descriptive_{model_run}_figures_{UTC}_*`：年度分母、特征变化分母、AP 森林图数据、事实重建核验和完整输入/输出哈希 manifest。原始计数、权重和与比例列分别命名。所有原件只读；脚本只写 D 盘获授权目录。
