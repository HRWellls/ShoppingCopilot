# Shopping Copilot 后续 Demo 指导

## 1. Demo 目标

这次视频不是展示一段静态聊天，而是让观众看懂：

1. Shopping Copilot 是 TechJam Conversational E-Commerce Search Challenge 的 hackathon 成果；
2. 它如何处理不完整需求、多轮补充和用户改口；
3. 它如何在 Buying 和 Browsing 两种任务之间切换；
4. 它如何用公开集指标证明结果和效率。

建议成片时长为 **4～6 分钟**。视频要像一次产品演示，而不是代码教学。

## 2. 录制前准备

### 2.1 检查环境

在项目根目录打开终端，确认分支和工作区状态：

```bash
git status
git branch --show-current
```

确保没有 API key、私有数据或不应公开的本地路径出现在终端和录屏中。不要展示 `.runtime` 中的内部轨迹、模型缓存或私有评测文件。

### 2.2 准备 Python 环境

如果尚未创建环境：

```bash
/opt/anaconda3/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

如果团队使用其他 Python 3.10+ 环境，只要能够运行下面的命令即可。

### 2.3 确认目录文件

确认 `data/catalog.jsonl` 已存在。比赛目录是只读数据，视频中不要展示或上传完整目录文件。

## 3. 推荐视频结构和台词

### 0:00～0:30：开场定位

画面：项目名称、比赛名称和一句话问题定义。

建议台词：

> Shopping Copilot 是我们参加 TechJam Conversational E-Commerce Search Challenge 的成果。比赛要求 Agent 在最多 10 轮对话中，从 50,000 个服饰、鞋类和珠宝商品中找到用户真正想要的商品。我们的重点是让 Agent 能理解用户、处理改口，并在合适的时机推荐。

### 0:30～1:20：架构总览

画面：展示 `demo/01-项目现有架构.md` 中的流程图，或制作一张简洁的幻灯片。

建议台词：

> 系统先判断用户是在购买还是浏览，再把需求保存成可更新的状态。随后按对应路径检索和排序；候选过宽时提出一个具体问题，候选足够集中时直接返回 Top 10。每轮结果都经过目录合法性校验。

不要在这一段展开 Python 类名、索引实现或模型参数。

### 1:20～2:20：场景一，Buying

画面：终端或简单调用界面，展示三轮消息。

推荐操作内容：

```text
I need black running shoes under $100.
Nike only.
Actually any brand is fine.
```

讲解重点：

- 第一轮提取品类、颜色和预算；
- 第二轮增加品牌条件；
- 第三轮只清除品牌条件，其他有效条件继续保留；
- 结果列表保持合法、去重，并且最多 10 个商品。

### 2:20～3:10：场景二，Browsing

画面：重新开始一个独立会话，避免沿用前一场景状态。

推荐操作内容：

```text
What should I wear for a summer wedding?
Show me something less formal.
```

讲解重点：

- 系统识别为探索型需求；
- 保留“夏季婚礼”上下文；
- “不那么正式”改变风格方向，而不是清空整段历史；
- 结果强调相关性和选择差异。

### 3:10～3:50：场景三，主动澄清

画面：从一个过于宽泛的请求开始。

```text
I want some shoes.
```

讲解重点：

- 系统不会连续问一串问题；
- 它选择一个最可能缩小候选范围的属性；
- 当前结果方向仍然可见，用户不会感觉被流程阻塞。

### 3:50～4:40：评测结果

在项目根目录运行公开集评测：

```bash
python3 -m scripts.run_public_set_local --profile d4
```

建议录制命令和最终 JSON 摘要，重点展示：

```text
Hit Rate@10       0.9600
MRR               0.606629
MTTC              2.585
TechnicalScore    0.830289
p95               68.675 ms
```

说明：TechnicalScore 是比赛定义的综合指标，不要把它说成“准确率”。同时说明 p95 低于 120 ms 的演示预算。

如果完整评测耗时较长，可以提前运行并在视频中展示已生成的结果摘要；但不要伪造实时输出，也不要修改评测器或公开标签。

### 4:40～5:20：收尾

建议台词：

> Shopping Copilot 的核心不是让模型多说话，而是让每一轮对话都推动搜索更接近用户目标。当前成果已经在公开集达到 TechnicalScore 0.830289；后续可以接入商品详情、库存和真实用户体验，但本次 hackathon 的 headless Agent 目标已经完整实现。

## 4. 实际录屏操作建议

### 4.1 录屏工具

可使用 macOS 自带“屏幕截图”录制、OBS Studio 或团队熟悉的录屏工具。推荐：

- 画面比例 16:9；
- 1080p；
- 终端字体放大到观众可读；
- 麦克风单独录音，避免键盘声盖过讲解；
- 关闭通知、聊天窗口和含个人信息的浏览器标签。

### 4.2 操作顺序

1. 先录一遍无旁白彩排，确认命令、数据路径和会话都能跑通。
2. 每个场景开始前执行一次新的 `reset`，明确说明“这是一个新会话”。
3. 输入消息时不要快速连按，给观众留出阅读时间。
4. 输出出现后停留 2～3 秒，再解释结果变化。
5. 最后统一展示评测命令和指标，不要在每个场景中重复跑完整 200 样本评测。

### 4.3 画面中应该出现什么

- 项目名称和比赛名称；
- 用户消息与 Agent 回复；
- Top 10 商品 ID 或商品摘要；
- Buying / Browsing 的路径差异；
- 最终评测指标。

### 4.4 画面中不要出现什么

- API key、`api.env` 内容或个人目录；
- 私有评测标签、ground truth 或未公开数据；
- 充满调试日志的代码窗口；
- 未解释的异常堆栈；
- 第三方受版权保护的商品图片、品牌素材或音乐。

## 5. YouTube 发布的真实操作

### 5.1 导出视频

剪辑完成后导出为：

- MP4；
- H.264 视频编码；
- 1080p；
- 帧率与录屏一致；
- 音频  AAC，采样率 48 kHz。

文件名建议：

```text
shopping-copilot-techjam-demo.mp4
```

### 5.2 上传步骤

1. 登录团队负责的 YouTube 账号。
2. 点击右上角 **Create → Upload videos**。
3. 选择导出的 MP4 文件。
4. 标题建议：`Shopping Copilot | TechJam Conversational E-Commerce Search Challenge Demo`。
5. 描述中写清项目定位、比赛名称、核心能力、公开集指标和 GitHub 仓库链接。
6. 添加缩略图，突出产品名和“Conversational Shopping Agent”，避免使用未经授权的品牌图。
7. Audience 选择是否面向儿童时，按团队账号实际情况填写；本项目不是儿童内容。
8. 在 **Checks** 页面确认没有版权或音频问题。
9. 可见性先选择 **Unlisted**，让团队成员完整观看并检查链接。
10. 确认字幕、声音、画面和链接无误后，改为 **Public** 并发布。

### 5.3 建议的视频描述模板

```text
Shopping Copilot is our hackathon submission for the TechJam
Conversational E-Commerce Search Challenge.

It helps shoppers refine incomplete requests through multi-turn dialogue,
routes Buying and Browsing intent differently, handles preference overrides,
and ranks products from a read-only catalog of 50,000 items.

Public-set results:
- Hit Rate@10: 0.9600
- MRR: 0.606629
- MTTC: 2.585
- TechnicalScore: 0.830289
- Response p95: 68.675 ms

Repository: <填入 GitHub 仓库链接>
```

### 5.4 发布后检查

用未登录窗口或手机网络打开公开视频，检查：

- 视频是否公开可播放；
- 开头 30 秒是否说清比赛和成果；
- 终端文字是否可读；
- 链接是否正确；
- 没有露出 API key、私有数据或内部调试信息；
- YouTube 自动字幕是否基本准确。

把最终公开视频链接记录到团队交付文档和 Devpost 描述中。不要只保存本地草稿链接。

## 6. 录制故障处理

| 情况 | Demo 操作 |
|---|---|
| 启动较慢 | 提前启动 Agent，正式录制时从已就绪状态开始，并在旁白中说明初始化只发生一次 |
| 某轮返回异常 | 停止录制，重置会话后重新演示；不要把异常堆栈剪成“成功结果” |
| 目录不存在 | 按 README 准备 `data/catalog.jsonl`，不要使用未经验证的替代目录 |
| 网络或 API 不可用 | 使用默认离线配置；本项目的规则和本地检索路径可以独立运行 |
| 输出太小看不清 | 放大终端字体或录制局部窗口，不要用低分辨率压缩视频 |

## 7. 给 Demo 同学的最后提醒

这是一场产品成果演示，不是算法答辩。每个操作都要回答一个产品问题：

- 用户刚才表达了什么？
- Agent 记住了什么？
- 为什么现在要追问或推荐？
- 结果和比赛指标有什么关系？

只要观众能清楚看到“需求变化 → 状态变化 → 结果变化 → 指标证明”，这次 Demo 就完成了最重要的任务。
