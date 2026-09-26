"""Write dataset-entry documentation and joint-filing audit; no label assignment."""
from pathlib import Path
import hashlib, json, stat
import pandas as pd
from universe_probe import BASE, RAW

def main():
    summary=json.loads((BASE/'results/universe_summary.json').read_text(encoding='utf-8'))
    data=pd.read_parquet(BASE/'datasets/universe_annual_filings_2010_2021.parquet')
    pd.read_csv(BASE/'datasets/universe_ciks_2010_2021.csv',dtype={'cik':'string'}).to_parquet(BASE/'datasets/universe_ciks_2010_2021.parquet',index=False)
    counts=pd.read_csv(BASE/'results/universe_annual_counts_2010_2021.csv')
    ncik=data.groupby('accession_number').cik.nunique()
    shared=ncik[ncik>1].index
    joint=data[data.accession_number.isin(shared)].copy()
    joint['n_ciks_same_accession']=joint.accession_number.map(ncik)
    joint.to_csv(BASE/'results/universe_joint_filing_records.csv',index=False)
    joint_summary={'shared_accessions':len(shared),'rows_in_shared_accessions':len(joint),'distinct_ciks_in_shared_accessions':joint.cik.nunique(),'max_ciks_one_accession':int(ncik.max()),'interpretation':'Multiple CIKs attached to the same accepted submission. This is an identity-audit flag, not proof that all such CIKs are one permanently identical economic group. The graph is historical and must not be used as an as-of feature without date restrictions.'}
    (BASE/'results/universe_joint_filing_summary.json').write_text(json.dumps(joint_summary,indent=2,ensure_ascii=False),encoding='utf-8')
    table='| 提交年 | 10-K | 10-KT | 申报记录 | 不同 CIK | 不同 accession |\n|---|---:|---:|---:|---:|---:|\n'
    for _,r in counts.iterrows():table+=f"| {int(r.year)} | {int(r['10-K']):,} | {int(r['10-KT']):,} | {int(r.annual_filings):,} | {int(r.distinct_ciks):,} | {int(r.distinct_accessions):,} |\n"
    report=f'''# 历史 SEC 风险集入口：实际取得与核验

日期：2026-09-21。状态：**历史申报抽样框可用；预测风险集及阴性标签尚未成立。**

本轮已取得公开镜像全部 20 个 Parquet 分片，合计 1,882,894,445 字节、24,943,448 行元数据。每片 SHA256 与 Hugging Face 仓库公布的 LFS 内容哈希一致。全源不是财报正文；本轮没有训练、没有建立当前 ticker 筛选、没有赋予任何企业阴性标签。[镜像及数据卡](https://huggingface.co/datasets/kapilrao/SEC_filings_1994_2024)

## 可以直接使用的产物

- `datasets/universe_annual_filings_2010_2021.parquet`：93,677 条原始 10-K / 10-KT 索引记录，15,631 个不同 CIK，90,338 个不同 accession；同名 CSV 供人工读取。
- `datasets/universe_ciks_2010_2021.parquet` 及同名 CSV：每个 CIK 一行，记录首次/末次年度申报日期、申报条数及覆盖年数。读取 CSV 必须 `dtype={{"cik":"string"}}`，保留 10 位前导零。
- `results/universe_annual_counts_2010_2021.csv`、`universe_annual_quarter_counts_2010_2021.csv`：年度及季度规模。
- `results/universe_sraf_count_crosscheck.csv`：独立学术镜像的计数核对。
- `results/universe_official_crosscheck.csv`：本机保存的官方 submissions 逐条核对。
- `results/universe_joint_filing_records.csv`：共同申报的 CIK/accession，供集团与法律主体关系审查。
- `results/universe_summary.json`、`universe_artifact_manifest.json`：数值摘要、来源及文件哈希。

这些文件是**按历史提交日期界定的申报候选框**，并不等于 15,631 家独立上市经营企业，也不等于已知存续/未破产企业。

## 来源链和真实访问

1. SEC 官方定义 master index 字段为公司名称、表单类型、CIK、提交日期和文件路径；CIK 不被回收重用，accession 的首十位则可能属于第三方提交代理。季度索引会纳入事后更正/删除。[SEC 官方说明](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
2. 取得的镜像是 `kapilrao/SEC_filings_1994_2024`。数据卡称来源为 SEC 季度 master 文件，并链接作者抓取仓库；实际每条记录还保留 master 标题、Last Data Received、SEC 来源地址。源声明共 24,943,448 行，本轮实数完全相同。[数据卡](https://huggingface.co/datasets/kapilrao/SEC_filings_1994_2024)；[作者仓库](https://github.com/arthrod/sec-edgar-bulker)
3. Notre Dame SRAF 提供独立 1993–2025 master 归档，明确取数日为 2026-03-18。本轮其 110 MB 10X 聚合、329 MB 完整索引 ZIP 及 188 MB Summary 的公开 Drive 下载均返回 quota exceeded，错误正文原样保留，未规避。其 130,264 字节年度×表单统计 XLSX 下载成功，作为外部覆盖核验。[SRAF 索引页](https://sraf.nd.edu/sec-edgar-data/master-index-data/)；[计数表原链接](https://docs.google.com/spreadsheets/d/1yblNDgSrouygy3RRNPLISa_67AU1HUUr/edit)
4. 本机 `csr_em_topic_study_20260823` 保存的是按原研究企业名单定向获取的 submissions，不是全市场 master。仅用于独立记录核对；没有拿它定义本轮市场总体。

所有 HTTP 请求未使用认证、未伪造联系人邮箱。HF 下载有一个分片发生 SSL 断流，一次正常重试成功，原失败 manifest 保留。新原件均使用 E 盘唯一文件名，下载后立即设只读；派生表和脚本在 D 盘。

## 覆盖与交叉核验

2010–2021 的 48 个季度均有年度申报记录。所有镜像记录的提交年/季度与 date_filed 一致；目标记录中 accession 解析缺失为 0，目录 CIK 与 CIK 列不一致为 0，CIK+表单+日期+文件路径完全重复为 0。

**跨来源计数：**12 年 × 4 表单（10-K、10-KT、10-K/A、10-KT/A），48 个单元与 SRAF 2026-03-18 归档计数全部完全一致。主抽样框只含 10-K 和 10-KT，修订表单仅用于覆盖核验。[SRAF](https://sraf.nd.edu/sec-edgar-data/master-index-data/)

**逐条官方核对：**本机既有 162 个 CIK 的 1,780 条 2010–2021 10-K/10-KT，按 CIK+accession 在新框中全部找到，提交日期与表单类型全部一致。该样本有原 CSR 研究的选择性，不能把 1,780/1,780 解释为整个镜像记录真实性的随机抽样误差上界。

{table}

年度计数是记录数；不同 accession 同样不是独立企业数。实际共同申报：{len(shared):,} 个 accession 关联多个 CIK，覆盖 {len(joint):,} 条记录、{joint.cik.nunique():,} 个 CIK，单个 accession 最多 {int(ncik.max())} 个 CIK。SEC 和 SRAF 均说明一个提交文件可能包含多个相关申报主体。[SRAF header 定义](https://sraf.nd.edu/sec-edgar-data/10-x-header-data/)

## 字段与执行边界

| 字段 | 解释与边界 |
|---|---|
| `cik` | 10 位字符串，索引中的申报主体。不能从 accession 前缀替代提取。 |
| `company_name` | 历史索引记载名称，只作身份审查；不保证集团母公司或股票上市身份。 |
| `form_type` | 主表严格只含 `10-K`、`10-KT`；不把 `10-K/A` 当新预测原点。 |
| `filing_date` | SEC 提交日，ISO 日期。是提交日，不是财年末，也不是法院破产日。 |
| `year`、`quarter` | 提交日所在日历年/季度。 |
| `filename`、`url` | SEC 原始完整申报路径；本轮没有下载正文。 |
| `accession_number` | 接受提交的标识；共同申报时一个 accession 可对应多个 CIK。 |
| `source_shard`、`source_master_last_data_received` | 镜像分片与原 master 头的版本线索；不是企业当时可见的财务变量。 |

主表不提供 reportDate、acceptanceDateTime、SIC、交易所历史、总资产、破产结果。这些需要再从官方 submissions / companyfacts / 原申报和 BRD 获取、对齐。已知 SEC 提交日期可支持按日的 as-of 设计；本轮不能支持任意盘中可见时间或声明完整原样历史档案。[SEC](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)

## 许可与限制

数据卡写的是 “Likely public domain as US government data”，没有明确给出本数据集的开放重分发许可证，因此不能把它改写为“已确认 CC0/可任意重分发”。当前可公开访问、可用于本地研究核验；正式发布应优先给代码、来源 URL、不可变哈希和衍生字段说明，是否重发整份镜像另行确认。SEC 官方说任何人可免费获取 EDGAR，但也存在第三方申报材料和访问政策边界。[数据卡](https://huggingface.co/datasets/kapilrao/SEC_filings_1994_2024)；[SEC 免费访问说明](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)

数据卡中的“CIK 在罕见情形可能复用”与 SEC 官方“不回收”说明冲突，本研究采用 SEC 官方定义。SRAF 和 SEC 均说明历史索引可能事后修正，因此本框是当前取得的回顾性元数据快照，而不是逐日冷冻的 2010 年原样数据库。

## 下一步入口与三项拒绝检查

可以在 15,631 个 CIK 的历史框中按预定概率抽取待核对企业，再拉官方 submissions 与 companyfacts；任何抽样概率和因特征缺失排除都必须单独保存。当前所有记录仍未带 outcome，不得将不在 BRD 的 CIK 自动编码为 0。

1. **主要风险：总体/标签不一致。**年度申报者可含非上市债务人、信托、集团子公司，BRD 有公开公司和规模门槛。拒绝条件是无法将研究总体和事件捕获范围对齐；需要定义目标总体、规模历史、集团映射和外部事件覆盖，而不是依靠本框自动消除。
2. **记录覆盖偏差。**现有全部分片哈希、48/48 年度表单计数一致、1,780/1,780 官方申报匹配显著加强可执行性；仍需在新增抽样企业中记录历史片遗漏与访问失败，不能只保留 API 成功企业。
3. **身份和时间设定错误。**共同申报不能算独立公司样本；10-KT 流量持续期不同，提交后修订的财务值不能倒灌。若无法建立 CIK/集团事件映射及逐 accession 的 as-of 财务快照，应缩小总体或停止该设计。

本轮判定：**历史元数据入口 GO；完整风险集与预测主线仍 CONDITIONAL。**当前工作解决了历史企业清单与提交日期的取得问题，没有证明阴性完整性或论文主线创新。
'''
    (BASE/'results/universe_feasibility.md').write_text(report,encoding='utf-8')
    raw_records=[]
    for p in sorted(RAW.iterdir()):
        if p.is_file():raw_records.append({'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'read_only':not bool(p.stat().st_mode & stat.S_IWRITE)})
    outputs=[]
    for sub in ['scripts','datasets','results']:
        for p in sorted((BASE/sub).glob('universe_*')):
            if p.is_file() and p.name!='universe_artifact_manifest.json':outputs.append({'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    artifact={'raw_files':raw_records,'derived_files':outputs,'all_new_originals_read_only':all(x['read_only'] for x in raw_records),'raw_total_bytes':sum(x['bytes'] for x in raw_records)}
    (BASE/'results/universe_artifact_manifest.json').write_text(json.dumps(artifact,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'joint':joint_summary,'raw_files':len(raw_records),'all_read_only':artifact['all_new_originals_read_only'],'report':str(BASE/'results/universe_feasibility.md')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
