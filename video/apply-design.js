// 设计优化：暖中性配色 + 衬线标题 + 模块化字号 + 关键布局留白
const fs = require('fs');
const path = require('path');
const file = path.join(path.resolve(__dirname, '..'), 'video/index.html');
let html = fs.readFileSync(file, 'utf8');
const must = (s) => { if (!html.includes(s)) throw new Error('未匹配: ' + s.slice(0, 60)); };

/* 1. 配色：保持变量名，换成暖中性底 + 深青蓝 + 暖橙 */
const OLD_ROOT = html.match(/:root\{[^}]*\}/)[0];
const NEW_ROOT = `:root{--ink:#241f1a;--muted:#7a7066;--line:#dcd3c6;--bg:#f4efe7;--paper:#fffcf6;--blue:#12556b;--blue-bg:#e6eff2;--orange:#b8621b;--orange-bg:#fbf0e5;--green:#3d6b52;--green-bg:#e9f2ec;--red:#a8452f;--red-bg:#fbeeeb;--dark:#1e2a30}`;
html = html.replace(OLD_ROOT, NEW_ROOT);

/* 2. 字体：标题用衬线（编辑感/人味），正文用精致无衬线 */
const OLD_BODY = 'body{background:var(--bg);color:var(--ink);font:18px/1.35 system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:0}';
const NEW_BODY = 'body{background:var(--bg);color:var(--ink);font:18px/1.45 "Aptos","Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,sans-serif;letter-spacing:-0.005em;-webkit-font-smoothing:antialiased}h1,h2,.insight-panel strong,.track-card strong,.mech-card strong,.value-group h3{font-family:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;letter-spacing:-0.015em;font-weight:600}';
must(OLD_BODY);
html = html.split(OLD_BODY).join(NEW_BODY);

/* 3. 字号：模块化比例，录屏下更清晰 */
const SIZES = [
  ['.slide h1{margin:0 0 12px;font-size:68px;line-height:1.05}', '.slide h1{margin:0 0 18px;font-size:76px;line-height:1.04}'],
  ['.slide h2{margin:0 0 18px;font-size:42px;line-height:1.12}', '.slide h2{margin:0 0 24px;font-size:48px;line-height:1.14;max-width:20ch}'],
  ['.slide .lead{max-width:1180px;margin:0;font-size:29px;color:#385060}', '.slide .lead{max-width:1140px;margin:0;font-size:31px;line-height:1.4;color:#4a423a}']
];
SIZES.forEach(([a, b]) => { must(a); html = html.split(a).join(b); });

/* 4. 布局：S02 面板留白与焦点 */
const INSIGHT_OLD = '.insight-panel p{margin:0;font-size:24px;line-height:1.4;color:#385060}';
const INSIGHT_NEW = '.insight-panel p{margin:0;font-size:30px;line-height:1.42;color:#3d352c;font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}';
must(INSIGHT_OLD);
html = html.split(INSIGHT_OLD).join(INSIGHT_NEW);

const TRACK_OLD = '.track-card strong{display:block;font-size:28px;margin-bottom:8px}.track-card span{font-size:19px;color:#4a5f6d}';
const TRACK_NEW = '.track-card strong{display:block;font-size:34px;margin-bottom:10px;color:var(--blue)}.track-card span{font-size:21px;line-height:1.45;color:#5c5349}';
must(TRACK_OLD);
html = html.split(TRACK_OLD).join(TRACK_NEW);

const COVER_OLD = '.coverage p{margin:0;font-size:23px;line-height:1.45;color:#385060}';
const COVER_NEW = '.coverage p{margin:0;font-size:28px;line-height:1.48;color:#3d352c;max-width:26ch;font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}';
must(COVER_OLD);
html = html.split(COVER_OLD).join(COVER_NEW);

/* 5. 证据页：数字等宽对齐并放大，标签字距拉开 */
const METRICS = [
  ['.metric strong{display:block;font-size:28px}', '.metric strong{display:block;font-size:34px;font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1;letter-spacing:-0.02em}'],
  ['.metric-panel h3{margin:0 0 12px;font-size:17px;color:var(--blue);text-transform:uppercase}', '.metric-panel h3{margin:0 0 14px;font-size:15px;color:var(--blue);text-transform:uppercase;letter-spacing:.09em}'],
  ['.metric span,.metric-panel p{font-size:12px;color:var(--muted)}', '.metric span,.metric-panel p{font-size:13px;line-height:1.45;color:var(--muted)}']
];
METRICS.forEach(([a, b]) => { must(a); html = html.split(a).join(b); });

fs.writeFileSync(file, html, 'utf8');
console.log('设计优化已应用');
