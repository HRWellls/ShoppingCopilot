# Git 分支协作指南

本文面向第一次使用 Git 分支协作的团队成员。项目当前使用：

- `main`：稳定主分支，只接收经过测试和评审的代码。
- `feature1_llm`：LLM 接入与调优分支，日常开发在这里进行。

## 1. 先理解三个概念

- **工作区**：电脑上正在编辑、尚未提交的文件。
- **提交（commit）**：一次有说明、有编号的代码快照。
- **分支（branch）**：指向一组提交的开发路线。

在 `feature1_llm` 上提交代码，不会改变 `main`。只有执行合并后，这些提交才会进入 `main`。

注意：**未提交的修改不完全属于某个分支**。切换分支时，它们可能一起被带过去。因此切换前必须先运行 `git status`，并提交或暂存当前修改。

## 2. 每次开始工作

进入项目目录：

```bash
cd /Users/wangminkai/Desktop/Hamburgerr
```

确认当前分支和文件状态：

```bash
git status
git branch --show-current
```

切换到 LLM 开发分支：

```bash
git switch feature1_llm
```

如果远程仓库已有新提交，拉取当前分支最新代码：

```bash
git pull --ff-only origin feature1_llm
```

看到 `Already up to date.` 表示已经是最新版本。

## 3. 修改代码并提交

完成一小块功能后，先检查修改：

```bash
git status
git diff
```

只添加本次需要提交的文件：

```bash
git add src/nlu/structured.py
git add tests/test_deepseek.py
```

不建议新手直接使用 `git add .`，因为它可能把测试输出、密钥或无关文件一起加入提交。

再次检查即将提交的内容：

```bash
git diff --staged
```

创建提交：

```bash
git commit -m "feat: add low-confidence LLM parser"
```

推荐每个提交只完成一件事情。常见提交前缀：

- `feat:` 新功能
- `fix:` 修复问题
- `test:` 增加或调整测试
- `docs:` 文档修改
- `refactor:` 不改变功能的代码整理

查看最近提交：

```bash
git log --oneline --decorate -10
```

## 4. 第一次推送新分支

第一次把 `feature1_llm` 推送到远程：

```bash
git push -u origin feature1_llm
```

设置上游后，以后在该分支只需：

```bash
git push
```

推送只是把 `feature1_llm` 上传到远程，不会自动修改远程 `main`。

## 5. 推荐的合并流程

团队协作推荐通过 GitHub Pull Request 合并：

1. 在 `feature1_llm` 完成开发、测试和提交。
2. 执行 `git push`。
3. 在 GitHub 创建从 `feature1_llm` 到 `main` 的 Pull Request。
4. 团队成员检查代码和测试结果。
5. 评审通过后，在 GitHub 页面执行合并。
6. 本地切回 `main` 并同步。

合并后同步本地主分支：

```bash
git switch main
git pull --ff-only origin main
```

然后继续开发时再切回功能分支：

```bash
git switch feature1_llm
```

## 6. 在本地合并到 main

只有团队明确决定本地合并时，才执行以下操作。

先确保功能分支没有未提交修改，并完成测试：

```bash
git switch feature1_llm
git status
python3 -m unittest discover -s tests -v
```

切换并更新主分支：

```bash
git switch main
git pull --ff-only origin main
```

合并功能分支：

```bash
git merge --no-ff feature1_llm
```

测试合并后的主分支，然后推送：

```bash
python3 -m unittest discover -s tests -v
git push origin main
```

`git merge` 是真正让功能分支代码进入 `main` 的步骤。在执行之前必须确认当前分支确实是 `main`。

## 7. main 更新后，同步到功能分支

其他成员可能已经更新了 `main`。将这些更新合入 `feature1_llm`：

```bash
git switch main
git pull --ff-only origin main
git switch feature1_llm
git merge main
```

如果没有冲突，运行测试后提交或推送即可。不要使用不理解的 `rebase` 或强制推送来代替这套流程。

## 8. 遇到合并冲突

发生冲突时，`git status` 会列出冲突文件。文件中通常出现：

```text
<<<<<<< HEAD
当前分支内容
=======
待合并分支内容
>>>>>>> main
```

处理步骤：

1. 打开每个冲突文件，决定保留哪些代码。
2. 删除 `<<<<<<<`、`=======`、`>>>>>>>` 标记。
3. 运行测试。
4. 标记冲突已解决并提交。

```bash
git add 冲突文件路径
git commit
```

如果尚未解决且希望取消这次合并：

```bash
git merge --abort
```

不确定如何选择代码时，先停止并联系修改该文件的成员，不要随意删除一侧内容。

## 9. 临时保存未完成修改

必须临时切换分支，但代码还不能提交时：

```bash
git stash push -u -m "WIP: LLM parser"
git switch main
```

回到原分支并恢复：

```bash
git switch feature1_llm
git stash pop
```

查看暂存列表：

```bash
git stash list
```

`stash` 只适合短期保存，不应代替正常提交。

## 10. 安全撤销

撤销某个文件尚未暂存的修改：

```bash
git restore 文件路径
```

把文件从暂存区移回工作区，但保留修改：

```bash
git restore --staged 文件路径
```

撤销一个已经共享或推送的提交，推荐创建反向提交：

```bash
git revert 提交编号
```

执行这些命令前先运行 `git diff` 和 `git status`。`git restore` 会丢弃对应的未提交内容。

## 11. 团队禁止事项

除非团队成员明确理解后果，否则不要执行：

```bash
git reset --hard
git push --force
git clean -fd
```

同时遵守以下规则：

- 不直接在 `main` 开发或提交。
- 不提交 API Key、密码、`api.env` 或私人数据。
- 不修改他人尚未提交的工作区文件。
- 不在测试失败时合并到 `main`。
- 不用 `git add .` 无检查地提交全部文件。

## 12. 当前项目的标准工作流

日常开发：

```bash
git switch feature1_llm
git status
# 修改代码并运行测试
git diff
git add 具体文件路径
git diff --staged
git commit -m "feat: describe the change"
git push
```

准备合并：

```bash
git status
python3 -m unittest discover -s tests -v
git push
```

随后在 GitHub 创建 `feature1_llm -> main` 的 Pull Request。确认评审和测试通过后再合并。

