// 从 manifest 重新生成 runbook 表格：旁白严格取 manifest，画面说明与备注沿用现有映射
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'video/index.html'), 'utf8');
const frames = JSON.parse(html.match(/id="frame-manifest">([\s\S]*?)<\/script>/)[1]);
const rbPath = path.join(root, 'demo/06-视频录制布局与路演画面设计.md');
const lines = fs.readFileSync(rbPath, 'utf8').split(/\r?\n/);

// 现有表行的画面说明 / 备注
const map = {};
lines.forEach(l => {
  const m = l.match(/^\| \d+:\d+-\d+:\d+ \| `([^`]+)` \| `([^`]+)` \| ([^|]*)\| ([^|]*)\| ([^|]*)\| ([^|]*)\|$/);
  if (m) map[m[1]] = { desc: m[3].trim(), note: m[6].trim() };
});

const ft = (s) => Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
const segs = [];
frames.forEach(f => {
  const last = segs[segs.length - 1];
  if (!last || last.key !== f.segment) segs.push({ key: f.segment, label: f.segmentLabel, rows: [], s: f.start, e: f.end });
  else last.e = f.end;
  segs[segs.length - 1].rows.push(f);
});

const out = ['| 时间 | Frame | PNG | 画面和技术重点 | Exact English voiceover | 进入操作 | 预期、下一步和恢复 |',
             '|---|---|---|---|---|---|---|'];
segs.forEach((sg, si) => {
  if (si > 0) out.push('', '### Segment ' + (si + 1) + ' · ' + sg.label + ' · ' + ft(sg.s) + '-' + ft(sg.e), '');
  sg.rows.forEach(f => {
    const src = map[f.id] || { desc: '（待补）', note: '按 `Space`；失败用本行 PNG。' };
    const act = out.length <= 2 && si === 0 ? '打开页面' : (f.segment !== (frames[frames.indexOf(f) - 1] || {}).segment ? ']' : 'Space');
    const actCell = f === frames[0] ? '打开页面' : '`' + act + '`';
    out.push('| ' + ft(f.start) + '-' + ft(f.end) + ' | `' + f.id + '` | `' + f.filename + '` | ' + src.desc + ' | ' + f.narration + ' | ' + actCell + ' | ' + src.note + ' |');
  });
});

const idx = [];
lines.forEach((l, i) => { if (/^\| \d+:\d+-\d+:\d+ \|/.test(l)) idx.push(i); });
// 表格从表头上一行开始（表头行不被正则匹配），回退两行以覆盖表头
const tStart = idx[0], tEnd = idx[idx.length - 1];
lines.splice(tStart, tEnd - tStart + 1, ...out);
fs.writeFileSync(rbPath, lines.join('\n'), 'utf8');
console.log('表格已重建，帧数', frames.length);
