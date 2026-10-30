import argparse
import csv
import json
import random
from pathlib import Path
import yaml
import optuna
from .harness_adapter import demo_task, official_task

ROOT = Path(__file__).resolve().parents[1]

def config_from_trial(trial, space):
    return {k:trial.suggest_categorical(k,v) for k,v in space.items()}

def evaluate(cfg, task_ids, runner, seed):
    outputs = [runner(cfg, t, seed) for t in task_ids]
    return {'pass_at_1':sum(x['passed'] for x in outputs)/len(outputs), 'usd':sum(x['usd'] for x in outputs), 'task_count':len(task_ids)}

def run(cfg):
    seed=cfg['seed']; rng=random.Random(seed)
    runner=demo_task if cfg['mode']=='demo' else official_task
    space=cfg['search_space']; n=cfg['search_trials']
    validation=list(range(cfg['validation_tasks']))
    test=list(range(10000,10000+cfg['test_tasks']))
    default={k:v[len(v)//2] for k,v in space.items()}
    Path(ROOT/'results').mkdir(exist_ok=True)
    log=[]; selected={}
    # For fairness, each search gets the same total number of task evaluations: n * validation_tasks.
    # Cost budgets are reported rather than constrained to be equal (benchmark asks cost curves).
    for name in ['default','random','bayesian','our_multifidelity']:
        best_cfg=default.copy(); best_score=-1; cumulative=0.; spent=0
        if name=='default':
            res=evaluate(default,validation,runner,seed)
            best_score=res['pass_at_1']; cumulative=res['usd'];spent=len(validation)
            log.append({'method':name,'trial':0,'tasks':len(validation),'cumulative_tasks':spent,'cumulative_usd':cumulative,'best_validation':best_score,'trial_validation':best_score,'config':json.dumps(default,sort_keys=True)})
        elif name in ['random','bayesian']:
            study=optuna.create_study(direction='maximize', sampler=(optuna.samplers.RandomSampler(seed=seed) if name=='random' else optuna.samplers.TPESampler(seed=seed,n_startup_trials=4)))
            for i in range(n):
                trial=study.ask(); c=config_from_trial(trial,space)
                res=evaluate(c,validation,runner,seed)
                # Performance objective selected before running; cost tracked separately.
                study.tell(trial,res['pass_at_1'])
                cumulative+=res['usd'];spent+=len(validation)
                if res['pass_at_1']>best_score:
                    best_score=res['pass_at_1'];best_cfg=c.copy()
                log.append({'method':name,'trial':i,'tasks':len(validation),'cumulative_tasks':spent,'cumulative_usd':round(cumulative,6),'best_validation':best_score,'trial_validation':res['pass_at_1'],'config':json.dumps(c,sort_keys=True)})
        else:
            # Developed approach: cost-aware two-stage screening.
            # First evaluate 2*n configs on 25% of validation tasks, then
            # evaluate the best candidates on full validation until budget exhausted.
            # Total evaluations <= n * validation_tasks. Held-out test NEVER used for selection.
            shortlist=[]
            batch=max(1,len(validation)//4)
            # stage 1 spends about half budget, stage 2 uses remainder
            for i in range(2*n):
                c={k:rng.choice(v) for k,v in space.items()}
                task_ids=validation[:batch]
                if spent+len(task_ids)>n*len(validation): break
                res=evaluate(c,task_ids,runner,seed);spent+=len(task_ids);cumulative+=res['usd']
                # Criterion: empirical success minus small price penalty
                score=res['pass_at_1']-.25*(res['usd']/len(task_ids))
                shortlist.append((score,c))
                log.append({'method':name,'trial':i,'tasks':len(task_ids),'cumulative_tasks':spent,'cumulative_usd':round(cumulative,6),'best_validation':'','trial_validation':res['pass_at_1'],'config':json.dumps(c,sort_keys=True)})
            shortlist.sort(key=lambda x:x[0],reverse=True)
            for j,(_,c) in enumerate(shortlist):
                if spent+len(validation)>n*len(validation):break
                res=evaluate(c,validation,runner,seed);spent+=len(validation);cumulative+=res['usd']
                if res['pass_at_1']>best_score:
                    best_score=res['pass_at_1'];best_cfg=c.copy()
                log.append({'method':name,'trial':2*n+j,'tasks':len(validation),'cumulative_tasks':spent,'cumulative_usd':round(cumulative,6),'best_validation':best_score,'trial_validation':res['pass_at_1'],'config':json.dumps(c,sort_keys=True)})
            if best_score<0:
                raise ValueError('Not enough evaluation budget for full-validation selection')
        # Test evaluation only after all search decisions finalized
        test_result=evaluate(best_cfg,test,runner,seed)
        selected[name]={'config':best_cfg,'best_validation_pass_at_1':best_score,'test_pass_at_1':test_result['pass_at_1'],'test_usd':test_result['usd'],'search_usd':round(cumulative,6),'search_task_evaluations':spent}
    out=ROOT/'results';
    with (out/'trials.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=log[0].keys());writer.writeheader();writer.writerows(log)
    (out/'summary.json').write_text(json.dumps({'mode':cfg['mode'],'WARNING':'SYNTHETIC DATA — NOT COURSE EVIDENCE' if cfg['mode']=='demo' else 'OFFICIAL RUNNER RESULTS; AUDIT BEFORE USE','methods':selected},indent=2),encoding='utf-8')
    return log,selected

def plot(log, demo):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(8,5))
    for name in ['random','bayesian','our_multifidelity']:
        pts=[x for x in log if x['method']==name and x['best_validation']!='']
        ax.step([x['cumulative_usd'] for x in pts],[x['best_validation'] for x in pts],where='post',label=name)
    ax.set(xlabel='Cumulative search cost (USD)',ylabel='Best full-validation pass@1',title='DEMO — SYNTHETIC' if demo else 'Incumbent curves')
    ax.legend();fig.tight_layout();fig.savefig(ROOT/'results'/'incumbent.png',dpi=170);plt.close(fig)

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',default='configs/config.yaml');args=p.parse_args()
    cfg=yaml.safe_load((ROOT/args.config).read_text(encoding='utf-8'))
    if cfg['mode'] not in ['demo','real']:raise ValueError('mode must be demo or real')
    log,selected=run(cfg)
    plot(log,cfg['mode']=='demo')
    print('MODE:',cfg['mode']);print('Results saved in results/');
    for name,s in selected.items():print(name,'validation=',round(s['best_validation_pass_at_1'],3),'test=',round(s['test_pass_at_1'],3),'search USD=',s['search_usd'])
    if cfg['mode']=='demo': print('WARNING: Synthetic demo results only. NOT official benchmark evidence.')
if __name__=='__main__':main()
