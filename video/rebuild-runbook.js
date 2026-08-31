const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'video/index.html'), 'utf8');
const frames = JSON.parse(html.match(/id="frame-manifest">([\s\S]*?)<\/script>/)[1]);
const rbPath = path.join(root, 'demo/06-视频录制布局与路演画面设计.md');
const lines = fs.readFileSync(rbPath, 'utf8').split(/\r?\n/);

// 1. 解析现有表格行 -> ID => {desc, note}
const map = {};
lines.forEach(l => {
  const m = l.match(/^\| (\d+:\d+-\d+:\d+) \| `([^`]+)` \| `([^`]+)` \| ([^|]*)\| ([^|]*)\| ([^|]*)\| ([^|]*)\|$/);
  if (m) map[m[2]] = { desc: m[4].trim(), note: m[7].trim() };
});

// 2. 画面说明的全局替换（代码口径已变）
const rep = (s) => (s || '')
  .replace(/本地检索/g, '属性检索')
  .replace(/Turn execution FSM/g, '设计状态机')
  .replace(/FSM broad-space guard/g, '状态守卫')
  .replace(/FSM 显示/g, '状态转移显示')
  .replace(/FSM 从 CLARIFY 返回/g, '状态从 CLARIFY 返回')
  .replace(/FSM 分支/g, '状态分支')
  .replace(/style\/fit/g, 'style')
  .replace(/lighter\/less fitted/g, 'lighter, less fitted')
  .replace(/Branch reason 为 Ask category/g, 'Branch reason 为 Ask highest-value slot');

// 3. S02 六帧重写（帧内容已重构）
const s02 = {
  'S02-F01': { desc: '传统搜索 `One query → one result set` 与真实购物四个痛点并列出现。', note: '问题与痛点建立；按 `Space`；失败用本行 PNG。' },
  'S02-F02': { desc: '洞察面板高亮：意图是变化的状态，不是静态查询。', note: '核心洞察可见；按 `Space`；失败用本行 PNG。' },
  'S02-F03': { desc: '双轨卡片出现，Buying 强调精度，Browsing 强调上下文与多样性。', note: '双轨差异清晰；按 `Space`；失败用本行 PNG。' },
  'S02-F04': { desc: '三项机制卡片出现：槽位级状态更新、信息增益澄清、受控放宽。', note: '三项机制完整；按 `Space`；失败用本行 PNG。' },
  'S02-F05': { desc: '六步产品闭环全部点亮，末步为可验证结果与轨迹记录。', note: '闭环六步完整；按 `Space`；失败用本行 PNG。' },
  'S02-F06': { desc: '80/20 覆盖条出现，强调能力贯穿全部 100% 场景。', note: '能力覆盖说明可见；按 `]` 进入 Buying；失败用本行 PNG。' }
};

const ft = (s) => Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');

const rows = frames.map((f, i) => {
  const src = s02[f.id] || { desc: rep(map[f.id] && map[f.id].desc), note: rep(map[f.id] && map[f.id].note) };
  const action = i === 0 ? '打开页面' : (f.segment !== frames[i - 1].segment ? ']' : 'Space');
  const actCell = i === 0 ? action : '`' + action + '`';
  return '| ' + ft(f.start) + '-' + ft(f.end) + ' | `' + f.id + '` | `' + f.filename + '` | ' + src.desc + ' | ' + f.narration + ' | ' + actCell + ' | ' + src.note + ' |';
});

// 4. 替换表格区间
const start = lines.findIndex(l => /^\| \d+:\d+-\d+:\d+ \|/.test(l));
let end = start;
for (let i = start; i < lines.length; i++) {
  if (/^\| \d+:\d+-\d+:\d+ \|/.test(lines[i])) end = i;
}
console.log('表格区间: 行', start + 1, '-', end + 1, '| 原行数', end - start + 1, '-> 新行数', rows.length);
lines.splice(start, end - start + 1, ...rows);
fs.writeFileSync(rbPath, lines.join('\n'), 'utf8');
console.log('已写入 runbook');
