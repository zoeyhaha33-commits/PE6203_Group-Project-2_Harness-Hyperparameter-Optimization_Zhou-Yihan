import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
const runtime='C:/Users/happy/.cache/codex-runtimes/codex-primary-runtime/dependencies';
process.env.RUNTIME_NODE_MODULES=runtime+'/node/node_modules';
const {Presentation,PresentationFile}=await import(pathToFileURL(runtime+'/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs').href);
const skill='C:/Users/happy/.codex/plugins/cache/openai-primary-runtime/presentations/26.1025.11240/skills/presentations';
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(skill+'/container_tools/artifact_tool_utils.mjs').href);
const root=path.dirname(fileURLToPath(import.meta.url));
const work=path.join(root,'presentation'),build=path.join(work,'.expanded-build'),out=path.join(work,'output');
await fs.mkdir(build,{recursive:true});await fs.mkdir(out,{recursive:true});
const S=JSON.parse(await fs.readFile(path.join(root,'final_test_summary.json'),'utf8'));
const P=JSON.parse(await fs.readFile(path.join(root,'parameter_sensitivity.json'),'utf8'));
const deck=Presentation.create({slideSize:{width:1280,height:720}});
const C={navy:'#17324D',teal:'#087F8C',gray:'#586779',ink:'#263547',blue:'#3978B4',orange:'#C77822',green:'#397B58'};
const FONT='Arial',times=[20,35,40,40,40,60,35,60,50,45,50,65,35,25],scripts=[];
function txt(s,t,x,y,w,h,size=25,color=C.ink,bold=false){
 const shape=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 shape.text=t;shape.text.style={typeface:FONT,fontFamily:FONT,fontSize:size,color,bold};return shape;
}
function page(title,sub,notes,source='final_test_summary.json'){
 const s=deck.slides.add();s.background.fill='#FFFFFF';const n=deck.slides.items.length;
 txt(s,title,60,38,1160,67,42,C.navy,true);if(sub)txt(s,sub,64,112,1150,54,23,C.gray);
 txt(s,'PE6203  |  PI Agent on SkillsBench',64,681,1050,22,15,C.gray);txt(s,String(n).padStart(2,'0'),1150,681,65,22,15,C.gray);
 const sec=times[n-1]??0;s.speakerNotes.text=`${sec?'Target duration: '+sec+' seconds.':'Backup / 5-minute Q&A; outside the main talk.'}\n\n${notes}\n\nEvidence: real_study/${source}. Figures are project-local observations; no synthetic demo data are used.`;
 scripts.push({n,title,sec,notes});return s;
}
function table(s,headers,rows,x=64,y=186,w=1152,h=310,widths=null,size=24){
 const all=[headers,...rows],t=s.tables.add({rows:all.length,columns:headers.length,left:x,top:y,width:w,height:h,values:all,...(widths?{columnWidths:widths}:{})});
 all.forEach((r,i)=>r.forEach((_,j)=>{let c=t.getCell(i,j);c.fill=i===0?C.navy:i%2?'#EFF3F7':'#FFFFFF';c.text.style={typeface:FONT,fontFamily:FONT,fontSize:size,color:i===0?'#FFFFFF':C.ink,bold:i===0};}));
 t.borders.assign({fill:'#DCE4EB',width:.7,style:'solid'});return t;
}
function block(s,label,body,x,y,w=535,size=25,h=102){txt(s,label,x,y,w,39,28,C.navy,true);txt(s,body,x,y+44,w,h,size);}
function end(s,t,y=622){txt(s,t,64,y,1152,47,24,C.teal,true);}
function curveSeries(){return Object.entries(S.validation).map(([name,v],i)=>{let pts=[],prev;
 for(const r of v.curve){if(r.best_complete_candidate_rate===null)continue;if(prev)pts.push([r.cumulative_record_accounting_usd,prev[1]]);prev=[r.cumulative_record_accounting_usd,r.best_complete_candidate_rate];pts.push(prev);}
 const color=[C.blue,C.orange,C.green][i];return{name:name==='multifidelity'?'Multi-fidelity':name==='bayesian'?'Bayesian / TPE':'Random',xValues:pts.map(p=>p[0]),values:pts.map(p=>p[1]),smooth:false,line:{fill:color,width:3},marker:{symbol:['circle','square','diamond'][i],fill:color,size:8}};});}

// 01 — Cover
{
 const s=page('Harness hyperparameter optimization','',
 'Our project studies hyperparameter optimization over a fixed PI Agent harness. We compare a two-stage multi-fidelity method with Default, Random search and Bayesian optimization. This pilot did not produce a held-out performance gain; we explain the method, evidence and lessons.');
 const t=s.shapes.items[0];t.text='Harness Hyperparameter\nOptimization';t.position={left:68,top:120,width:1130,height:180};t.text.style={typeface:FONT,fontSize:62,color:C.navy,bold:true};
 txt(s,'An empirical study of PI Agent on SkillsBench',72,355,1110,70,38,C.navy);
 txt(s,'Two-stage multi-fidelity search under task and monetary budgets',72,452,1110,65,28,C.gray);
 txt(s,'PE6203 Group Project 3  |  30 October 2026',72,598,1110,45,25,C.gray);
}
// 02 — Motivation and research questions
{
 const s=page('Research problem and study design','Optimize exposed configuration inputs while keeping the agent implementation fixed',
 'The project treats harness improvement as configuration search. Our question is whether a small supported parameter surface improves success within a declared budget, and whether that improvement survives held-out testing. We separate the one-time search expense from the runtime cost of using the selected configuration. The contribution is a complete empirical workflow, including a student-developed multi-fidelity allocation strategy. The experiment is deliberately small, and we evaluate the claim with verifier outcomes rather than subjective output quality.','report_draft/PE6203_Harness_HPO_Report_Draft.docx');
 block(s,'Research questions','1. Which configuration performs best on validation?\n2. Does the selected setting generalize to unseen tasks?\n3. Does any gain justify search and execution cost?',68,190,550,26,190);
 block(s,'Experimental boundary','Fixed model, agent loop, prompts and task verifier.\nOnly contextWindow and maxTokens vary.\nTest outcomes never choose the configuration.',675,190,535,26,190);
 block(s,'What we contribute','Reproducible scheduling, raw-result collection, cost accounting and two-stage task allocation.',68,454,550,26,110);
 block(s,'What the evidence supports','A small-scale negative result with auditable failure cases—not a demonstrated optimizer advantage.',675,454,535,26,110);
 end(s,'Success is defined by official task verification, not by fluent output or heuristic quality scores.');
}
// 03 — Setup
{
 const s=page('Fixed execution stack and reproducible task split','Three validation tasks guide search; three different held-out tasks evaluate the frozen selection',
 'The fixed stack is PI 0.81.0 with pi-acp 0.0.34, BenchFlow 0.6.3 and Qwen3 Coder through OpenRouter. Runs use Docker, no skills, a single-shot loop and concurrency one. Validation uses financial modeling, JAX and travel planning; testing uses Scala translation, reserves at risk and Three.js parsing. Commit and task-definition fingerprints are recorded. Four methods on the same three test tasks produce twelve primary slots, not twelve independent questions. The small split is a major limitation.','protocol.json; final_test_protocol.json');
 table(s,['Component','Fixed setting'],[['Harness','PI 0.81.0 / pi-acp 0.0.34'],['Orchestrator','BenchFlow 0.6.3'],['Model','qwen/qwen3-coder'],['Runtime','Docker; no-skill; single-shot'],['Concurrency','1']],64,183,558,354,[180,378],23);
 block(s,'Validation tasks','financial-modeling-qa\njax-computing-basics\ntravel-planning',670,186,540,25,130);
 block(s,'Held-out tasks','python-scala-translation\nreserves-at-risk-calc\nthreejs-structure-parser',670,391,540,25,130);
 txt(s,'Pinned benchmark commit: b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af',68,565,1140,42,20,C.gray);
 end(s,'600-second agent limit on final tasks; original resource and verifier settings retained.');
}
// 04 — Parameters and selection
{
 const s=page('Exposed parameters and configuration selection','A 3 × 3 configuration space; complete validation results determine eligibility',
 'The configuration space has three contextWindow values and three maxTokens values. These are passed through BenchFlow provider-model metadata to PI. Context controls the configured context budget and maxTokens the generation limit; this is not a claim about the model vendor’s maximum capability. Only candidates with three valid validation outcomes are eligible. Selection ranks strict passes, then mean official reward, then lower observed candidate cost, then candidate index. Default passes no overrides. Keeping the eligibility rule matters because a Random candidate with one success has another missing result.','run_search.py; protocol.json');
 table(s,['Field','Declared values'],[['contextWindow','64k / 96k / 128k'],['maxTokens','4096 / 8192 / 16384']],64,190,558,228,[220,338],27);
 block(s,'Configuration interface','BENCHFLOW_PROVIDER_MODELS\n→ generated PI provider-model settings\nDefault: no parameter override',68,454,550,23,100);
 block(s,'Eligibility before ranking','All 3 validation tasks must have valid scores.\nMissing outcomes are not replaced by zero.',670,188,540,26,110);
 block(s,'Tie-breaking order','Strict passes → mean reward\n→ lower observed candidate cost\n→ earlier candidate index',670,382,540,26,140);
 end(s,'Objective: high validation task success under the declared evaluation and cost caps.');
}
// 05 — Baselines and fairness
{
 const s=page('Comparison methods and declared budgets','All search methods receive 9 planned task slots and a USD 1.50 admission ceiling',
 'Default is untuned. Random samples three unique configurations and evaluates three tasks each. Bayesian uses standard Optuna TPE with one startup trial and three candidate records; duplicates are allowed and all three records happen to be identical here. Our method allocates five screening tasks and four continuations. Actual search launches differ because Random and multi-fidelity each used one additional recovery attempt. Equal budget ceilings do not require equal actual spending, but asymmetric extra opportunities are a fairness limitation. We disclose them instead of claiming completely equal realized attempts.','run_search.py; final_test_summary.json');
 table(s,['Method','Configuration allocation','Unique settings','Launches'],[['Default','No search / no overrides','—','—'],['Random','3 candidates × 3 validation tasks','3','10'],['Bayesian / TPE','3 candidate records × 3 tasks','1','9'],['Multi-fidelity','5 screens + 2 × 2 continuations','5','10']],64,183,1152,315,[230,530,220,172],24);
 block(s,'Budget admission','USD 0.20 reserve per admission.\nShared held-out ceiling: USD 2.00.',68,534,560,24,75);
 block(s,'Fairness limitation','Extra recovery attempts are not symmetric.\nActual USD expenditure is reported separately.',675,534,535,24,75);
}
// 06 — Developed algorithm
{
 const s=page('Developed method: two-stage multi-fidelity search','Task coverage is the fidelity variable; screening results are reused rather than rerun',
 'The developed method samples five unique configurations and tests each on financial-modeling-qa. It promotes two using the declared ranking and evaluates JAX and travel only for those two, reusing the screen. That is five plus four slots. In this run candidates one and zero are promoted, and zero is eventually selected because candidate one has a missing continuation outcome. All five screens score zero, so the screening signal cannot separate success and promotion depends on tie-breaking. This explains why the method’s intended allocation efficiency is not enough to establish performance or cost improvement.','multifidelity_state.json; run_search.py');
 block(s,'1  Screen five configurations','Each runs financial-modeling-qa once.\n5 configurations × 1 task = 5 slots',70,181,575,27,85);
 block(s,'2  Continue the top two','Candidates 1 and 0 run JAX + Travel.\n2 configurations × 2 tasks = 4 slots',70,335,575,27,85);
 block(s,'3  Select a complete candidate','Reuse its screening result.\nSelect candidate 0: context 64k / tokens 16384.',70,490,575,27,95);
 txt(s,'5 + 4 = 9',785,190,410,80,54,C.teal,true);
 txt(s,'validation task slots',786,282,410,45,28,C.gray);
 block(s,'Why it might help','Reject weak configurations before full evaluation.',730,366,480,27,82);
 block(s,'What happened here','All screening rewards were 0.\nThe proxy task provided no success separation.',730,498,480,26,100);
}
// 07 — Implementation and safeguards
{
 const s=page('Implementation and outcome accounting','A persisted ledger connects configuration generation, execution, scoring and cost',
 'The implementation is Python orchestration around the fixed BenchFlow and PI runtime. Configuration generation creates candidate records. The launcher persists a slot before a subprocess, runs the harness and retains the official raw verifier result. Dedicated-key usage snapshots are used for costs because token telemetry may be unavailable. Source task hashes and frozen selection hashes stop unnoticed changes. Missing outcomes, scored zeros and billing-pending states remain distinct. Installation hardening changed bounded download retries and checks, not the agent loop, but was introduced during validation and is disclosed.','run_search.py; run_test.py; bench_hardened.py');
 table(s,['Pipeline step','Implementation artifact'],[['Generate / schedule','run_search.py; seed 20261028'],['Execute fixed harness','bench_hardened.py → BenchFlow / PI'],['Verify / account','result.json + dedicated-key usage deltas'],['Freeze / test','final_test_protocol.json + run_test.py']],64,184,720,300,[235,485],23);
 block(s,'Key safeguards','Persist before launch.\nCheck task / protocol fingerprints.\nSerialize runs with a shared lock.\nRetain raw evidence and billing checks.',835,185,385,24,210);
 txt(s,'Scored zero ≠ missing reward ≠ unresolved billing',70,533,1140,51,29,C.teal,true);
 txt(s,'Installation retries and later failure-rule amendments are documented operational changes.',70,603,1140,51,23,C.gray);
}
// 08 — Curve and interpretation
{
 const s=page('Validation incumbent and configuration selection','Best-so-far performance includes only complete, eligible validation candidates',
 'The curve is plotted against cumulative observed search cost, with straight step segments. Bayesian obtains one success out of three at about ten cents, then retains it. Random’s eligible candidates remain at zero; its other candidate has a success but is incomplete, so it cannot be the incumbent. Multi-fidelity only completes an eligible candidate at the final slot; its incumbent is a single point at zero. Therefore the graph provides little evidence about early convergence for that method. Default has no search curve because it is untuned. The right-side selected settings explain the final evaluation.','validation_summary.py; final_test_summary.json');
 const ch=s.charts.add('scatter',{position:{left:58,top:184,width:815,height:391},series:curveSeries(),scatterOptions:{style:'lineWithMarkers'},hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:20}},chartFill:'#FFFFFF',
 xAxis:{title:'Cumulative search accounting (USD)',min:0,max:.33,majorUnit:.05,numberFormatCode:'0.00',textStyle:{fontSize:20}},yAxis:{title:'Best validation pass rate',min:0,max:.4,majorUnit:.1,numberFormatCode:'0%',textStyle:{fontSize:20},majorGridlines:{fill:'#DDE4EB',width:1}}});applyPresentationChartFont(ch,{fontFamily:FONT});
 block(s,'Selected settings','Random 64k / 16384: 0/3\nTPE 128k / 4096: 1/3\nMulti-fid. 64k / 16384: 0/3',907,186,310,22,150);
 block(s,'Interpreting the curve','TPE repeats one setting.\nMulti-fidelity completes its\nonly incumbent at slot 9.',907,390,310,24,135);
 end(s,'A single success and a small task set do not establish a general optimizer ranking.');
}
// 09 — Held-out
{
 const s=page('Held-out performance and generalization','The selected configurations are evaluated separately from validation',
 'The original final test has ten valid zeros and two missing outcomes. An explicitly recorded later amendment permits one supplementary Scala launch each for the two missing Default and Bayesian slots. Both supplements finish with official zero and settled costs. We preserve the original results and separately present supplemented estimates. Every method has zero successes out of three after supplementation. Bayesian’s gap is minus thirty-three point three percentage points from the selected validation candidate. Default’s historical validation baseline also has one success, but predates the later installation wrapper, another comparison caveat.','final_test_summary.json; supplementary_test/amendment.json');
 table(s,['Method','Validation result','Original test','After supplementation'],[['Default','1/3 historical baseline','0/2 + 1 missing','0/3 (0%)'],['Random','0/3 selected candidate','0/3','0/3 (0%)'],['Bayesian / TPE','1/3 selected candidate','0/2 + 1 missing','0/3 (0%)'],['Multi-fidelity','0/3 selected candidate','0/3','0/3 (0%)']],64,182,1152,302,[232,300,280,340],24);
 block(s,'Generalization gap','Bayesian: 1/3 validation → 0/3 test\nGap: −33.3 pp; descriptive only.',68,518,560,26,83);
 block(s,'Protocol disclosure','One extra Scala attempt for each missing slot.\nNo tuning, no best-of-attempt replacement.',675,518,535,25,83);
}
// 10 — Costs
{
 const s=page('Search cost versus selected-configuration runtime cost','No observed held-out gain is available to offset the one-time optimization expense',
 'The stacked chart separates one-time search from primary plus supplementary test execution. Search costs are approximately 0.2043 dollars for Random, 0.1416 for Bayesian and 0.3058 for multi-fidelity. Multi-fidelity is the most expensive here, affected by one costly screen. Total search plus test and supplement accounting is 0.991319 dollars. The old Default validation baseline is 0.14043120 dollars and excluded from that scope, as are probes and preparation. A stable usage difference is not a hard provider billing guarantee. With no solved test tasks, cost per solved task and an amortization break-even claim are unsupported.','final_test_summary.json');
 const keys=['default','random','bayesian','multifidelity'];
 const ch=s.charts.add('bar',{position:{left:56,top:182,width:720,height:379},categories:['Default','Random','Bayesian','Multi-fidelity'],series:[{name:'Search',values:keys.map(k=>S.validation[k]?.budget_accounted_usd??0),fill:C.navy},{name:'Test + supplement',values:keys.map(k=>S.supplementary.completed_estimates[k].test_accounted_usd),fill:C.teal}],barOptions:{direction:'column',grouping:'stacked'},hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:20}},xAxis:{textStyle:{fontSize:20}},yAxis:{title:'Observed USD',min:0,max:.45,majorUnit:.1,numberFormatCode:'0.00',textStyle:{fontSize:20},majorGridlines:{fill:'#DDE4EB',width:1}}});applyPresentationChartFont(ch,{fontFamily:FONT});
 table(s,['Accounted phase','USD'],[['Optimizer search','0.65175928'],['Test + supplements','0.33955972'],['Combined scope','0.99131900']],816,187,400,244,[255,145],22);
 txt(s,'Earlier Default validation baseline:\nUSD 0.14043120, reported separately.\nProbes / preparation excluded.',830,464,375,100,21,C.gray);
 end(s,'Admission caps are not hard spending caps; observed Key deltas are subject to delayed billing.');
}
// 11 — sensitivity
{
 const s=page('Parameter sensitivity: matched validation observations','Same task; change one field while holding the other fixed',
 'We retain the report’s exploratory sensitivity analysis rather than imply that a full ablation was performed. It uses twenty-five scored records and six matched comparisons. Increasing maxTokens from 4096 to 8192 at context 128k has the largest observed cost contrast, but the larger setting has only one run and no financial-task success. Larger context coincides with successes on JAX and travel, with unequal repeats and method/order confounding. The two large financial contrasts share one expensive run. We can report these observations, but cannot rank causal importance or estimate harmful interaction.','parameter_sensitivity.json');
 table(s,['Fixed task / field','Parameter contrast','n low / high','Success Δ','Mean USD Δ'],[['Financial / context 128k','tokens 4096 → 8192','5 / 1','0 pp','+0.14353'],['JAX / tokens 4096','context 96k → 128k','2 / 3','+33.3 pp','+0.00123'],['Travel / tokens 4096','context 96k → 128k','1 / 4','+25.0 pp','−0.05064']],64,181,1152,281,[290,330,160,165,207],23);
 block(s,'Observed pattern','Parameter changes correlate with cost\nand occasional successes.',68,496,555,26,89);
 block(s,'Evidence limit','Unequal repeats; one costly run.\nNo reliable importance ranking.',675,496,535,26,89);
 end(s,'6 matched pairs; 25 scored observations. Missing outcomes are excluded.');
}
// 12 — report-backed failures
{
 const s=page('Validation reversals and held-out failure evidence','The selected Bayesian candidate trades success across tasks rather than dominating Default',
 'The report contains both requested directional examples on validation. Default fails JAX while selected Bayesian succeeds; Default succeeds travel while the selected Bayesian candidate fails. These are real historical baseline records, not synthetic demo data. Raw baseline Linux jobs have not been re-read, so we do not invent their behavioral causes. The held-out logs are available and show concrete faults: required Excel formulas are missing; Three.js instance structures or vertices are missing; Scala has source or test-compilation failures. For both supplements, source compilation succeeds but test compilation fails with twenty-one symbol-resolution errors. These problems explain valid zeros without equating heuristic quality scores with task success.','validation_default_summary.json; final_test_failure_analysis.md');
 table(s,['Validation task','Default','Selected TPE'],[['JAX basics','0','1'],['Travel planning','1','0']],64,185,550,197,[268,130,152],25);
 block(s,'What this comparison means','Both directions are observed on validation.\nDifferent times, wrapper versions and model\nrandomness prevent causal attribution.',68,430,545,25,133);
 block(s,'Held-out verifier findings','Excel: required formulas missing.\nThree.js: cabin instances / vertices missing.\nScala: compilation or test-integration errors.',670,185,545,25,140);
 txt(s,'Scala supplementary log excerpt',675,400,535,38,25,C.navy,true);
 txt(s,'Compilation successful\nTest / compileIncremental failed\nTokenType: not found\n21 errors found',675,450,535,126,23,C.gray);
 end(s,'Official rewards remain 0; 88% / 96% code-quality scores are not pass rates.');
}
// 13 — limitations
{
 const s=page('Interpretation, fairness and validity limits','Evidence supports a pilot-study conclusion, not a robust ranking of HPO algorithms',
 'Three threats are especially important. First, only three test tasks and sparse independent repetitions limit generalization. Second, the methods share declared caps, but two have extra recovery launches; observed cost differences alone are not the fairness issue. Third, failure-handling rules, installation hardening and the supplements were amended during the study. We preserve provenance and distinguish main from supplemental results. The Default/Bayesian validation reversals are descriptive, and sensitivity cannot identify causal effects. These are remaining evidence limitations, not issues that can be fixed by relabeling a chart.','report_draft/PE6203_Harness_HPO_Report_Draft.docx');
 block(s,'Sample and exploration','3 held-out tasks; sparse replication.\nTPE evaluated one unique setting three times.',68,190,555,27,100);
 block(s,'Budget and operations','Common caps, asymmetric recovery attempts.\nInstallation hardening introduced mid-validation.',675,190,535,27,100);
 block(s,'Post hoc changes','Two missing test slots supplemented once.\nOriginal failures and costs remain visible.',68,402,555,27,100);
 block(s,'Inference boundary','No reliable importance / interaction estimate.\nValidation reversals are not held-out success.',675,402,535,27,100);
 end(s,'Primary outcomes remain intact; no best-of-attempt selection or test-guided tuning.');
}
// 14 — conclusion
{
 const s=page('Conclusions and lessons learned','The contribution is an auditable HPO workflow and a transparent negative result',
 'We implemented a two-stage method and compared it with all three required references. No held-out improvement was observed. Screening quality matters because every candidate failed the proxy task. Future work should predeclare recovery rules and use repeated balanced validation to estimate parameter effects. The value of this pilot is a reproducible, cost-accounted record of what worked operationally and what did not improve task success.','final_test_summary.json; final_test_failure_analysis.md');
 block(s,'Empirical conclusion','All four supplemented configurations: 0/3.\nBayesian validation success did not generalize.',68,190,555,29,110);
 block(s,'Methodological lesson','Allocation efficiency needs a useful proxy.\nHere all five screening rewards were 0.',675,190,535,29,110);
 block(s,'Implementation lesson','Persist raw outcomes and costs.\nSeparate missing results from scored failures.',68,420,555,29,110);
 block(s,'Next research step','Replicated validation and balanced factor tests,\nwith failure handling declared in advance.',675,420,535,29,110);
}
// 15 — Q&A / practical answers
{
 const s=page('Discussion and Q&A','5 minutes • backup evidence follows',
 'Discuss the evidence limitations directly. A zero result is still reportable when verification and execution are auditable. The supplements were declared after observing two unscored failures, not used to retry scored zeros. The sensitivity results are exploratory due to time and replication limits. No optimizer superiority is claimed.','report_draft/PE6203_Harness_HPO_Report_Draft.docx');
 table(s,['Likely question','Evidence-based answer'],[['Why no improvement?','Common output-structure / compilation failures; very small task set.'],['Why were two tasks rerun?','Only missing rewards; one supplementary attempt each, separately reported.'],['Why not claim parameter importance?','Six observational contrasts, unequal repeats and confounding.'],['What would improve the study?','Informative screening task; prospective retry policy; balanced replication.']],64,190,1152,352,[350,802],25);
 end(s,'Backup slides: candidate history, complete sensitivity table and protocol/evidence details.');
}
// 16 — full candidate table
{
 const s=page('Backup: candidate history and final selection','Candidate IDs are zero-based; only complete three-task candidates are eligible',
 'The Random candidate with one success is ineligible because another task is missing. TPE selected candidate one despite proposing the same configuration in all three records. Multi-fidelity candidates two to four were screened but not continued, not counted as failures on unobserved tasks. Candidate one was promoted but missing a continuation; candidate zero was selected.','final_test_summary.json');
 const rows=[];for(const [name,v] of Object.entries(S.validation))for(const c of v.candidates)rows.push([name==='multifidelity'?'Multi-fidelity':name,c.candidate,`${c.config.contextWindow} / ${c.config.maxTokens}`,`${c.passes}/${c.scored}`,String(c.missing),c.eligible?'Yes':'No',c.selected?'Selected':'—']);
 table(s,['Method','ID','Context / tokens','Pass / scored','Missing','Eligible','Decision'],rows,64,184,1152,430,[195,70,260,180,130,135,182],20);
 end(s,'TPE repeated one setting; these are stochastic repeats, not distinct parameter points.');
}
// 17 — full sensitivity
{
 const s=page('Backup: all six matched-parameter contrasts','Delta = higher parameter value minus lower value; n counts valid observations',
 'Each pair compares the same task at a fixed other parameter. Two financial contrasts share the single expensive context128k/maxTokens8192 run. These rows should not be interpreted as independent repeated evidence of an interaction. No new factorial experiment was performed.','parameter_sensitivity.json');
 const rows=P.pairs.map(p=>[p.task==='financial-modeling-qa'?'Financial':p.task==='jax-computing-basics'?'JAX':'Travel',p.parameter==='contextWindow'?'Context':'maxTokens',String(p.fixed_value),`${p.lower[p.parameter]} → ${p.upper[p.parameter]}`,`${p.lower.n}/${p.upper.n}`,`${(p.pass_rate_delta*100).toFixed(1)} pp`,`${p.mean_usd_delta>=0?'+':''}${p.mean_usd_delta.toFixed(5)}`]);
 table(s,['Task','Changed','Other fixed','Low → high','n','Success Δ','USD Δ'],rows,64,183,1152,363,[155,150,160,230,105,165,187],22);
 txt(s,'Largest observed cost increase: maxTokens 4096 → 8192 at context 128k.',70,575,1140,38,24,C.navy,true);end(s,'One high-value observation; causal importance and interactions remain unknown.');
}
// 18 — evidence trail
{
 const s=page('Backup: protocol amendment and evidence trail','Primary outcomes, supplementary attempts and historical baseline costs stay distinct',
 'The original twelve slots remain ten valid zeros and two missing outcomes. The supplementary amendment freezes original hashes and allows Default and Bayesian one extra Scala launch each without parameter or time-limit changes. Both score zero. Primary test accounting is 0.31901342 dollars and additional accounting is 0.02054630. Hash-checked archives and indexed verifier output support the final result. The earlier Default baseline adds separate cost but not optimizer-search expenditure. No synthetic demo artifacts are used as course evidence.','supplementary_test/amendment.json; final_test_evidence/supplementary_manifest.json');
 table(s,['Phase','Outcome','Observed USD'],[['Original held-out phase','10 scored zeros; 2 missing','0.31901342'],['Supplementary Scala phase','2 scored zeros; no further retry','0.02054630'],['Original + supplements','12 filled task estimates, all zero','0.33955972']],64,184,1152,233,[330,600,222],24);
 block(s,'Reproduction artifacts','protocol.json; final_test_protocol.json\nrun_search.py; run_test.py\nsummarize_final_test.py; validation_summary.py',68,460,555,23,112);
 block(s,'Evidence provenance','Original and supplementary log archives\nSHA-256 indexed results and verifier logs\nHistorical Default baseline summaries copied',675,460,535,23,112);
 end(s,'Known limitations and protocol deviations are part of the reported result, not omitted exceptions.');
}

if(times.reduce((a,b)=>a+b,0)!==600)throw Error('Main talk must total 600 seconds');
await fs.writeFile(path.join(out,'Expanded_Speaker_Notes_and_Timing.md'),scripts.map(s=>`# ${s.n}. ${s.title}\n\n${s.sec?`Target: ${s.sec} seconds`:'Q&A / backup'}\n\n${s.notes}\n`).join('\n'));
const candidatePath=path.join(build,'candidate.pptx');await(await PresentationFile.exportPptx(deck)).save(candidatePath);
for(let i=0;i<deck.slides.items.length;i++){const png=await deck.export({slide:deck.slides.items[i],format:'png',scale:1});await fs.writeFile(path.join(build,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));}
const owners=[3,4,5,7,9,10,11,12,15,16,17,18];
const finalPath=path.join(out,'PE6203_HPO_Presentation_Expanded_v2.pptx');
const result=await finalizePresentation({workspaceDir:work,candidatePath,finalPath,pythonExecutable:runtime+'/python/python.exe',integrityValidatorPath:skill+'/container_tools/inspect_presentation_package_integrity.py',layoutValidatorPath:skill+'/container_tools/inspect_presentation_layout_geometry.py',layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',...owners.flatMap(n=>['--require-native-table-slide',String(n)])],explicitTotalSlideCount:18,requiredNativeTableOwnerSlides:owners,requiredNativeChartOwnerSlides:[8,10],materializeLiteralChartWorkbooks:true,nativeChartTargetApplication:'powerpoint',fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,receiptPath:path.join(build,'validation-v2.json')});
console.log('Final deck: '+result.finalPath);
