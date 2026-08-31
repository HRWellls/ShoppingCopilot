// 画面做减法：证据去技术前缀、执行步骤压到 3 步、价值链改为一句价值点
const fs = require('fs');
const path = require('path');
const file = path.join(path.resolve(__dirname, '..'), 'video/index.html');
let html = fs.readFileSync(file, 'utf8');

const PATCH = {
  buy1: {
    evidence: "['need','shoes','under $100']",
    operations: "['Filter by hard constraints','Retrieve and rank','Verify and return']"
  },
  buy2: {
    evidence: "['Nike']",
    operations: "['Add brand to state','Re-filter and rerank','Verify and return']"
  },
  buy3: {
    evidence: "['any brand','is fine']",
    operations: "['Clear brand only','Re-filter and rerank','Verify and return']",
    value: 'One condition changes, the rest survives. Less repetition, less friction.'
  },
  browse1: {
    evidence: "['what should I wear']",
    operations: "['Keep category filter off','Retrieve and rank','Diversify']"
  },
  browse2: {
    evidence: "['lighter','less fitted']",
    operations: "['Update style weights','Rerank','Diversify']",
    value: 'Scene stays while direction changes. Explore first, then narrow.'
  },
  clarify1: {
    evidence: "['shoes']",
    operations: "['Inspect candidate spread','Score each missing slot','Ask the best one']"
  },
  clarify2: {
    evidence: "['running shoes']",
    operations: "['Bind the answer','Retrieve and rank','Verify and return']",
    value: 'One useful question instead of a form. Real convergence.'
  },
  boundary1: {
    evidence: "['Nike shoes','under $5']",
    operations: "['Filter returns empty','Relax brand','Verify budget holds']",
    value: 'No fabricated match, no broken budget.'
  }
};

let n = 0;
Object.entries(PATCH).forEach(([key, p]) => {
  // 定位该 action 的整段
  const re = new RegExp('(\\b' + key + ':\\{session:[\\s\\S]*?\\n)');
  const m = html.match(re);
  if (!m) { console.log('未匹配 action:', key); return; }
  let seg = m[1];

  seg = seg.replace(/evidence:\[[^\]]*\]/, 'evidence:' + p.evidence);
  seg = seg.replace(/operations:\[[^\]]*\]/, 'operations:' + p.operations);
  // 移除不再展示的 stateChange
  seg = seg.replace(/,?stateChange:'[^']*'/, '');
  // valueChain -> value
  if (p.value) {
    seg = seg.replace(/valueChain:\[[^\]]*\]/, "value:'" + p.value.replace(/'/g, "\\'") + "'");
  } else {
    seg = seg.replace(/,?valueChain:\[[^\]]*\]/, '');
  }

  html = html.replace(re, seg);
  n++;
});

fs.writeFileSync(file, html, 'utf8');
console.log('已精简', n, '个 action');
