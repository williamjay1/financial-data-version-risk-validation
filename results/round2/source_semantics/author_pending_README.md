# 作者待确认接口

`author_pending_sign_confirmation.csv`有四条精确来源事实。默认决策为保留API值，符号替换只保留争议敏感性。CSV中未填写的作者姓名、日期、选择及依据均是真正空白；不代表复核已完成。

建议每行按以下链核验：官方原文件→当次实例文件和schemaRef→目标us-gaap概念→entity/context和维度→instant/duration期间→USD unit及scale/decimals→presentation linkbase与label role→显示报表的经济行含义。若采用显示值替换，明确只达到display-supported，不升级原实例认证。

可选结论：

1. KEEP_API：保留API并说明理由。
2. DISPLAY_SUPPORTED_REPLACEMENT_ONLY：用于显示报表支持的敏感性，原XBRL仍未知。
3. ORIGINAL_INSTANCE_CERTIFIED_REPLACEMENT：仅在实际取到并认证完整实例链后使用；提供文件与具体定位。
4. UNRESOLVED：保留争议，不在确证纠正集合中。

22倍率键另在 `scale_supported_corrections.csv`，已获原财务报表单位标题/年份金额支持，但同样没有原始XBRL上下文认证或人的签核。无需等签核才运行目前已授权的计算；计算不能替代认证。

对应模型影响与阶段见 `source_keys_to_components_features_stages.csv`、`six_feature_cells_stage_trace.csv`、`scale22_prediction_effect_summary.csv`。来源状态和模型影响必须分别判断；不得因为预测指标好坏决定符号接受与否。
