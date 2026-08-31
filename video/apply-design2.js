// 第二轮设计修正：配色收拢为两个色族、架构追踪放大、FSM 去深蓝底、流程节点平衡
const fs = require('fs');
const path = require('path');
const file = path.join(path.resolve(__dirname, '..'), 'video/index.html');
let html = fs.readFileSync(file, 'utf8');
const must = (s) => { if (!html.includes(s)) throw new Error('未匹配: ' + s.slice(0, 70)); };

/* 1. 配色：两个色族（深青蓝 / 暖橙）+ 纯度分级，中性色略带主色色调 */
const OLD_ROOT = html.match(/:root\{[^}]*\}/)[0];
const NEW_ROOT = `:root{` +
  `--teal-900:#0b3745;--teal-700:#12556b;--teal-600:#1a6b85;--teal-300:#8fbccb;--teal-100:#dceaf0;--teal-050:#eef5f8;` +
  `--amber-800:#8a4710;--amber-600:#b8621b;--amber-300:#dfb98c;--amber-100:#f7e9d9;` +
  `--ink:#1c272b;--ink-2:#43565c;--muted:#74878d;--line:#cddade;--bg:#f1f5f6;--paper:#fdfefe;` +
  `--blue:var(--teal-700);--blue-bg:var(--teal-100);` +
  `--orange:var(--amber-600);--orange-bg:var(--amber-100);` +
  `--green:#3d6b52;--green-bg:#e8f1ec;` +
  `--red:#9c4a33;--red-bg:#f6ebe7;` +
  `--dark:var(--teal-900)}`;
html = html.replace(OLD_ROOT, NEW_ROOT);

/* 2. 架构追踪：文字整体放大，说明栏不再挤在正中 */
const ARCH = [
  ['.arch-label{margin-bottom:10px;color:var(--muted);font-size:12px}',
   '.arch-label{margin-bottom:12px;color:var(--muted);font-size:14px}'],
  ['.arch-note{margin-top:11px;padding:9px 11px;border-left:4px solid var(--blue);background:#fff;font-size:12px;color:#415663}',
   '.arch-note{margin-top:14px;padding:13px 16px;border-left:4px solid var(--teal-600);background:var(--paper);font-size:17px;line-height:1.5;color:var(--ink-2)}'],
  ['.arch-node strong{display:block;font-size:13px;line-height:1.15}',
   '.arch-node strong{display:block;font-size:15px;line-height:1.2;color:var(--ink)}'],
  ['.arch-node small{display:block;margin-top:5px;color:var(--muted);font-size:10px;line-height:1.2}',
   '.arch-node small{display:block;margin-top:6px;color:var(--muted);font-size:12px;line-height:1.3}'],
  ['.arch-node{position:relative;min-height:83px;padding:10px 8px;border:1px solid var(--line);border-top:4px solid #aebac1;border-radius:5px;background:#fff;text-align:left}',
   '.arch-node{position:relative;min-height:88px;padding:12px 10px;border:1px solid var(--line);border-top:4px solid var(--teal-300);border-radius:6px;background:var(--paper);text-align:left}'],
  ['.arch-node.active{border-color:var(--blue);border-top-color:var(--blue);background:#dceefa;box-shadow:inset 0 0 0 1px var(--blue)}',
   '.arch-node.active{border-color:var(--teal-600);border-top-color:var(--teal-700);background:var(--teal-100);box-shadow:inset 0 0 0 1px var(--teal-600)}'],
  ['.arch-node.empty{border-color:#d99b97;border-top-color:var(--red);background:var(--red-bg)}',
   '.arch-node.empty{border-color:#dcb3a6;border-top-color:var(--red);background:var(--red-bg)}'],
  ['.arch-node.relax{border-color:#e4ab84;border-top-color:var(--orange);background:var(--orange-bg)}',
   '.arch-node.relax{border-color:var(--amber-300);border-top-color:var(--orange);background:var(--orange-bg)}']
];
ARCH.forEach(([a, b]) => { must(a); html = html.split(a).join(b); });

/* 3. FSM lane：去掉深蓝底，改为浅色卡片行 */
must('.fsm-lane{grid-column:1/-1;display:grid;grid-template-columns:1fr auto 1.3fr auto 1fr 1.2fr;align-items:center;gap:8px;padding:13px 17px;background:var(--dark);color:#fff}');
html = html.split('.fsm-lane{grid-column:1/-1;display:grid;grid-template-columns:1fr auto 1.3fr auto 1fr 1.2fr;align-items:center;gap:8px;padding:13px 17px;background:var(--dark);color:#fff}')
  .join('.fsm-lane{grid-column:1/-1;display:grid;grid-template-columns:1fr auto 1.3fr auto 1fr 1.2fr;align-items:center;gap:11px;padding:15px 18px;background:var(--teal-050);border:1px solid var(--teal-300);border-radius:8px;color:var(--ink)}');

const FSM = [
  ['.fsm-box{min-width:0;padding:8px 9px;border:1px solid #4f6571;border-radius:4px;background:#1f3946}',
   '.fsm-box{min-width:0;padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:var(--paper)}'],
  ['.fsm-box strong{display:block;font-size:10px;color:#a9bec8;text-transform:uppercase}',
   '.fsm-box strong{display:block;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em}'],
  ['.fsm-box span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:13px}',
   '.fsm-box span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:15px;color:var(--ink)}']
];
FSM.forEach(([a, b]) => { must(a); html = html.split(a).join(b); });

/* 4. 流程节点：从 5 列改为 3 列，6 个节点排成 3×2 平衡 */
must('.pipeline{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin-top:18px}');
html = html.split('.pipeline{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin-top:18px}')
  .join('.pipeline{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:18px}');

const PIPE = [
  ['.pipe-node{min-height:118px;padding:15px;border:1px solid var(--line);border-top:5px solid #8fa0aa;border-radius:6px;background:#fff}',
   '.pipe-node{min-height:104px;padding:16px 18px;border:1px solid var(--line);border-top:5px solid var(--teal-300);border-radius:7px;background:var(--paper);display:flex;flex-direction:column;justify-content:center}'],
  ['.pipe-node.on{border-top-color:var(--blue);background:var(--blue-bg)}',
   '.pipe-node.on{border-top-color:var(--teal-700);background:var(--teal-050)}'],
  ['.pipe-node.buy{border-top-color:var(--orange);background:var(--orange-bg)}',
   '.pipe-node.buy{border-top-color:var(--amber-600);background:var(--amber-100)}'],
  ['.pipe-node strong{display:block;font-size:18px;margin-bottom:7px}',
   '.pipe-node strong{display:block;font-size:19px;margin-bottom:8px;color:var(--ink)}'],
  ['.pipe-node span{font-size:14px;color:var(--muted)}',
   '.pipe-node span{font-size:14px;line-height:1.4;color:var(--muted)}']
];
PIPE.forEach(([a, b]) => { must(a); html = html.split(a).join(b); });

/* 5. 状态链说明：与流程节点拉开距离，改为辅助信息样式 */
must('.foundation{grid-column:1/-1;padding:12px;background:var(--dark);color:#fff;text-align:center;border-radius:5px;font-weight:750}');
html = html.split('.foundation{grid-column:1/-1;padding:12px;background:var(--dark);color:#fff;text-align:center;border-radius:5px;font-weight:750}')
  .join('.foundation{margin-top:22px;padding:14px 18px;background:var(--teal-050);border:1px dashed var(--teal-300);border-radius:7px;text-align:center;color:var(--ink-2);font-size:15px;line-height:1.5;letter-spacing:.01em}');

fs.writeFileSync(file, html, 'utf8');
console.log('第二轮设计修正已应用');
