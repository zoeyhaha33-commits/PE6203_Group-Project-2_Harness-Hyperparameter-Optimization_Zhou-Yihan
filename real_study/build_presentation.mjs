import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';

const runtime = 'C:/Users/happy/.cache/codex-runtimes/codex-primary-runtime/dependencies';
process.env.RUNTIME_NODE_MODULES = runtime + '/node/node_modules';
const {Presentation, PresentationFile} = await import(pathToFileURL(runtime + '/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs').href);
const skill = 'C:/Users/happy/.codex/plugins/cache/openai-primary-runtime/presentations/26.1025.11240/skills/presentations';
const {finalizePresentation, applyPresentationChartFont} = await import(pathToFileURL(skill+'/container_tools/artifact_tool_utils.mjs').href);
const root = path.dirname(fileURLToPath(import.meta.url));
const work = path.join(root,'presentation');
const build = path.join(work,'.build');
const out = path.join(work,'output');
await fs.mkdir(build,{recursive:true}); await fs.mkdir(out,{recursive:true});
const summary = JSON.parse(await fs.readFile(path.join(root,'final_test_summary.json'),'utf8'));
const sensitivity = JSON.parse(await fs.readFile(path.join(root,'parameter_sensitivity.json'),'utf8'));
const deck = Presentation.create({slideSize:{width:1280,height:720}});
const C = {navy:'#17324D',teal:'#087F8C',gray:'#526174',light:'#EDF2F6',blue:'#3978B4',orange:'#C77822',green:'#397B58',ink:'#202B38'};
const font = 'Arial';
const timings=[30,55,45,70,45,65,60,55,55,65,35,20];
const scripts=[];

function text(slide,content,x,y,w,h,size=26,color=C.ink,bold=false){
  const s=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  s.text=content;
  s.text.style={fontFamily:font,typeface:font,fontSize:size,color,bold};
  return s;
}
function slide(title,notes,source='final_test_summary.json'){
  const s=deck.slides.add(); s.background.fill='#FFFFFF';
  text(s,title,64,40,1152,82,42,C.navy,true);
  const n=deck.slides.items.length;
  text(s,'PE6203  |  Harness hyperparameter optimization',64,676,1020,22,15,C.gray);
  text(s,String(n).padStart(2,'0'),1150,676,64,22,15,C.gray);
  const duration=timings[n-1];
  s.speakerNotes.text=`${duration ? 'Target duration: '+duration+' seconds.':'Q&A / backup slide; outside the 10-minute talk.'}\n\n${notes}\n\nProject evidence: real_study/${source}. All values are project-local experimental observations.`;
  scripts.push({slide:n,title,seconds:duration??0,notes});
  return s;
}
function table(s,headers,rows,{x=64,y=154,w=1152,h=330,widths=null,size=25}={}){
  const all=[headers,...rows];
  const t=s.tables.add({rows:all.length,columns:headers.length,left:x,top:y,width:w,height:h,values:all,
    ...(widths?{columnWidths:widths}: {})});
  for(let r=0;r<all.length;r++)for(let c=0;c<headers.length;c++){
    const cell=t.getCell(r,c);
    cell.fill=r===0?C.navy:(r%2?'#F0F4F7':'#FFFFFF');
    cell.text.style={fontFamily:font,typeface:font,fontSize:size,color:r===0?'#FFFFFF':C.ink,bold:r===0};
  }
  t.borders.assign({fill:'#DCE4EB',width:0.7,style:'solid'});
  return t;
}
function lines(s,items,y=168,size=29,gap=106){
  items.forEach((item,i)=>text(s,item,70,y+i*gap,1138,gap-18,size));
}
function takeaway(s,t,y=604){text(s,t,64,y,1152,57,25,C.teal,true);}

// 1 — Minimal typographic cover.
{
 const s=slide('Harness Hyperparameter Optimization',
 'We study whether tuning a small, supported configuration surface can improve a fixed coding-agent harness. We compare three standard references with our two-stage multi-fidelity method. This is a small empirical study: no held-out success improvement is observed. Our emphasis is on the search design, measured cost, and what the failures teach us. The presentation takes ten minutes, followed by five minutes of questions.','report_draft/PE6203_Harness_HPO_Report_Draft.docx');
 const coverTitle=s.shapes.items[0]; coverTitle.text='Harness Hyperparameter\nOptimization';
 coverTitle.position={left:68,top:135,width:1140,height:185}; coverTitle.text.style={fontSize:62,bold:true,color:C.navy,typeface:font};
 text(s,'PI Agent on SkillsBench',68,365,1120,76,42,C.navy);
 text(s,'Default · Random search · Bayesian optimization · Multi-fidelity search',68,467,1090,86,29,C.gray);
 text(s,'PE6203 Group Project 3  |  30 October 2026',68,594,1090,55,25,C.gray);
}
// 2
{
 const s=slide('Harness, benchmark and task split',
 'The fixed stack uses PI version 0.81.0, pi-acp 0.0.34 and BenchFlow 0.6.3, with Qwen3 Coder through OpenRouter. We use Linux Docker, no skills, a single-shot loop and concurrency one. Three validation tasks guide configuration selection and three disjoint held-out tasks evaluate the selected configuration. The benchmark commit and task hashes are frozen. There are only three independent test questions; four methods on those questions produce twelve primary evaluation slots.','protocol.json; final_test_protocol.json');
 table(s,['Component','Setting'],[
 ['Harness / model','PI 0.81.0 + pi-acp 0.0.34 / Qwen3 Coder'],
 ['Execution','BenchFlow 0.6.3 · Docker · concurrency 1'],
 ['Validation','Financial modeling · JAX basics · Travel planning'],
 ['Held-out test','Python → Scala · Reserves at risk · Three.js parser']],{h:350,widths:[280,872],size:25});
 takeaway(s,'3 validation tasks and 3 disjoint test tasks; benchmark and definitions pinned');
}
// 3
{
 const s=slide('Exposed search space and objective',
 'We tune two exposed provider-model fields: contextWindow and maxTokens. Each has three declared values, giving nine configurations. BenchFlow forwards these values through BENCHFLOW_PROVIDER_MODELS into PI configuration. We do not modify model weights, prompts, the agent loop, task definitions or verification. The objective is high validation success under the declared admission and evaluation budgets. Strict passes lead the ranking, followed by mean reward, lower observed cost and candidate order. Only candidates completing all three validation tasks may be selected.','run_search.py; protocol.json');
 table(s,['Parameter','Declared values'],[['contextWindow','64,000 · 96,000 · 128,000'],['maxTokens','4,096 · 8,192 · 16,384']],{h:220,widths:[340,812],size:31});
 text(s,'Objective: maximize validation task success within the search budget',70,425,1110,74,30,C.navy,true);
 text(s,'Selection uses complete 3-task candidates; test outcomes never choose settings.',70,525,1110,70,27,C.gray);
}
// 4
{
 const s=slide('Developed method: two-stage multi-fidelity search',
 'Our method allocates task coverage in two stages. First, five unique configurations each run the financial-modeling task. We rank them using task success, reward and observed cost. The two promoted candidates then run JAX and travel planning. The initial screening result is reused, so the total is five plus four, or nine task slots. This is intended to avoid spending three tasks on every candidate. Its assumption is that the screening task is informative. Here every screening evaluation fails, so promotion relies on tie-breaking and the proxy is weak.','run_search.py; multifidelity_state.json');
 table(s,['Stage','Configurations','Task coverage','Slots'],[
 ['1  Screen','5 unique candidates','Financial-modeling-qa','5'],
 ['2  Promote','Top 2 candidates','JAX + Travel','4'],
 ['3  Select','Complete candidates','Reuse screening result','9 total']],{h:310,widths:[220,310,440,182],size:27});
 text(s,'Intended saving: spend full validation coverage only on promising candidates.',70,520,1100,75,28,C.teal,true);
 text(s,'Key assumption: the screening task predicts broader task performance.',70,605,1100,45,25,C.gray);
}
// 5
{
 const s=slide('Implementation and baseline comparison',
 'The Python pipeline generates configurations, launches the fixed harness, collects verifier rewards and queries dedicated-key usage. Ledgers are written before execution, so an interrupted run cannot silently relaunch. Random evaluates three unique configurations on three tasks. Bayesian uses standard Optuna TPE, with duplicate proposals allowed. In this run all three Bayesian proposals are numerically identical. All search methods have nine planned slots and a 1.50 dollar admission ceiling. Random and multi-fidelity each have an additional recovery launch, an important fairness caveat.','run_search.py; run_test.py; bench_hardened.py');
 table(s,['Method','Search allocation','Actual launches'],[
 ['Default','No tuning; no parameter overrides','Not a search method'],
 ['Random','3 unique configurations × 3 tasks','10 including recovery'],
 ['Bayesian / TPE','3 candidate records × 3 tasks','9; one unique configuration'],
 ['Multi-fidelity','5 screen + 2 × 2 continuation','10 including recovery']],{h:340,widths:[240,560,352],size:25});
 text(s,'Pipeline: generate → execute → verify → account → freeze → test',70,535,1110,55,28,C.navy,true);
 text(s,'Common declared caps; asymmetric recovery opportunities are disclosed.',70,610,1110,45,25,C.gray);
}
// 6 Native scatter with step points and actual cost axis.
{
 const s=slide('Validation incumbent versus cumulative search cost',
 'The horizontal axis is cumulative observed search accounting in dollars. The vertical axis is the best validation pass rate among complete eligible candidates. The incumbent is undefined until a configuration has three valid outcomes. Bayesian reaches one third at approximately ten cents and retains it. Random remains at zero among eligible candidates. Multi-fidelity has only one complete candidate at the end, so its curve is a single point. Default is untuned and has no search curve. These sparse observations do not establish a general optimizer ranking.','validation_summary.py; final_test_summary.json');
 const colors=[C.blue,C.orange,C.green];
 const series=Object.entries(summary.validation).map(([name,data],i)=>{
   const pts=[]; let prev=null;
   for(const r of data.curve){if(r.best_complete_candidate_rate===null)continue;
     if(prev)pts.push([r.cumulative_record_accounting_usd,prev[1]]);
     const p=[r.cumulative_record_accounting_usd,r.best_complete_candidate_rate];pts.push(p);prev=p;}
   return {name:name==='multifidelity'?'Multi-fidelity':name==='bayesian'?'Bayesian / TPE':'Random',xValues:pts.map(p=>p[0]),values:pts.map(p=>p[1]),smooth:false,line:{fill:colors[i],width:3},marker:{symbol:['circle','square','diamond'][i],size:8,fill:colors[i]}};
 });
 const c=s.charts.add('scatter',{position:{left:70,top:142,width:1140,height:438},series,scatterOptions:{style:'lineWithMarkers'},hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:23}},chartFill:'#FFFFFF',plotAreaFill:'#FFFFFF',
 xAxis:{title:'Cumulative search accounting (USD)',min:0,max:.33,majorUnit:.05,numberFormatCode:'0.00',textStyle:{fontSize:22}},
 yAxis:{title:'Best validation pass rate',min:0,max:.4,majorUnit:.1,numberFormatCode:'0%',textStyle:{fontSize:22},majorGridlines:{fill:'#DDE4EB',width:1}}});
 applyPresentationChartFont(c,{fontFamily:font});
 text(s,'Bayesian: 1/3 validation success; Random and multi-fidelity: 0/3',70,606,1120,42,25,C.teal,true);
}
// 7
{
 const s=slide('Held-out test results and generalization',
 'Primary evaluation produced ten valid zero rewards and two missing rewards, one each for Default and Bayesian on Scala. We preserved those records. A later documented amendment allowed one supplementary launch for each missing slot, with unchanged configurations and limits. Both supplements score zero. The supplemented pass at one is therefore zero out of three for every method. Bayesian falls from one third validation success to zero on the three test tasks. The gap is descriptive and based on tiny different task sets, so it cannot prove overfitting.','final_test_summary.json; supplementary_test/amendment.json');
 table(s,['Method','Selected validation','Primary test','Supplemented test'],[
 ['Default','1/3 historical baseline','0/2 + 1 missing','0/3  (0%)'],
 ['Random','0/3','0/3','0/3  (0%)'],
 ['Bayesian / TPE','1/3','0/2 + 1 missing','0/3  (0%)'],
 ['Multi-fidelity','0/3','0/3','0/3  (0%)']],{h:330,widths:[230,285,305,332],size:26});
 text(s,'Bayesian validation → supplemented test: −33.3 percentage points',70,530,1110,65,29,C.teal,true);
 text(s,'Two post hoc supplements are separate; original missing outcomes remain visible.',70,613,1110,44,24,C.gray);
}
// 8 Native cost chart.
{
 const s=slide('Search cost and selected-configuration execution cost',
 'Search cost is a one-time optimization expense, whereas execution cost recurs when using the chosen settings. This chart includes primary plus supplementary test execution. Search is most expensive for multi-fidelity in this run, partly because of a single costly screen. The complete accounting scope is 0.65175928 dollars of search plus 0.33955972 of primary and supplementary execution, or 0.991319 dollars. The earlier Default validation baseline costs 0.14043120 dollars and is excluded from that subtotal. Provider probes and preparation are also excluded. No observed test gain justifies amortizing the search cost.','final_test_summary.json');
 const names=['Default','Random','Bayesian','Multi-fidelity'];
 const keys=['default','random','bayesian','multifidelity'];
 const c=s.charts.add('bar',{position:{left:65,top:150,width:780,height:430},categories:names,
 series:[{name:'Search',values:keys.map(k=>summary.validation[k]?.budget_accounted_usd??0),fill:C.navy},
 {name:'Test + supplement',values:keys.map(k=>summary.supplementary.completed_estimates[k].test_accounted_usd),fill:C.teal}],
 barOptions:{direction:'column',grouping:'stacked'},hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:22}},
 xAxis:{textStyle:{fontSize:22}},yAxis:{title:'Observed USD',min:0,max:.45,majorUnit:.1,numberFormatCode:'0.00',textStyle:{fontSize:22},majorGridlines:{fill:'#DDE4EB',width:1}}});
 applyPresentationChartFont(c,{fontFamily:font});
 text(s,'$0.65176',895,202,310,70,44,C.navy,true);text(s,'search accounting',895,280,310,50,25,C.gray);
 text(s,'$0.33956',895,365,310,70,44,C.teal,true);text(s,'test + supplement',895,443,310,62,25,C.gray);
 text(s,'No demonstrated test gain; cost per solved task is undefined.',70,605,1130,46,27,C.teal,true);
}
// 9
{
 const s=slide('Parameter sensitivity: exploratory evidence',
 'We use existing validation records only and compare the same task while holding one field fixed. Across twenty-five scored observations, there are six matched pairs. This table highlights three contrasts; all six are in the backup evidence. The largest observed cost increase comes from raising maxTokens at context 128000 on the financial task, but the high-limit cell has only one run. A larger context coincides with some success on JAX and travel, also with few observations. Both financial cost contrasts depend on the same expensive run. These are associations, not causal estimates or reliable importance rankings.','parameter_sensitivity.json');
 table(s,['Task / fixed field','Parameter change','n low / high','Success Δ','Mean USD Δ'],[
 ['Financial / context 128k','maxTokens 4096 → 8192','5 / 1','0 pp','+0.14353'],
 ['JAX / maxTokens 4096','context 96k → 128k','2 / 3','+33.3 pp','+0.00123'],
 ['Travel / maxTokens 4096','context 96k → 128k','1 / 4','+25.0 pp','−0.05064']],{h:290,widths:[280,330,160,170,212],size:24});
 text(s,'6 matched comparisons across 25 scored validation observations',70,495,1120,55,29,C.navy,true);
 text(s,'Limited replication and confounding prevent a reliable parameter ranking.',70,590,1120,64,27,C.teal,true);
}
// 10
{
 const s=slide('Representative failures and success reversals',
 'The recovered real Default validation baseline gives both directions required for a comparison. On JAX, Default scores zero while the selected Bayesian candidate scores one. On travel, Default scores one while that candidate scores zero. These are validation cases, not held-out cases, and different run times and randomness prevent a causal interpretation. On held-out tasks, all methods fail: Excel outputs miss required formulas, Three.js outputs miss cabin instances or valid vertices, and Scala outputs have compilation or test-integration problems. Both supplementary Scala source files compile, but test compilation reports twenty-one unresolved-symbol errors.','validation_default_summary.json; final_test_failure_analysis.md');
 table(s,['Validation task','Default','Selected Bayesian','Observed contrast'],[
 ['JAX basics','0','1','Tuned success; Default failure'],
 ['Travel planning','1','0','Default success; tuned failure']],{h:200,widths:[300,160,280,412],size:25});
 text(s,'Held-out failures',70,409,1100,50,31,C.navy,true);
 text(s,'Excel: missing formulas   •   Three.js: missing instances / vertices\nScala: source or test-compilation errors',70,474,1110,100,27);
 text(s,'Success reversals are validation evidence; harmful parameter interaction is unproven.',70,612,1120,44,24,C.gray);
}
// 11
{
 const s=slide('Interpretation and limitations',
 'The main limitations are substantive, not just formatting caveats. We have only three held-out tasks, sparse replication and one unique Bayesian configuration. Equal declared caps do not mean identical actual spending, but extra recovery opportunities were asymmetric. Failure-handling amendments and installation hardening were introduced during the study. The two supplements were declared separately after seeing the original missing outcomes. We preserve primary and supplementary results and do not report the better of repeated attempts. Sensitivity remains exploratory. These limits mean we can describe this run but cannot claim a robust optimizer ranking.','report_draft/PE6203_Harness_HPO_Report_Draft.docx');
 lines(s,['Small sample: 3 held-out tasks and sparse independent replication',
 'Fairness: common caps, but asymmetric recovery opportunities',
 'Protocol: failure rules and supplements amended during the study',
 'Inference: no reliable parameter ranking or harmful-interaction estimate'],165,29,103);
}
// 12
{
 const s=slide('Conclusions and lessons learned',
 'We implemented an auditable HPO workflow with a student-developed multi-fidelity search and three required references. No test improvement was observed, including the two supplements. The lessons are to use an informative screening task, distinguish execution failures from scored zeros, and plan replication and failure rules before final evaluation. Our strongest contribution is a reproducible account of negative results, costs and failure evidence. Thank you.','final_test_summary.json; final_test_failure_analysis.md');
 lines(s,['No observed held-out improvement: all supplemented results are 0/3',
 'Screening quality matters: all first-stage candidates failed the proxy task',
 'Reliable comparisons need replication and predeclared failure handling'],185,32,125);
 text(s,'Evidence and reproducibility are the main outcomes of this pilot study.',70,594,1120,61,29,C.teal,true);
}
// 13 Q&A, no new claims.
{
 const s=slide('Questions and discussion',
 'Five-minute Q&A. Why no performance gain? The task sample is small and verifier logs show structural output and compilation failures. Why supplement? Two primary outcomes were missing, and an explicit amendment allowed one additional launch each without tuning. Why no full sensitivity study? Time constraints; we retain exploratory observations and disclose the evidence gap. Why TPE repeated settings? Duplicates were allowed under a tiny proposal budget; this limits exploration. Default baseline summaries are real saved records, not synthetic demo outputs.','supplementary_test/amendment.json; parameter_sensitivity.md');
 text(s,'Q&A',70,230,1110,100,76,C.navy,true);
 text(s,'5 minutes',74,355,1080,68,34,C.gray);
 text(s,'Budget fairness · Missing outcomes · Sensitivity limits · Failure evidence',74,510,1090,85,28,C.gray);
}
// 14 Backup full sensitivity table.
{
 const s=slide('Backup: full matched-parameter comparisons',
 'Use only if asked. Each row holds the other field fixed and uses the same validation task. The two large financial cost contrasts share a single expensive high-context, high-token run, so they are not independent confirmations. Repetition counts differ and method/order effects are confounded. There was no additional sensitivity experiment. The complete numeric evidence and exclusion of missing outcomes are in parameter_sensitivity.json.','parameter_sensitivity.json');
 const rows=sensitivity.pairs.map(p=>[p.task==='financial-modeling-qa'?'Financial':p.task==='jax-computing-basics'?'JAX':'Travel',
   p.parameter==='contextWindow'?'Context':'maxTokens',String(p.fixed_value),`${p.lower[p.parameter]} → ${p.upper[p.parameter]}`,
   `${p.lower.n} / ${p.upper.n}`,`${(p.pass_rate_delta*100).toFixed(1)} pp`,`${p.mean_usd_delta>=0?'+':''}${p.mean_usd_delta.toFixed(5)}`]);
 table(s,['Task','Changed','Other fixed','Low → high','n','Success Δ','USD Δ'],rows,{y:153,h:380,widths:[155,150,160,230,105,165,187],size:22});
 text(s,'Observational comparisons only; no claim of causal parameter importance.',70,602,1120,50,25,C.teal,true);
}

if(timings.reduce((a,b)=>a+b,0)!==600)throw Error('Talk timing must total 600 seconds');
await fs.writeFile(path.join(out,'Speaker_Notes_and_Timing.md'),scripts.map(s=>`# ${s.slide}. ${s.title}\n\n${s.seconds?`Target: ${s.seconds} seconds`:'Q&A / backup'}\n\n${s.notes}\n`).join('\n'));
const candidatePath=path.join(build,'candidate.pptx');
await (await PresentationFile.exportPptx(deck)).save(candidatePath);
console.log('Exported candidate: '+candidatePath);
for(let i=0;i<deck.slides.items.length;i++){
  const png=await deck.export({slide:deck.slides.items[i],format:'png',scale:1});
  await fs.writeFile(path.join(build,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));
}
const finalPath=path.join(out,'PE6203_HPO_Presentation_v2.pptx');
const result=await finalizePresentation({workspaceDir:work,candidatePath,finalPath,
 pythonExecutable:runtime+'/python/python.exe',
 integrityValidatorPath:skill+'/container_tools/inspect_presentation_package_integrity.py',
 layoutValidatorPath:skill+'/container_tools/inspect_presentation_layout_geometry.py',
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',...[2,3,4,5,7,9,10,14].flatMap(n=>['--require-native-table-slide',String(n)])],
 explicitTotalSlideCount:14,requiredNativeTableOwnerSlides:[2,3,4,5,7,9,10,14],requiredNativeChartOwnerSlides:[6,8],
 materializeLiteralChartWorkbooks:true,nativeChartTargetApplication:'powerpoint',
 fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,
 receiptPath:path.join(build,'validation-v2.json')});
console.log('Final deck: '+result.finalPath);
