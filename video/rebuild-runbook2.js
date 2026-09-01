const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'video/index.html'), 'utf8');
const frames = JSON.parse(html.match(/id="frame-manifest">([\s\S]*?)<\/script>/)[1]);
const rbPath = path.join(root, 'demo/06-视频录制布局与路演画面设计.md');
let lines = fs.readFileSync(rbPath, 'utf8').split(/\r?\n/);

const ft = (s) => Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');

// 找出当前连续的表格行
const idx = [];
lines.forEach((l, i) => { if (/^\| \d+:\d+-\d+:\d+ \|/.test(l)) idx.push(i); });
const start = idx[0], end = idx[idx.length - 1];
console.log('当前表格行:', start + 1, '-', end + 1, '共', idx.length);

// 按 segment 重建带分组的表格
const segs = [];
frames.forEach(f => {
  const last = segs[segs.length - 1];
  if (!last || last.key !== f.segment) segs.push({ key: f.segment, label: f.segmentLabel, rows: [], s: f.start, e: f.end });
  else last.e = f.end;
  segs[segs.length - 1].rows.push(f);
});

const out = ['| 时间 | Frame | PNG | 画面和技术重点 | Exact English voiceover | 进入操作 | 预期、下一步和恢复 |',
             '|---|---|---|---|---|---|---|'];
const tableLines = lines.slice(start, end + 1);

segs.forEach((sg, si) => {
  if (si > 0) out.push('', '### Segment ' + (si + 1) + ' · ' + sg.label + ' · ' + ft(sg.s) + '-' + ft(sg.e), '');
  sg.rows.forEach(f => {
    const row = tableLines.find(l => l.indexOf('`' + f.id + '`') >= 0);
    if (row) out.push(row); else console.log('!! 未找到行', f.id);
  });
});

lines.splice(start, end + 1 - start, ...out);
fs.writeFileSync(rbPath, lines.join('\n'), 'utf8');
console.log('segment 分组:', segs.map(s => s.key + '(' + s.rows.length + ')').join(' '));
console.log('已写入 runbook，总行数', lines.length);
