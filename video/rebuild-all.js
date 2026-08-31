// 一次性重建 index.html：扩帧、重写旁白、精简画面数据、重写渲染
// 统一用函数形式 replace，避免 $ 被当作捕获组
const fs = require('fs');
const path = require('path');
const file = path.join(path.resolve(__dirname, '..'), 'video/index.html');
let html = fs.readFileSync(file, 'utf8');
const swap = (re, gen) => { if (!re.test(html)) throw new Error('未匹配: ' + re); html = html.replace(re, gen); };

/* ---------- 1. 旁白：按帧时长分配，聚焦叙事与价值，语速 <= 2.6 词/秒 ---------- */
const N = {
  'S01-F01': 'Shopping Copilot is a conversational shopping search agent. It turns a one-off query into a shopping process you can correct.',
  'S01-F02': 'Within ten turns, it converges changing shopping intent into trustworthy product results.',
  'S01-F03': 'The hard part is not finding more products. It is that users keep adding, revising, and contradicting what they asked for.',

  'S02-F01': 'Traditional search treats every request as a static query, so an old condition can quietly outlive its welcome.',
  'S02-F02': 'We treat intent as a changing state and put the difference in one state-driven framework.',
  'S02-F03': 'Buying protects your hard constraints. Browsing protects your options. Both run on the same state.',
  'S02-F04': 'Three mechanisms do the work: slot-level update, a question that earns its turn, and controlled relaxation.',
  'S02-F05': 'Route it, update the valid slots, retrieve, verify, then recommend, clarify, or relax, and keep the trace.',
  'S02-F06': 'These are not patches for the hard cases. They run across every scenario, including the easy eighty percent.',

  'S03-T01-P01': 'Maya asks for black running shoes under one hundred dollars.',
  'S03-T01-P02': 'The system reads that as Buying and writes three hard constraints.',
  'S03-T01-P03': 'Category, colour, and budget become conditions every result must satisfy.',
  'S03-T01-P04': 'It filters first, retrieves and ranks, then verifies before anything is shown.',
  'S03-T01-P05': 'Only results that clear every hard constraint reach her.',
  'S03-T02-P01': 'Then she adds one condition: Nike only.',
  'S03-T02-P02': 'Brand joins the state. Nothing else is touched.',
  'S03-T02-P03': 'She keeps every constraint she already gave.',
  'S03-T02-P04': 'The tighter state triggers a fresh retrieval.',
  'S03-T02-P05': 'Now only legal Nike candidates come back.',
  'S03-T03-P01': 'Then she changes her mind: any brand is fine.',
  'S03-T03-P02': 'The system catches the no-preference signal on brand.',
  'S03-T03-P03': 'It clears brand only. Category, colour, and budget survive.',
  'S03-T03-P04': 'Stale results are dropped, and retrieval runs again.',
  'S03-T03-P05': 'One condition changed. She did not have to say the rest again.',

  'S04-T01-P01': 'Maya explores summer outdoor training instead.',
  'S04-T01-P02': 'Scene language routes this to Browsing.',
  'S04-T01-P03': 'The occasion is kept as context, not a hard filter.',
  'S04-T01-P04': 'It retrieves, ranks, and keeps the results diverse.',
  'S04-T01-P05': 'Tops, shorts, and breathable layers all stay in play.',
  'S04-T02-P01': 'She asks for lighter, less fitted options.',
  'S04-T02-P02': 'The route stays Browsing.',
  'S04-T02-P03': 'Style updates. The occasion stays put.',
  'S04-T02-P04': 'Soft preferences reweight the ranking without excluding anything.',
  'S04-T02-P05': 'The direction changes. She can still explore before narrowing.',

  'S05A-T01-P01': 'Maya starts with a broad request.',
  'S05A-T01-P02': 'The system reads it as Buying.',
  'S05A-T01-P03': 'But the category is too broad.',
  'S05A-T01-P04': 'It scores which missing detail would help most.',
  'S05A-T01-P05': 'So it asks one question that earns its turn.',
  'S05A-T02-P01': 'She answers: running shoes.',
  'S05A-T02-P02': 'The route holds.',
  'S05A-T02-P03': 'Category narrows from broad to specific.',
  'S05A-T02-P04': 'Retrieval resumes.',
  'S05A-T02-P05': 'One question, real convergence, no form to fill in.',

  'S05B-T01-P01': 'Maya asks for Nike shoes under five dollars.',
  'S05B-T01-P02': 'The system reads this as Buying.',
  'S05B-T01-P03': 'Budget is locked. Brand can give way.',
  'S05B-T01-P04': 'Nothing matches, so it relaxes brand and holds the budget.',
  'S05B-T01-P05': 'No legal match exists, so it explains rather than cheats.',

  'S06-F01': 'On the latest 200-session public set, HitRate at ten is 0.9600, MRR is 0.606629, mean first-hit turn is 2.585, and the composite score is 0.830289.',
  'S06-F02': 'On the same catalog, HitRate is 0.880 on 100 self-built sessions and 0.854 on 500. These test transfer, not headline.',
  'S06-F03': 'The public run recorded zero fallbacks, p95 at 48.044 milliseconds, and no external model calls.',

  'S07-F01': 'For shoppers: less repetition, local correction, results you can trust, and no quietly broken constraints.',
  'S07-F02': 'For a platform these are hypotheses worth testing: efficiency, conversion, fewer hand-offs. The roadmap starts with a live catalog.'
};

/* ---------- 2. S02 从 5 帧扩到 6 帧 ---------- */
const S02_OLD = /  \{"id":"S02-F01"[\s\S]*?\{"id":"S02-F05"[^\n]*\n/;
const S02_NEW = [
  { id: 'S02-F01', fn: 's02-f01-problem-pain.png', s: 30, e: 38, cue: 'Contrast static search with changing intent.' },
  { id: 'S02-F02', fn: 's02-f02-insight.png', s: 38, e: 46, cue: 'State the core insight.' },
  { id: 'S02-F03', fn: 's02-f03-dual-track.png', s: 46, e: 54, cue: 'Explain the two tracks.' },
  { id: 'S02-F04', fn: 's02-f04-three-mechanisms.png', s: 54, e: 62, cue: 'Preview the three mechanisms.' },
  { id: 'S02-F05', fn: 's02-f05-product-loop.png', s: 62, e: 71, cue: 'Reveal the six-step product loop.' },
  { id: 'S02-F06', fn: 's02-f06-capability-coverage.png', s: 71, e: 80, cue: 'Show capability covers every scenario.' }
].map(f => `  {"id":"${f.id}","filename":"${f.fn}","segment":"S02","segmentLabel":"Product loop","start":${f.s},"end":${f.e},"view":"flow","phase":"Static","step":${f.id.slice(-1)},"narration":"${N[f.id]}","cue":"${f.cue}"},\n`).join('');
swap(S02_OLD, () => S02_NEW);

/* ---------- 3. 其余帧旁白 ---------- */
Object.entries(N).forEach(([id, text]) => {
  if (id.startsWith('S02-F')) return;
  swap(new RegExp('("id":"' + id + '"[^}]*?"narration":")[^"]*(")'), (m, a, b) => a + text + b);
});

/* ---------- 4. ACTIONS：精简画面数据，聚焦叙事 ---------- */
const ACTIONS_NEW = `const ACTIONS={
  buy1:{session:'BUY-01',turn:1,route:'Buying',user:'I need black running shoes under $100.',prior:[],intent:{before:'Unknown',evidence:['need','shoes','under $100'],events:[],resolved:'Buying',source:'rule',changed:true},slots:{before:[],delta:[['category','∅ → running shoes','hard','added'],['color','∅ → black','hard','added'],['price_max','∅ → $100','hard','added']],effective:[['category','running shoes','hard','active'],['color','black','hard','active'],['price_max','$100','hard','fixed']]},fsm:{previous:'UNDERSTAND',event:'valid slots and budget',guard:'parse succeeded',next:'RETRIEVE',branch:'Recommend',kind:'recommend'},execution:{route:'Buying',hardFilters:['category = running shoes','color = black','price_max ≤ $100'],signals:['attribute matches','route weights'],operations:['Filter by hard constraints','Retrieve and rank','Verify and return'],verification:'legal candidates only',policy:'recommend'},response:{decision:'Recommend',text:'I will filter by category, color, and budget before ranking.',results:[['A-104','Black Road Runner · $79'],['A-118','City Pace Knit · $89'],['A-131','Everyday Sprint · $95']],trace:'Buying · 3 hard constraints · verified · recommend'}},
  buy2:{session:'BUY-01',turn:2,route:'Buying',user:'Nike only.',prior:[['user','I need black running shoes under $100.'],['agent','I will filter by category, color, and budget before ranking.']],intent:{before:'Buying',evidence:['Nike'],events:[],resolved:'Buying',source:'stable',changed:false},slots:{before:[['category','running shoes','hard','kept'],['color','black','hard','kept'],['price_max','$100','hard','fixed']],delta:[['brand','∅ → Nike','hard','added']],effective:[['category','running shoes','hard','kept'],['color','black','hard','kept'],['price_max','$100','hard','fixed'],['brand','Nike','hard','active']]},fsm:{previous:'RETRIEVE',event:'brand added to state',guard:'hard state changed',next:'ASSESS',branch:'Re-retrieve',kind:'recommend'},execution:{route:'Buying',hardFilters:['category = running shoes','color = black','price_max ≤ $100','brand = Nike'],signals:['brand attribute'],operations:['Add brand to state','Re-filter and rerank','Verify and return'],verification:'legal Nike candidates only',policy:'recommend'},response:{decision:'Recommend',text:'Brand is added. All existing hard constraints remain active.',results:[['N-204','Nike Run Swift · $92'],['N-218','Nike Road Flex · $98'],['N-231','Nike Daily Pace · $76']],trace:'Buying retained · brand added · verified · recommend'}},
  buy3:{session:'BUY-01',turn:3,route:'Buying',user:'Actually, any brand is fine.',prior:[['user','I need black running shoes under $100.'],['agent','I will filter by category, color, and budget before ranking.'],['user','Nike only.'],['agent','Brand is added. All existing hard constraints remain active.']],intent:{before:'Buying',evidence:['any brand','is fine'],events:['no_preference (brand)'],resolved:'Buying',source:'stable',changed:false},slots:{before:[['category','running shoes','hard','kept'],['color','black','hard','kept'],['price_max','$100','hard','fixed'],['brand','Nike','hard','active']],delta:[['brand','Nike → cleared','hard','cleared']],effective:[['category','running shoes','hard','kept'],['color','black','hard','kept'],['price_max','$100','hard','fixed']]},fsm:{previous:'RETRIEVE',event:'no-preference on brand',guard:'explicit no preference',next:'ASSESS',branch:'Re-retrieve',kind:'recommend'},execution:{route:'Buying',hardFilters:['category = running shoes','color = black','price_max ≤ $100'],signals:['regenerated query','attribute matches'],operations:['Clear brand only','Re-filter and rerank','Verify and return'],verification:'no conflicting brand survives',policy:'recommend'},response:{decision:'Recommend',text:'Brand is cleared. Category, color, and budget remain active.',results:[['A-104','Black Road Runner · $79'],['R-302','Black Trail Light · $88'],['C-117','Urban Pace · $69']],trace:'Buying·HR@10=0.9625 MRR=0.57754 MTTC=2.1375\\nIntent Override·HR@10=1 MRR=0.876667 MTTC=3.8',value:'One condition changes, the rest survives. Less repetition, less friction.'}},
  browse1:{session:'BROWSE-01',turn:1,route:'Browsing',user:'What should I wear for summer outdoor training?',prior:[],intent:{before:'Unknown',evidence:['what should I wear'],events:[],resolved:'Browsing',source:'rule',changed:true},slots:{before:[],delta:[['occasion','∅ → summer outdoor training','context','added']],effective:[['occasion','summer outdoor training','context','active']]},fsm:{previous:'UNDERSTAND',event:'scene request',guard:'browse signal; no exact item',next:'RETRIEVE',branch:'Recommend diverse',kind:'recommend'},execution:{route:'Browsing',hardFilters:[],signals:['occasion context','light diversity'],operations:['Keep category filter off','Retrieve and rank','Diversify'],verification:'context relevant; legal',policy:'recommend diverse'},response:{decision:'Recommend diverse',text:'I will keep the scene open and return breathable, cross-category options.',results:[['S-044','Airflow Training Tee · tops'],['S-052','Light Run Shorts · shorts'],['S-067','Breeze Layer · outer layer']],trace:'Browsing · occasion retained · cross-category response'}},
  browse2:{session:'BROWSE-01',turn:2,route:'Browsing',user:'Show me something lighter and less fitted.',prior:[['user','What should I wear for summer outdoor training?'],['agent','I will keep the scene open and return breathable, cross-category options.']],intent:{before:'Browsing',evidence:['lighter','less fitted'],events:[],resolved:'Browsing',source:'stable',changed:false},slots:{before:[['occasion','summer outdoor training','context','kept']],delta:[['style','lighter → lighter, less fitted','soft','updated']],effective:[['occasion','summer outdoor training','context','kept'],['style','lighter, less fitted','soft','updated']]},fsm:{previous:'RETRIEVE',event:'soft preference update',guard:'route unchanged; context valid',next:'ASSESS',branch:'Rerank diverse',kind:'recommend'},execution:{route:'Browsing',hardFilters:[],signals:['occasion retained','style weights updated'],operations:['Update style weights','Rerank','Diversify'],verification:'soft mismatch does not hard-exclude',policy:'recommend diverse'},response:{decision:'Recommend diverse',text:'Style is updated. The summer training context remains.',results:[['S-071','Relaxed Breeze Tee · light'],['S-083','Open-Air Jogger · loose fit'],['S-096','Summer Mesh Layer · relaxed']],trace:'Browsing·HR@10=0.975 MRR=0.57754 MTTC=2.2875',value:'Scene stays while direction changes. Explore first, then narrow.'}},
  clarify1:{session:'CLARIFY-01',turn:1,route:'Buying',user:'I want some shoes.',prior:[],intent:{before:'Unknown',evidence:['shoes'],events:[],resolved:'Buying',source:'rule',changed:true},slots:{before:[],delta:[['category','∅ → shoes','hard','broad']],effective:[['category','shoes','hard','broad']]},fsm:{previous:'ASSESS',event:'candidate space too broad',guard:'more than 10 candidates',next:'CLARIFY',branch:'Ask highest-value slot',kind:'clarify'},execution:{route:'Buying',hardFilters:['category = shoes'],signals:['candidate spread'],operations:['Inspect candidate spread','Score each missing slot','Ask the best one'],verification:'too broad to converge',policy:'clarify highest-value slot'},response:{decision:'Clarify',text:'Are you looking for running, casual, or formal shoes?',results:[['?','Highest-value missing slot'],['1','One attribute per turn'],['4','Legal response from turn 4']],trace:'Stage 3 diagnostic · 0.264985 → 0.119633 without clarification'}},
  clarify2:{session:'CLARIFY-01',turn:2,route:'Buying',user:'Running shoes.',prior:[['user','I want some shoes.'],['agent','Are you looking for running, casual, or formal shoes?']],intent:{before:'Buying',evidence:['running shoes'],events:[],resolved:'Buying',source:'stable',changed:false},slots:{before:[['category','shoes','hard','broad']],delta:[['category','shoes → running shoes','hard','answered']],effective:[['category','running shoes','hard','active']]},fsm:{previous:'CLARIFY',event:'valid answer to asked slot',guard:'specific enough to retrieve',next:'RETRIEVE',branch:'Resume retrieval',kind:'recommend'},execution:{route:'Buying',hardFilters:['category = running shoes'],signals:['category attribute'],operations:['Bind the answer','Retrieve and rank','Verify and return'],verification:'specific legal candidates',policy:'recommend'},response:{decision:'Recommend',text:'Category is now specific enough to retrieve and verify legal candidates.',results:[['R-011','Daily Runner · $72'],['R-024','Road Light · $84'],['R-039','Trail Start · $91']],trace:'Clarify → answer → state update → verified recommendation',value:'One useful question instead of a form. Real convergence.'}},
  boundary1:{session:'BOUNDARY-01',turn:1,route:'Buying',user:'I want Nike shoes under $5.',prior:[],intent:{before:'Unknown',evidence:['Nike shoes','under $5'],events:[],resolved:'Buying',source:'rule',changed:true},slots:{before:[],delta:[['category','∅ → shoes','hard','added'],['brand','∅ → Nike','hard','added'],['price_max','∅ → $5','hard','fixed']],effective:[['category','shoes','hard','active'],['brand','Nike','hard','relaxable'],['price_max','$5','hard','fixed']]},fsm:{previous:'ASSESS',event:'hard filter returns empty',guard:'empty set; buying route',next:'RELAX',branch:'Relax brand; keep budget',kind:'relax'},execution:{route:'Buying',hardFilters:['category = shoes','brand = Nike','price_max ≤ $5 (fixed)'],signals:['relaxation order'],operations:['Filter returns empty','Relax brand','Verify budget holds'],verification:'no budget-valid match remains',policy:'explain constrained response'},response:{decision:'Constrained response',text:'No budget-valid match remains, so I will explain the constraint instead of violating it.',results:[['—','No legal match'],['→','Raise budget or drop brand'],['LOCK','Budget stays fixed']],trace:'Boundary·HR@10=0.7 MRR=0.42833 MTTC=4.9',value:'No fabricated match, no broken budget.'}}
};`;
swap(/const ACTIONS=\{[\s\S]*?\n\};/, () => ACTIONS_NEW);

/* ---------- 5. flow()：六帧叙事，配置常驻底部 ---------- */
const FLOW_NEW = `function flow(frame){
  const step=frame.step;
  const loopNodes=[['User message','incomplete, added, or overridden'],['Current valid intent','route + slots + turn'],['Buying / Browsing','retrieval strategy'],['Fusion, ranking, verification','hard constraints enforced'],['Recommend / clarify / relax','policy decision'],['Verifiable result + trace','recorded for replay']];
  const mechanisms=[['Slot-level state update','revisions change only what conflicts'],['A question that earns its turn','asks what narrows the pool most'],['Controlled relaxation','empty or out-of-bounds requests']];
  const tracks=[['Buying','your hard constraints are protected'],['Browsing','your options stay open']];
  const pains=['Starts vague','Adds constraints','Changes mind','Switches from buying to browsing'];
  const titles=['Static queries miss changing intent','Intent is changing state, not a query','Two tracks, one shared state','Three mechanisms on shared state','The product loop','It runs across every scenario'];
  const panels=[
    '<div class="compare"><div class="old"><strong>Traditional search</strong>One query → one result list</div><div class="new"><strong>Real shopping behaviour</strong><div class="chips" style="margin-top:8px">'+pains.map(function(p){return '<span class="chip">'+p+'</span>'}).join('')+'</div></div></div>',
    '<div class="insight-panel"><strong>Insight</strong><p>Intent is a changing state, not a static query. One state-driven framework updates only what changed.</p></div>',
    '<div class="track-grid">'+tracks.map(function(t){return '<div class="track-card"><strong>'+t[0]+'</strong><span>'+t[1]+'</span></div>'}).join('')+'</div><p class="loop-note">Two tracks, one shared state and one decision boundary.</p>',
    '<div class="mech-grid">'+mechanisms.map(function(m,i){return '<div class="mech-card"><b>'+(i+1)+'</b><strong>'+m[0]+'</strong><span>'+m[1]+'</span></div>'}).join('')+'</div><p class="loop-note">Not three features. Three behaviours of one shared state.</p>',
    '<div class="pipeline">'+loopNodes.map(function(n){return '<div class="pipe-node on"><strong>'+n[0]+'</strong><span>'+n[1]+'</span></div>'}).join('')+'</div><div class="foundation">Design state machine: START → UNDERSTAND → RETRIEVE → ASSESS → CLARIFY / RELAX → RECOMMEND → LIMIT_RECOMMEND</div>',
    '<div class="coverage"><div class="coverage-bar"><div class="seg base">80% Buying + Browsing</div><div class="seg hard">20% Override + Boundary</div></div><p>The same mechanisms run across all 100%. The hard 20% is where you can see them most clearly.</p></div>'
  ];
  return '<section class="slide"><div class="capture-note">Promoted d4 path · explanatory product loop</div><h2>'+titles[step-1]+'</h2>'+panels[step-1]+'<div class="config-strip"><b>Active configuration:</b> offline rules · local lexical / attribute retrieval · dense=false · llm=false · intent model=off</div></section>';
}`;
swap(/function flow\(frame\)\{[\s\S]*?\n\}/, () => FLOW_NEW);

/* ---------- 6. inspector：事件为空显示 none；响应帧加一句价值 ---------- */
const EV_OLD = '<div class="info-label">Detected event</div><div class="info-value">${action.intent.events.map(esc).join(\' · \')}</div>';
const EV_NEW = '<div class="info-label">Detected event</div><div class="info-value">${action.intent.events.length?action.intent.events.map(esc).join(\' · \'):\'none\'}</div>';
if (!html.includes(EV_OLD)) throw new Error('未匹配 Detected event');
html = html.split(EV_OLD).join(EV_NEW);

const TRACE_OLD = '<div class="info"><div class="info-label">Trace summary</div><div class="info-value">${esc(action.response.trace)}</div></div>`;';
const TRACE_NEW = '${action.response.value?`<div class="info"><div class="info-label">Why it matters</div><div class="info-value value-note">${esc(action.response.value)}</div></div>`:\'\'}<div class="info"><div class="info-label">Trace summary</div><div class="info-value">${esc(action.response.trace).replace(/\\n/g,\'<br>\')}</div></div>`;';
if (!html.includes(TRACE_OLD)) throw new Error('未匹配 Trace summary');
html = html.split(TRACE_OLD).join(TRACE_NEW);

/* ---------- 7. CSS ---------- */
const CSS = `
    .insight-panel{background:var(--paper);border:1px solid var(--line);border-left:4px solid var(--blue);border-radius:8px;padding:18px 22px}.insight-panel strong{display:block;font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--blue);margin-bottom:8px}.insight-panel p{margin:0;font-size:24px;line-height:1.4;color:#385060}
    .track-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.track-card{background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:22px 24px;box-shadow:0 1px 3px rgba(19,38,49,.06)}.track-card strong{display:block;font-size:28px;margin-bottom:8px}.track-card span{font-size:19px;color:#4a5f6d}.loop-note{margin:16px 0 0;font-size:19px;color:var(--muted)}
    .mech-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.mech-card{background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:20px 22px;position:relative;box-shadow:0 1px 3px rgba(19,38,49,.06)}.mech-card b{position:absolute;top:-12px;left:18px;width:26px;height:26px;border-radius:50%;background:var(--blue);color:#fff;font-size:14px;display:grid;place-items:center}.mech-card strong{display:block;font-size:21px;margin:6px 0 8px}.mech-card span{font-size:17px;color:#4a5f6d}
    .coverage-bar{display:flex;height:56px;border-radius:8px;overflow:hidden;margin-bottom:18px}.coverage-bar .seg{display:grid;place-items:center;color:#fff;font-size:18px;font-weight:650}.coverage-bar .seg.base{background:var(--blue);flex:80}.coverage-bar .seg.hard{background:var(--orange);flex:20}.coverage p{margin:0;font-size:23px;line-height:1.45;color:#385060}
    .value-note{color:var(--green);font-weight:650}
    .baseline-panel{background:#fff;border:1px solid var(--line);border-top:5px solid var(--blue);border-radius:7px;padding:18px 22px;box-shadow:0 1px 3px rgba(19,38,49,.06)}.baseline-source{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:12px}.baseline-source strong{font-size:17px;color:var(--blue);text-transform:uppercase;letter-spacing:.07em}.baseline-source span{font-size:13px;color:var(--muted)}.baseline-table{display:grid;grid-template-columns:1.25fr .9fr .9fr .85fr;border:1px solid var(--line);border-radius:6px;overflow:hidden}.baseline-cell{min-height:62px;padding:10px 14px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);display:flex;align-items:center}.baseline-cell:nth-child(4n){border-right:0}.baseline-cell:nth-last-child(-n+4){border-bottom:0}.baseline-cell.head{min-height:38px;background:var(--teal-050);font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}.baseline-metric{font-size:16px;font-weight:750}.baseline-number{font-size:23px;font-weight:750;font-variant-numeric:tabular-nums}.baseline-number.current{color:var(--blue)}.baseline-delta{display:inline-block;padding:5px 9px;border-radius:4px;background:var(--green-bg);color:var(--green);font-size:17px;font-weight:850;font-variant-numeric:tabular-nums}.mttc-note{margin-top:12px;padding:10px 14px;border-left:4px solid var(--orange);background:var(--orange-bg);font-size:15px;color:var(--ink-2)}.mttc-note b{color:var(--orange)}
    .focus-kpis{display:grid;gap:14px;margin-top:8px}.focus-kpis.two{grid-template-columns:repeat(2,1fr)}.focus-kpis.three{grid-template-columns:repeat(3,1fr)}.focus-kpi{min-height:150px;padding:20px 22px;border:1px solid var(--line);border-radius:6px;background:var(--teal-050);display:flex;flex-direction:column;justify-content:center}.focus-kpi.green{background:var(--green-bg)}.focus-kpi strong{font-size:44px;line-height:1.05;color:var(--blue);font-variant-numeric:tabular-nums;letter-spacing:-.025em}.focus-kpi.green strong{color:var(--green)}.focus-kpi b{margin-top:9px;font-size:16px;color:var(--ink)}.focus-kpi span{margin-top:3px;font-size:13px;color:var(--muted)}.focus-note{margin-top:14px;padding:11px 14px;border-left:4px solid var(--blue);background:var(--teal-050);font-size:15px;color:var(--ink-2)}.focus-note.green{border-left-color:var(--green);background:var(--green-bg)}.runtime-config{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:12px;padding:10px 14px;border:1px solid var(--line);border-radius:5px;background:#fff;font-size:13px}.runtime-config b{color:var(--orange)}.runtime-config span{color:var(--muted)}
`;
swap(/  <\/style>/, () => CSS + '  </style>');

fs.writeFileSync(file, html, 'utf8');
console.log('index.html 重建完成');
