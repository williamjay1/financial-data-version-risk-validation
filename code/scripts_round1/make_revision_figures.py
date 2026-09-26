"""Regenerate the revision's scientific figures from stored results, without fitting."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

REV=Path(__file__).resolve().parents[1]; ROOT=REV.parent
OUT=REV/'figures'; OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,
 'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none','axes.titleweight':'bold'})
COL=['#156082','#C46527','#4B8063']
BLOCKS=['2016_2017','2018_2019','2020_2021']
def save(fig,name):
 for ext in ('pdf','svg','png'):fig.savefig(OUT/(name+'.'+ext),dpi=900,bbox_inches='tight',facecolor='white')
 fig.savefig(OUT/(name+'_preview.png'),dpi=140,bbox_inches='tight',facecolor='white');plt.close(fig)
def wq(x,w,q):
 idx=np.argsort(x,kind='stable');x=np.asarray(x)[idx];w=np.asarray(w)[idx]
 return np.interp(q,np.cumsum(w)/sum(w),x)

def protocol():
 fig,ax=plt.subplots(figsize=(7.2,4.8));ax.axis('off');ax.set_xlim(0,1);ax.set_ylim(0,1)
 ax.text(0,.98,'a  One filing landmark',weight='bold',va='top')
 ax.annotate('',xy=(.98,.77),xytext=(.04,.77),arrowprops={'arrowstyle':'->','color':'#555555'})
 points=[(.08,'Fiscal\nperiod end'),(.25,'Original\nfiling'),(.40,'Origin\n(next day)'),(.73,'365-day\noutcome ends'),(.91,'+90-day\nmaturity buffer')]
 for x,l in points:ax.plot([x,x],[.75,.79],c='#555555');ax.text(x,.83,l,ha='center',va='bottom',fontsize=8)
 ax.annotate('Later accession B\nmay follow the event',xy=(.65,.77),xytext=(.57,.63),ha='center',fontsize=8,arrowprops={'arrowstyle':'->','color':COL[1]})
 ax.text(.03,.52,'b  Train-only preprocessing and temporal development',weight='bold')
 for x,width,txt in [(.03,.29,'Mature training outcomes'),(.36,.23,'Historical validation'),(.63,.34,'Chronological test block')]:
  ax.add_patch(FancyBboxPatch((x,.40),width,.08,boxstyle='round,pad=.007',facecolor='#F0F3F5',edgecolor='#90999E'))
  ax.text(x+width/2,.44,txt,ha='center',va='center',fontsize=8)
 ax.text(.03,.31,'c  Cross fitted pipeline and scoring inputs',weight='bold')
 for x,t in [(.34,'Score A'),(.68,'Score B')]:ax.text(x,.245,t,ha='center',weight='bold')
 for y,label,vals in [(.17,'Fit A',['AA: baseline','AB: input replacement']),(.075,'Fit B',['BA: fit replacement','BB: complete B pipeline'])]:
  ax.text(.03,y,label,va='center',weight='bold')
  for x,t in zip([.34,.68],vals):ax.text(x,y,t,ha='center',va='center',bbox={'facecolor':'#EDF3F6','edgecolor':'#A5B4BC','pad':7},fontsize=8)
 save(fig,'figure1_protocol')

def inputs():
 df=pd.read_parquet(ROOT/'datasets/model_cohort.parquet')
 f=pd.read_parquet(ROOT/'datasets/vintage_facts.parquet').merge(df[['cik','accession','sample_weight']],left_on=['cik','original_accession'],right_on=['cik','accession'],validate='many_to_one')
 rows=[]
 for name,g in f.groupby('feature',sort=False):
  good=g.A.notna()&g.B.notna();g=g[good];a=g.A.to_numpy(float);b=g.B.to_numpy(float);w=g.sample_weight.to_numpy()
  change=np.abs(a-b)>1e-12*np.maximum(1,np.maximum(np.abs(a),np.abs(b)))
  magnitude=np.abs(b-a)/np.maximum(1,np.maximum(np.abs(a),np.abs(b)))
  rows.append({'feature':name,'weighted_changed_percent':100*np.sum(w*change)/sum(w),'n_observed':len(g),
   'changed_q50':wq(magnitude[change],w[change],.5),'changed_q95':wq(magnitude[change],w[change],.95)})
 stats=pd.DataFrame(rows).sort_values('weighted_changed_percent');stats.to_csv(OUT/'input_change_statistics.csv',index=False)
 names={'assets':'Assets','liabilities':'Liabilities','equity':'Equity','cash':'Cash','net_income':'Net income','revenue':'Revenue','operating_income':'Operating income','operating_cash':'Operating cash flow','retained_earnings':'Retained earnings','current_assets':'Current assets','current_liabilities':'Current liabilities'}
 fig,axs=plt.subplots(1,2,figsize=(7.3,4.8),gridspec_kw={'width_ratios':[1.1,1]},layout='constrained')
 y=np.arange(len(stats));axs[0].barh(y,stats.weighted_changed_percent,color=COL[0]);axs[0].set_yticks(y,[names.get(v,v.replace('_',' ').title()) for v in stats.feature]);axs[0].set_xlabel('Changed (% of observed weighted mass)');axs[0].set_title('a  Frequency',loc='left')
 axs[1].hlines(y,stats.changed_q50,stats.changed_q95,color=COL[1],lw=2);axs[1].scatter(stats.changed_q50,y,color=COL[1],s=20,label='Median');axs[1].scatter(stats.changed_q95,y,facecolors='white',edgecolors=COL[1],s=20,label='95th percentile');axs[1].set_yticks(y,[]);axs[1].set_xscale('log');axs[1].set_xlabel('Relative magnitude among changed facts');axs[1].set_title('b  Magnitude (log scale)',loc='left');axs[1].legend(loc='upper left',bbox_to_anchor=(0,-.12),ncol=2,fontsize=8)
 for a in axs:a.grid(axis='x',alpha=.2);a.set_axisbelow(True)
 save(fig,'figure2_input_changes')

def model_contrasts():
 d=pd.read_csv(REV/'results/models/four_cell_differences.csv');d=d[d.metric.eq('average_precision')]
 configs=[('original_four_cell','LGBM','Tuned LightGBM'),('fixed_full','LGBM','Fixed LightGBM'),('rolling_three_year','LGBM','Rolling LightGBM'),('fixed_spline_rf','SPLINE_LR','Spline logistic'),('fixed_spline_rf','RF','Random forest')]
 fig,axs=plt.subplots(1,2,figsize=(7.4,3.7),gridspec_kw={'width_ratios':[1.65,1]},layout='constrained')
 for j,b in enumerate(BLOCKS):
  for k,(e,m,lab) in enumerate(configs):
   q=d[(d.experiment==e)&(d.model==m)&(d.block==b)]
   if len(q):axs[0].scatter(100*q.total_refit_difference,k+(j-1)*.19,c=COL[j],s=32,marker=['o','s','^'][j],label=b.replace('_','–') if k==0 else None)
  for k,e in enumerate(['original_four_cell','fixed_full','rolling_three_year']):
   q=d[(d.experiment==e)&(d.model=='LR')&(d.block==b)]
   if len(q):axs[1].scatter(100*q.total_refit_difference,k+(j-1)*.19,c=COL[j],s=32,marker=['o','s','^'][j])
 axs[0].set_yticks(range(len(configs)),[x[2] for x in configs]);axs[1].set_yticks(range(3),['Tuned LR','Fixed LR','Rolling LR']);axs[0].set_title('a  Nonlinear learners',loc='left');axs[1].set_title('b  Logistic regression: enlarged scale',loc='left',fontsize=9)
 for a in axs:a.axvline(0,c='#777777',lw=.8);a.invert_yaxis();a.set_xlabel('BB − AA AP (percentage points)');a.grid(axis='x',alpha=.2)
 axs[0].legend(loc='lower left',fontsize=7);save(fig,'figure3_model_contrasts')

def transitions():
 d=pd.read_csv(REV/'results/models/four_cell_differences.csv');d=d[d.metric.eq('average_precision')&d.model.eq('LGBM')]
 configs=[('original_four_cell','Original tuned'),('transition_test_only','Test exclusion only'),('transition_development_tuned','Development exclusion, tuned'),('fixed_full','Full sample, fixed parameters'),('transition_development_fixed','Development exclusion, fixed')]
 fig,ax=plt.subplots(figsize=(7.2,3.7),layout='constrained')
 for j,b in enumerate(BLOCKS):
  vals=[float(d[(d.experiment==e)&(d.block==b)].total_refit_difference.iloc[0])*100 for e,_ in configs]
  y=np.arange(len(configs))+(j-1)*.2
  ax.scatter(vals,y,color=COL[j],s=34,marker=['o','s','^'][j],label=b.replace('_','–'))
  for x,yy in zip(vals,y):ax.annotate(f'{x:+.2f}',(x,yy),xytext=(5,0),textcoords='offset points',va='center',fontsize=7,color=COL[j])
 ax.axvline(0,c='#777777',lw=.8);ax.set_xlim(-5.6,8.1);ax.set_yticks(range(len(configs)),[x[1] for x in configs]);ax.invert_yaxis();ax.set_xlabel('LightGBM BB − AA AP (percentage points)');ax.grid(axis='x',alpha=.2);ax.legend(loc='upper left',bbox_to_anchor=(0,-.15),ncol=3,fontsize=8)
 save(fig,'figure4_transition_decomposition')

def score_propagation():
 d=pd.read_csv(REV/'results/uncertainty/score_rank_group_summary.csv')
 d=d[(d.model=='LGBM')&(d.label_group=='all')&(d.input_group!='all')]
 fig,axs=plt.subplots(1,2,figsize=(7.2,3.6),layout='constrained')
 groups=[('refit_vintages','changed','Refit / changed'),('refit_vintages','unchanged','Refit / unchanged'),('frozen_A_inputs','changed','Frozen A / changed'),('frozen_A_inputs','unchanged','Frozen A / unchanged')]
 # Stored groups are explicit and checked rather than silently dropping rows.
 actual=set(d.input_group);aliases={k:next((a for a in actual if a==k or a in ['input_'+k,'inputs_'+k]),k) for k in ['changed','unchanged']}
 for j,b in enumerate(BLOCKS):
  for k,(mode,g,lab) in enumerate(groups):
   s=d[(d.block==b)&(d.analysis_mode==mode)&(d.input_group==aliases[g])]
   if len(s)!=1:raise ValueError((mode,g,b,actual))
   s=s.iloc[0];y=k+(j-1)*.2
   for a,p in zip(axs,['absolute_score_difference','absolute_weighted_midrank_difference']):
    lo=s[p+'_weighted_q50'];hi=s[p+'_weighted_q95'];a.plot([lo,hi],[y,y],color=COL[j],lw=1.8);a.scatter(lo,y,color=COL[j],s=16,label=b.replace('_','–') if k==0 and a is axs[0] else None)
 for a in axs:a.set_yticks(range(4),[x[2] for x in groups]);a.invert_yaxis();a.grid(axis='x',alpha=.2)
 axs[0].set_title('a  Absolute probability change',loc='left');axs[1].set_title('b  Absolute weighted-rank change',loc='left');axs[0].set_xlabel('Probability units; median to 95th percentile');axs[1].set_xlabel('Fraction of weighted test mass');axs[0].legend(fontsize=7,loc='lower right');save(fig,'figure5_score_propagation')

def refitting():
 d=pd.read_csv(REV/'results/uncertainty/full_pipeline_paired_replicates.csv');d=d[d.metric.eq('average_precision')]
 summary=pd.read_csv(REV/'results/uncertainty/full_pipeline_distribution_summary.csv')
 fig,axs=plt.subplots(1,2,figsize=(7.2,3.4),layout='constrained');rng=np.random.default_rng(20260922)
 for ax,model in zip(axs,['LGBM','LR']):
  for j,b in enumerate(BLOCKS):
   z=d[(d.model==model)&(d.block==b)];assert len(z)==200 and z.valid.all()
   x=z.difference_B_minus_A.to_numpy()*100;y=j+rng.uniform(-.2,.2,len(x))
   ax.scatter(x,y,s=7,color=COL[j],alpha=.4,linewidths=0)
   s=summary[(summary.metric=='average_precision')&(summary.model==model)&(summary.block==b)].iloc[0]
   ax.plot([100*s.q5_0,100*s.q95_0],[j,j],color=COL[j],lw=2)
   ax.scatter(100*s.original_difference_B_minus_A,j,marker='D',s=25,facecolors='white',edgecolors='black',zorder=4)
  ax.axvline(0,c='#555555',lw=.8);ax.set_yticks(range(3),[block.replace('_','–') for block in BLOCKS]);ax.invert_yaxis();ax.set_xlabel('BB − AA AP (percentage points)');ax.grid(axis='x',alpha=.2)
 axs[0].set_title('a  LightGBM',loc='left');axs[1].set_title('b  Logistic regression: separate scale',loc='left',fontsize=9)
 save(fig,'figure6_refitting')

if __name__=='__main__':
 protocol();inputs();model_contrasts();transitions();score_propagation();refitting()
 print(json.dumps({'figures':sorted(p.name for p in OUT.glob('*.pdf'))}))
