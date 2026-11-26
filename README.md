# 小说创作 · Novel Writing

一个面向 Codex 的中文小说创作技能。可以从一句设定写起，也可以接手已有章节，帮你规划故事、续写正文、定向改稿和检查前后矛盾。短篇不必先填表；长篇可以用可选的故事档案跨会话接力。

## 安装

从 GitHub 下载或克隆本仓库，把整个 `skills/novel-writing` 文件夹复制到项目的 `.agents/skills/`，或复制到用户级 `~/.agents/skills/` 供不同项目使用。请保留所有子目录。

例如，在本仓库根目录用 PowerShell 安装到用户级目录：

```powershell
$skillsDir = Join-Path $HOME '.agents\skills'
$target = Join-Path $skillsDir 'novel-writing'
if (Test-Path -LiteralPath $target) { throw "已存在同名技能，请先检查现有版本：$target" }
New-Item -ItemType Directory -Path $skillsDir -Force | Out-Null
Copy-Item -LiteralPath '.\skills\novel-writing' -Destination $target -Recurse
```

打开新的 Codex 对话，输入 `$novel-writing` 加上你的任务。

## 可以这样用

```text
$novel-writing 写一篇近未来短篇：一座城市把昨天的天气借给了明天。用第一人称，直接给正文。

$novel-writing 读取项目中的前三章和故事档案，续写第四章。保留原视角，不要让主角提前知道读者已经知道的事。

$novel-writing 以定稿清单中的第七章接第八章，不接重写稿。切到已认出寄信人的主角视角，沿用他上一场的叙述语气；第十二章前不揭露寄信人的身份。

$novel-writing 只检查第八章与既有章节在时间线、人物信息和伏笔上的矛盾。注明出处，先不要改稿。

$novel-writing 润色这段对话。保留情节和人物关系，用停顿和答非所问表现冲突，不添加解释性旁白。
```

默认在对话中交付；只有你要求落盘时，才写入稿件或创建故事档案。待定提案和已确认设定分开记录，避免改稿时悄悄改掉故事事实。

## 开篇与首个剧情闭环

设计、试写或审读连载开篇时，可按[开篇指南](skills/novel-writing/references/opening-arc.md)检查读者想追什么、在意谁、谁的选择改变了局面，以及正文有没有在兑现前给足依据。不要求固定章数，也不替换原有的连续性规则。

```text
$novel-writing 把这份原创设定写成连载开篇，直到第一个局部谜题得到可核对的答案。让主角自己的选择改变局面，主线谜底保留，只给正文，不更新故事档案。
```

## 长篇连续性监视者

这是写作任务内的可选角色，不会在后台监控文件。第一次可按指定章节建档；之后只归档新确认或重写的章节。档案记录人物与关键事件的关联、伏笔状态和已确定的揭晓限制，每条可追溯到原文。

```text
$novel-writing 为本书启用连续性监视者，用第一至第三章定稿创建 story-bible.md。以后每次我明确确认章节定稿时，持续更新这个档案。

$novel-writing 读 story-bible.md 和第三章末尾，续写第四章。正文先当试稿，设定和伏笔状态不入档。

$novel-writing 第四章现在定稿，以 chapters/04.md 为准。只更新 story-bible.md，不改正文。
```

换对话时打开同一小说项目，并在续写请求中指出档案。续写先读接续段，按事件编号或具体线索取档案里的少量记录，完整的 Markdown 档案保持不变，不需要重新建档。若可用 Python 3.9 或更新版本，Skill 可直接查标准档案表，并用文件指纹核对本章依赖的稿件；没有 Python 时可定点文本搜索和人工确认。只有信息缺失、稿本变更或关键条目冲突时才回查原文。补写中间章时，按章和场景取人物当时的状态，不套用后文已经发生的变化。
