// 同步 runbook 的预览图区块：按 manifest 更新文件名并补齐缺帧
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'video/index.html'), 'utf8');
const frames = JSON.parse(html.match(/id="frame-manifest">([\s\S]*?)<\/script>/)[1]);
const rbPath = path.join(root, 'demo/06-视频录制布局与路演画面设计.md');
let lines = fs.readFileSync(rbPath, 'utf8').split(/\r?\n/);

const idx = [];
lines.forEach((l, i) => { if (/^!\[S/.test(l)) idx.push(i); });
const start = idx[0], end = idx[idx.length - 1];
console.log('预览区: 行', start + 1, '-', end + 1, '共', idx.length, '张');

const out = frames.map(f => '![' + f.id + '](./video-assets/' + f.filename + ')');
lines.splice(start, end - start + 1, ...out);
fs.writeFileSync(rbPath, lines.join('\n'), 'utf8');
console.log('预览图已更新为', out.length, '张');
