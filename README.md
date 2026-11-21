# 小说创作 · Novel Writing

一个面向 Codex 的中文小说创作技能。可以从一句设定写起，也可以接手已有章节，帮你规划故事、续写正文、定向改稿和检查前后矛盾。短篇不必先填表；长篇可以用可选的故事档案跨会话接力。

## 安装

从 GitHub 下载或克隆本仓库，把整个 `skills/novel-writing` 文件夹复制到项目的 `.agents/skills/`，或复制到用户级 `~/.agents/skills/` 供不同项目使用。请保留 `references/`、`assets/` 和 `agents/` 子目录。

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

$novel-writing 只检查第八章与既有章节在时间线、人物信息和伏笔上的矛盾。注明出处，先不要改稿。

$novel-writing 润色这段对话。保留情节和人物关系，用停顿和答非所问表现冲突，不添加解释性旁白。
```

技能无需额外依赖。默认在对话中交付；只有你要求落盘时，才写入稿件或创建故事档案。待定提案和已确认设定分开记录，避免改稿时悄悄改掉故事事实。
