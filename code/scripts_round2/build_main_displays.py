"""Assemble main tables and figures from frozen round-two numerical outputs."""
from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

R=Path(__file__).resolve().parents[1]; BASE=R.parent; OLD=BASE/'revision_20260922'
OUT=R/'manuscript'; OUT.mkdir(exist_ok=True); FIG=R/'figures'; FIG.mkdir(exist_ok=True)
E=R/'results/evaluation_diagnostics'; D=R/'results/development_controls'
sources={}
def read(p):
    sources[str(p.relative_to(BASE))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return pd.read_csv(p)
def table(head,rows):
    return '\n'.join(['| '+' | '.join(head)+' |','| '+' | '.join(['---']*len(head))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def block(b):return b.replace('_','–')
tables={}
flow=read(BASE/'results/cohort_flow.csv')
print('flow',flow.columns.tolist())
tables['flow']=table(['Sequential eligibility stage','Windows','CIKs','Positive windows'],[[x.stage,f'{x.rows:,}',f'{x.ciks:,}',str(x.positive_windows)] for x in flow.itertuples()])
four=read(E/'four_cell_decomposition_unrounded.csv')
g=four.query("model=='LGBM' and metric=='average_precision'")
tables['four_cells']=table(['Test block','AA','AB','BA','BB','I','F','J','Total'],[
    [block(x.block)]+[f'{getattr(x,c)*100:.3f}' for c in ['AA','AB','BA','BB','input_AB_minus_AA','fit_BA_minus_AA','interaction','total_BB_minus_AA']] for x in g.itertuples()])
ex=read(E/'version_exposure_summary.csv')
rows=[]
for (dom,label),s in ex.loc[ex.domain!='full_cohort'].groupby(['domain','label'],sort=True):
    cells=[]
    for group in ['no_later_bundle','later_without_raw_change','later_with_raw_change']:
        z=s.loc[s.exposure_group==group].iloc[0];cells.append(f'{z.raw_n:,} ({z.within_label_weighted_fraction*100:.1f}%)')
    rows.append([block(dom),str(label)]+cells)
tables['exposure']=table(['Test block','Event','No later bundle','Later unchanged','Later changed'],rows)
fit=read(R/'results/fit_date/fit_date_comparisons.csv');cov=read(R/'results/fit_date/fit_date_coverage.csv')
rows=[]
for x in fit.query("model=='LGBM' and metric=='average_precision'").itertuples():
    z=cov.loc[cov.block==x.block].iloc[0]
    rows.append([block(x.block)]+[f'{getattr(x,c)*100:.3f}' for c in ['original_A_train_A_score','fit_date_train_A_score','latest_B_train_A_score']]+[f'{z.latest_not_available_at_fit_n} / {z.n_train:,}',f'{z.latest_not_available_at_fit_weighted_percent:.3f}%'])
tables['fitdate']=table(['Test block','A fit','As of fit date','Latest B fit','Late B / training N','Late B weight'],rows)
cpi=read(D/'CPI_domain_diagonal.csv').query("model=='LGBM'")
rows=[]
labels={'full_train_full_test':'Full / Full','full_train_size_test':'Full / Size','size_train_size_test':'Size / Size'}
for b in sorted(cpi.block.unique()):
    for exp in labels:
        s=cpi.loc[(cpi.block==b)&(cpi.experiment==exp)];a=s.loc[s.train_version=='A'].iloc[0];v=s.loc[s.train_version=='B'].iloc[0]
        rows.append([block(b),labels[exp],f'{int(a.n)} / {int(a.positive_windows)}',f'{a.weighted_prevalence*100:.3f}',f'{a.average_precision*100:.3f}',f'{v.average_precision*100:.3f}',f'{(v.average_precision-a.average_precision)*100:+.3f}'])
tables['size']=table(['Test block','Develop / Evaluate','N / +','Event %','AA %','BB %','Δ pp'],rows)
scale=read(R/'results/scale_only/four_cell_differences.csv')
disputed=read(OLD/'results/corrected_models_v2/four_cell_differences.csv')
rows=[]
for b in sorted(g.block.unique()):
    orig=g.loc[g.block==b].iloc[0]
    for name,s,exper in [('Unadjusted',four,None),('Scale supported',scale,'source_corrected_tuned'),('Scale + disputed signs',disputed,'source_corrected_tuned')]:
        if exper is None:z=orig;total=z.total_BB_minus_AA
        else:z=s.loc[(s.block==b)&(s.model=='LGBM')&(s.metric=='average_precision')&(s.experiment==exper)].iloc[0];total=z.total_refit_difference
        rows.append([block(b),name,f'{z.AA*100:.3f}',f'{z.BB*100:.3f}',f'{total*100:+.3f}'])
tables['source']=table(['Test block','Input scenario','AA %','BB %','Δ pp'],rows)
(OUT/'generated_tables.json').write_text(json.dumps(tables,indent=2),encoding='utf-8')

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':12,'axes.labelsize':11,'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
colors=['#24567A','#B45C30','#57927B']
def save(fig,name):
    for ext in ['png','pdf','svg']:fig.savefig(FIG/f'{name}.{ext}',dpi=900,bbox_inches='tight',facecolor='white')
    plt.close(fig)

fig,ax=plt.subplots(figsize=(9,5.6));ax.set(xlim=(0,10),ylim=(0,6));ax.axis('off')
def box(x,y,w,h,text,col):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.12',fc=col,ec='#8194A0',lw=.8));ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=11,linespacing=1.5)
box(.15,4.65,4.3,1.1,'Historical training row\nOutcome mature before model fit date T','#EAF0F5')
box(5.25,4.65,4.45,1.1,'Test row at prediction origin o\nOriginal filing inputs A; outcome follows','#EAF0F5')
box(.15,3,4.3,1.15,'Training clock\nUse original A, latest B, or disclosure < T','#FFFFFF')
box(5.25,3,4.45,1.15,'Scoring clock\nA is origin associated; B can be later','#FFFFFF')
for x in [2.3,7.5]:ax.annotate('',xy=(x,4.16),xytext=(x,4.63),arrowprops={'arrowstyle':'->','lw':1.5})
ax.text(.15,2.35,'Matched rows · labels · design weights · initial missingness',fontsize=12,fontweight='bold')
box(.15,.2,3.1,1.55,'Fit A → score A: AA\nFit A → score B: AB','#EEF4F8')
box(3.5,.2,3.1,1.55,'Fit B → score A: BA\nFit B → score B: BB','#F9F0E9')
box(6.85,.2,2.85,1.55,'Input: AB − AA\nFit: BA − AA\nInteraction: residual','#EDF4F0')
save(fig,'figure1_protocol')

raw=pd.read_parquet(E/'raw_component_change_magnitudes.parquet')
print('raw columns',raw.columns.tolist())
print('raw sample',raw.head(1).to_dict('records'))
mag=read(E/'raw_component_magnitude_summary.csv');sign=read(E/'raw_component_sign_categories.csv')
# Prefer explicit agent summaries, with separate units for change frequency and size.
features=list(mag.feature.drop_duplicates());names={'assets':'Assets','liabilities':'Liabilities','equity':'Equity','cash':'Cash','net_income':'Net income','revenue':'Revenue','operating_income':'Operating income','operating_cash_flow':'Operating cash flow','retained_earnings':'Retained earnings','current_assets':'Current assets','current_liabilities':'Current liabilities'}
print('features',features)
names['operating_cash']='Operating cash flow'
fig,axes=plt.subplots(1,3,figsize=(10.2,5.6),sharey=True,gridspec_kw={'width_ratios':[1,1.35,1]})
for j,f in enumerate(features):
    s=raw.loc[raw.feature==f];changed=s.changed_tolerance
    axes[0].barh(j,100*s.loc[changed,'sample_weight'].sum()/s.sample_weight.sum(),color=colors[0],height=.6)
    v=s.loc[changed & (s.sign_category=='same_sign_nonzero'),'log10_absolute_ratio'].dropna()
    if len(v):
        axes[1].scatter(v,np.full(len(v),j),s=10,c=colors[1],alpha=.32)
    flip=100*s.loc[s.sign_category=='sign_flip','sample_weight'].sum()/s.sample_weight.sum()
    zero=100*s.loc[s.sign_category.isin(['zero_to_nonzero','nonzero_to_zero']),'sample_weight'].sum()/s.sample_weight.sum()
    axes[2].barh(j,flip,color=colors[1],height=.6)
    axes[2].barh(j,zero,left=flip,color=colors[2],height=.6)
axes[0].set_yticks(range(len(features)),[names.get(f,f) for f in features]);axes[0].invert_yaxis()
axes[0].set_title('A  Any raw change');axes[0].set_xlabel('Weighted % of observed pairs')
axes[1].set_title('B  Changed same-sign pairs');axes[1].set_xlabel('log₁₀ |B / A|');axes[1].axvline(0,color='#555',lw=.8)
axes[2].set_title('C  Sign and zero transitions');axes[2].set_xlabel('Weighted % of observed pairs')
axes[2].plot([],[],color=colors[1],lw=7,label='Sign flip');axes[2].plot([],[],color=colors[2],lw=7,label='To / from zero');axes[2].legend(loc='lower right',fontsize=8,frameon=False)
for ax in axes:
    ax.grid(axis='x',alpha=.15);ax.tick_params(labelsize=12);ax.xaxis.label.set_size(12)
fig.subplots_adjust(wspace=.22);save(fig,'figure2_changes')

# Figure 3 draws all prespecified ordinary deletion repeats, not a confidence interval.
de=read(D/'deletion_AP_changes.csv');comp=read(D/'matched_deletion_comparison.csv')
groups=['positive_unchanged','changed_negative','other_unchanged_negative'];gnames=['Unchanged positive','Changed negatives','Other unchanged\nnegatives']
fig,axes=plt.subplots(1,3,figsize=(9.8,4.5),sharex=True,sharey=True)
for ax,b in zip(axes,sorted(comp.block.unique())):
    for j,group in enumerate(groups):
        z=comp.loc[(comp.block==b)&(comp.model=='LGBM')&(comp.group==group)].iloc[0]
        mask=de.experiment.str.startswith('ordinary_matched_'+group+'_')
        vals=de.loc[mask&(de.block==b)&(de.model=='LGBM'),'total_refit_difference_minus_full'].to_numpy()*100
        if len(vals):ax.scatter(vals,np.full(len(vals),j)+np.linspace(-.14,.14,len(vals)),s=18,c='#8898A4',alpha=.8)
        if z.ordinary_repetitions:ax.scatter([z.transition_delta_change*100],[j],marker='D',s=65,c=colors[1],zorder=4)
        else:ax.text(0,j,'No mature\ntarget',ha='left',va='center',fontsize=11)
    ax.axvline(0,color='#555555',lw=.8);ax.set_title(block(b),fontsize=14);ax.set_yticks(range(3),gnames);ax.tick_params(labelsize=13);ax.grid(axis='x',alpha=.15)
axes[0].invert_yaxis();fig.supxlabel('Change in version contrast (AP percentage points)',fontsize=14);fig.subplots_adjust(wspace=.12,bottom=.17);save(fig,'figure3_deletion')

rep=read(E/'perturbation_modes_all_replicates.csv').query("model=='LGBM' and metric=='average_precision'")
modes=['development_only','evaluation_only','joint'];mlab=['Development','Evaluation','Joint']
fig,axes=plt.subplots(1,3,figsize=(9.8,3.6),sharex=True,sharey=True)
for ax,b in zip(axes,sorted(rep.block.unique())):
    data=[rep.loc[(rep.block==b)&(rep['mode']==m),'delta'].to_numpy()*100 for m in modes]
    bp=ax.boxplot(data,orientation='horizontal',positions=[1,2,3],whis=(5,95),showfliers=False,patch_artist=True,widths=.48)
    for patch,c in zip(bp['boxes'],colors):patch.set_facecolor(c);patch.set_alpha(.7)
    ax.axvline(0,color='#555555',lw=.8);ax.set_yticks([1,2,3],mlab);ax.set_title(block(b),fontsize=14);ax.tick_params(labelsize=13);ax.grid(axis='x',alpha=.15)
axes[0].invert_yaxis();fig.supxlabel('BB − AA (AP percentage points)',fontsize=14);fig.subplots_adjust(wspace=.1,bottom=.17);save(fig,'figure4_perturbations')
(OUT/'display_sources.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
print('tables and figures 1,3,4 complete')
