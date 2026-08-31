// 按 verify 的 2.6 词/秒上限重写旁白：价值说明与证据交给画面，旁白只念核心句
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const file = path.join(root, 'video/index.html');
let html = fs.readFileSync(file, 'utf8');

const N = {
  'S01-F01': 'Shopping Copilot is a conversational shopping search agent.',
  'S01-F02': 'Within at most ten turns, it converges a dynamically changing shopping intent into trustworthy product results.',
  'S01-F03': 'This is a backend agent; the challenge evaluates retrieval, ranking, and dialogue decisions, not a frontend interface.',

  'S02-F01': 'Traditional search treats each request as a static query; real shoppers start vague, add constraints, or change their minds.',
  'S02-F02': 'Our design treats intent as a changing state and builds the difference on a state-driven framework.',
  'S02-F03': 'Buying prioritizes precision; Browsing preserves context and diversity. Both share one state and decision boundary.',
  'S02-F04': 'Three mechanisms operate on that shared state: slot-level update, information-gain clarification, controlled relaxation.',
  'S02-F05': 'The loop routes, updates valid slots, retrieves, verifies hard constraints, then recommends, clarifies, or relaxes.',
  'S02-F06': 'These run across all scenarios, not just the hard twenty percent where their value is most visible.',

  'S03-T01-P01': 'Maya asks for black running shoes under one hundred dollars.',
  'S03-T01-P02': 'Rule evidence resolves the route to Buying.',
  'S03-T01-P03': 'Category, colour, and budget enter state as hard constraints.',
  'S03-T01-P04': 'It filters to the legal subset, retrieves by attribute, then reranks.',
  'S03-T01-P05': 'Only candidates satisfying every hard constraint reach the response.',
  'S03-T02-P01': 'On turn two, Maya adds one condition: Nike only.',
  'S03-T02-P02': 'The route stays Buying; no destructive event is detected.',
  'S03-T02-P03': 'Brand is added; every earlier constraint stays.',
  'S03-T02-P04': 'The stricter state triggers a fresh retrieval and rerank.',
  'S03-T02-P05': 'The response now contains legal Nike candidates only.',
  'S03-T03-P01': 'Maya changes her mind: any brand is fine.',
  'S03-T03-P02': 'A no-preference event is detected, targeting the brand slot.',
  'S03-T03-P03': 'Brand is cleared; category, colour, and budget stay.',
  'S03-T03-P04': 'Stale candidates are invalidated, then retrieval reruns.',
  'S03-T03-P05': 'This is state update, not history concatenation. The rest survives.',

  'S04-T01-P01': 'Maya explores summer outdoor training wear.',
  'S04-T01-P02': 'Scene language resolves the route to Browsing.',
  'S04-T01-P03': 'The occasion is retained as context, not a hard filter.',
  'S04-T01-P04': 'It retrieves, reranks, and diversifies the results.',
  'S04-T01-P05': 'Tops, shorts, and breathable layers stay discoverable.',
  'S04-T02-P01': 'She asks for lighter, less fitted options.',
  'S04-T02-P02': 'The route stays Browsing.',
  'S04-T02-P03': 'Style updates while the occasion stays.',
  'S04-T02-P04': 'Soft weights are updated; diversity is preserved.',
  'S04-T02-P05': 'The direction changes; scene relevance remains.',

  'S05A-T01-P01': 'Maya begins with a broad request.',
  'S05A-T01-P02': 'Rule evidence resolves the route to Buying.',
  'S05A-T01-P03': 'The category is too broad.',
  'S05A-T01-P04': 'It scores each missing slot.',
  'S05A-T01-P05': 'It asks the highest-value question.',
  'S05A-T02-P01': 'Maya answers: running shoes.',
  'S05A-T02-P02': 'Buying remains the stable route.',
  'S05A-T02-P03': 'Category is bound from broad to specific.',
  'S05A-T02-P04': 'Retrieval resumes.',
  'S05A-T02-P05': 'Verified results return; information gain, not guessing.',

  'S05B-T01-P01': 'Maya requests Nike shoes under five dollars.',
  'S05B-T01-P02': 'Rule evidence resolves this as Buying.',
  'S05B-T01-P03': 'Budget is fixed; brand is relaxable.',
  'S05B-T01-P04': 'It relaxes brand, then colour, then category synonym.',
  'S05B-T01-P05': 'No legal match remains, so it explains the constraint.',

  'S06-F01': 'On the latest 200-session public set, HitRate at ten is 0.9600, MRR is 0.606629, mean first-hit turn is 2.585, and the composite score is 0.830289.',
  'S06-F02': 'On the same catalog, HitRate is 0.880 on 100 self-built sessions and 0.854 on 500. These are generalization checks, not replacements.',
  'S06-F03': 'The public run recorded zero fallbacks, with response p95 at 48.044 milliseconds and no external model-call cost.',

  'S07-F01': 'Less repetition, local correction, trustworthy results, no silent constraint violation. Platform outcomes stay hypotheses.',
  'S07-F02': 'The roadmap is dynamic catalog, pricing consistency, then online experiments.'
};

let changed = 0, missing = [];
Object.entries(N).forEach(([id, text]) => {
  const re = new RegExp('("id":"' + id + '"[^}]*?"narration":")([^"]*)(")');
  if (re.test(html)) { html = html.replace(re, (m, a, b, c) => a + text + c); changed++; }
  else missing.push(id);
});
fs.writeFileSync(file, html, 'utf8');
console.log('已更新旁白', changed, '帧');
if (missing.length) console.log('未匹配:', missing.join(','));
