// 覆盖式导出 54 帧 PNG：execFileSync + 每张 30s 超时 + 失败重试 2 次 + 实时进度
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const os = require('os');

const root = path.resolve(__dirname, '..');
const videoDir = path.join(root, 'video');
const index = path.join(videoDir, 'index.html');
const assets = path.join(videoDir, 'assets');
const mirror = path.join(root, 'demo/video-assets');
const edge = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

const html = fs.readFileSync(index, 'utf8');
const frames = JSON.parse(html.match(/id="frame-manifest">([\s\S]*?)<\/script>/)[1]);
const baseUri = 'file:///' + index.replace(/\\/g, '/');

if (!fs.existsSync(edge)) { console.error('未找到 Edge:', edge); process.exit(1); }
fs.mkdirSync(assets, { recursive: true });
fs.mkdirSync(mirror, { recursive: true });

function shot(id, filename) {
  const profile = path.join(os.tmpdir(), 'sc-assets-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8));
  const target = path.join(assets, filename);
  const url = baseUri + '?frame=' + encodeURIComponent(id);
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      execFileSync(edge, [
        '--headless=new', '--disable-gpu', '--hide-scrollbars',
        '--window-size=1920,1080',
        '--user-data-dir=' + profile,
        '--screenshot=' + target,
        url
      ], { stdio: 'ignore', timeout: 30000 });
      if (fs.existsSync(target) && fs.statSync(target).size > 1000) {
        try { fs.copyFileSync(target, path.join(mirror, filename)); } catch (e) {}
        return true;
      }
      if (fs.existsSync(target)) fs.rmSync(target, { force: true });
    } catch (e) {
      // retry
    }
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch (e) {}
  }
  return false;
}

let ok = 0, bad = [];
frames.forEach((f, i) => {
  if (shot(f.id, f.filename)) ok++;
  else bad.push(f.id);
  process.stdout.write('\r进度: ' + (i + 1) + '/' + frames.length + ' 成功:' + ok);
});

console.log('\n\n成功', ok, '/', frames.length);
if (bad.length) { console.log('失败帧:', bad.join(', ')); }
