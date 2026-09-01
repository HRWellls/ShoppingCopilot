// verify.ps1 的等价校验（Node 版），用于在不依赖 PowerShell 回显的情况下确认一致性
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');

const html = fs.readFileSync(path.join(root, 'video/index.html'), 'utf8');
const frames = JSON.parse(html.match(/<script type="application\/json" id="frame-manifest">\s*([\s\S]*?)\s*<\/script>/)[1]);
const rbPath = path.join(root, 'demo/06-视频录制布局与路演画面设计.md');
const rbLines = fs.readFileSync(rbPath, 'utf8').split(/\r?\n/);

const fails = [];
const fail = (m) => fails.push(m);
const ft = (s) => Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');

// --- 帧契约（对应 Assert-FrameContract）---
if (frames.length !== 54) fail(`帧数 ${frames.length}，应为 54`);
const dupId = frames.map(f => f.id).filter((v, i, a) => a.indexOf(v) !== i);
if (dupId.length) fail(`重复帧 ID: ${dupId[0]}`);
const dupFile = frames.map(f => f.filename).filter((v, i, a) => a.indexOf(v) !== i);
if (dupFile.length) fail(`重复文件名: ${dupFile[0]}`);
if (frames[0].start !== 0) fail('首帧必须从 0:00 开始');
frames.forEach((f, i) => {
  if (!f.id || !f.filename || !f.narration) fail(`字段缺失: ${f.id}`);
  if (f.end <= f.start) fail(`时长非正: ${f.id}`);
  if (i > 0 && f.start !== frames[i - 1].end) fail(`时间线断裂: ${f.id}`);
  const rate = f.narration.trim().split(/\s+/).length / (f.end - f.start);
  if (rate > 2.6) fail(`语速超限 ${rate.toFixed(2)} 词/秒: ${f.id}`);
});
if (frames[frames.length - 1].end !== 295) fail(`末帧必须结束于 4:55，实际 ${frames[frames.length - 1].end}`);

// --- runbook 对齐（对应 Assert-RunbookAlignment）---
const rows = [];
rbLines.forEach(l => {
  const m = l.match(/^\| (\d+:\d+-\d+:\d+) \| `([^`]+)` \| `([^`]+)` \| ([^|]*)\| ([^|]*)\| ([^|]*)\| ([^|]*)\|$/);
  if (m) rows.push({ Time: m[1], Id: m[2], Filename: m[3], Narration: m[5].trim(), EntryAction: m[6].trim() });
});
if (rows.length !== frames.length) fail(`runbook 表格 ${rows.length} 行，应为 ${frames.length}`);
frames.forEach((f, i) => {
  const r = rows[i];
  if (!r) return fail(`runbook 缺少第 ${i + 1} 行 (${f.id})`);
  if (r.Id !== f.id) fail(`runbook ID 不符 #${i}: ${r.Id} != ${f.id}`);
  if (r.Filename !== f.filename) fail(`runbook PNG 不符 ${f.id}: ${r.Filename}`);
  const t = `${ft(f.start)}-${ft(f.end)}`;
  if (r.Time !== t) fail(`runbook 时间不符 ${f.id}: ${r.Time} != ${t}`);
  if (r.Narration !== f.narration) fail(`runbook 旁白不符 ${f.id}`);
  const expected = i === 0 ? '打开页面' : (f.segment !== frames[i - 1].segment ? '`]`' : '`Space`');
  if (r.EntryAction !== expected) fail(`runbook 操作不符 ${f.id}: ${r.EntryAction} != ${expected}`);
});
const embeds = rbLines.filter(l => /^!\[S/.test(l));
if (embeds.length !== 54) fail(`runbook 嵌入预览 ${embeds.length} 张，应为 54`);

// --- 禁用词扫描 ---
const banned = ['summer wedding', '68.675', '300 → 40 → 8', 'total cost is zero', 'always returns the closest product'];
banned.forEach(b => { if (html.includes(b)) fail(`命中禁用词: ${b}`); });

console.log('=== 校验结果 ===');
console.log('帧数:', frames.length, '| runbook 行数:', rows.length, '| 嵌入预览:', embeds.length);
console.log('语速范围:', Math.min(...frames.map(f => f.narration.trim().split(/\s+/).length / (f.end - f.start))).toFixed(2),
            '-', Math.max(...frames.map(f => f.narration.trim().split(/\s+/).length / (f.end - f.start))).toFixed(2), '词/秒');
if (fails.length) { console.log('\n❌ 失败 ' + fails.length + ' 项:'); fails.forEach(f => console.log('  - ' + f)); process.exit(1); }
else console.log('\n✅ 全部通过');
