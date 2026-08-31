# Shopping Copilot Recording Kit

这是独立于 `Hamburgerr` 的离线录屏工具，不参与官方提交，也不连接真实 Agent、评测器、网络或模型。

## 打开与录制

1. 双击 `index.html`。
2. 浏览器设为 1920×1080、缩放 100%。
3. 操作员模式显示 frame ID 和准确英文旁白，用于彩排。
4. 正式录制按 `F` 进入无控制栏 clean capture。

不需要 Python、Node、PPT、API key 或完整商品目录。完整逐帧画面、英文稿和切屏说明见：

```text
..\Hamburgerr\demo\06-视频录制布局与路演画面设计.md
```

## 导播键

- `Space`：下一正式帧
- `Backspace`：上一正式帧
- `[` / `]`：上一段 / 下一段
- `R`：回到当前段第一帧
- `B`：跳到当前段终态
- `P`：按脚本时长自动彩排；正式录制不使用
- `F`：进入或退出 clean capture 全屏

正式顺序为 Opening → Product Loop → Buying → Browsing → Clarification → Boundary → Evidence → Value & Roadmap，共 53 帧、4:55。

## 直接打开指定帧

在本地 URL 后添加 frame ID：

```text
index.html?frame=S03-T03-P03
```

该模式隐藏操作栏，适合检查、补录或重新导出 PNG。

## PNG 备用素材

- `assets/`：独立录制包的 53 张 1920×1080 PNG。
- `../Hamburgerr/demo/video-assets/`：仓内同名镜像。
- 文件名按段、轮次、阶段排序，例如 `s03-t03-p03-slots.png`。

动态录制失败时，停止当前片段，打开 Runbook 本行对应 PNG 全屏补录。无需预建 53 个 OBS 场景；后期按 frame ID 拼接即可。

## 重新导出与验收

在本目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\export-assets.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\verify.ps1
```

导出脚本从 `index.html` 内嵌 manifest 读取全部 frame ID，先写 staging，通过后再替换两个 active PNG 目录。验收脚本检查 53 帧、五阶段、295 秒时间线、Runbook 对齐、尺寸、哈希、JavaScript 和披露边界。
