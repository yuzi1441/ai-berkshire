# AI Berkshire 的 GitHub / Git 工作流程

这是一份给初学者的项目专用说明。这里的“GitHub 代码”指我们实际使用的 Git 命令，不是让你一次学会全部 Git。

## 先记住最简单的关系

Git 是电脑上的版本记录工具，GitHub 是网上保存和同步版本的地方。

    当前电脑的项目文件夹
             │
             │ git commit：保存本地版本
             │ git push：上传到 GitHub
             ▼
    GitHub 远程仓库
             │
             │ git fetch / git pull：下载到另一台电脑
             ▼
    另一台电脑

GitHub 只保存文件，不会因为 push 就自动运行复核程序。

## 一、你这个项目里的对象

### 仓库

仓库就是整个项目 “ai-berkshire”。当前电脑的目录是：

    /Users/liyuwen/Documents/ai-berkshire

GitHub 仓库是：

    https://github.com/yuzi1441/ai-berkshire

仓库里面包含代码、报告、测试、数据和多个分支。

### 远程名称

本项目有两个远程地址：

    origin    https://github.com/yuzi1441/ai-berkshire.git
    upstream  https://github.com/xbtlin/ai-berkshire.git

- “origin” 是你的 GitHub 仓库，日常 push 使用它。
- “upstream” 是原始项目仓库，一般只读，不要随便 push。

### 分支

分支是同一个仓库里的不同版本线：

    main                                      稳定主版本
    codex/dongfang-fundamental-review-pilot   当前复核工作版本

当前分支是 “codex/dongfang-fundamental-review-pilot”。它包含 main 的基础内容，以及复核程序、测试和 93 个单股票结果。

其他 “codex/...” 或 “agent/...” 分支大多是以前任务留下的历史分支，不会自动影响当前分支。

## 二、常用查看命令

### 查看当前分支

    git branch --show-current

- “git”：调用 Git。
- “branch”：处理分支。
- “--show-current”：只显示当前分支名。

### 查看当前修改

    git status

它会告诉你：

- “M”：文件被修改；
- “A”：新增文件已加入提交；
- “D”：文件被删除；
- “??”：新文件还没有被 Git 跟踪。

### 查看本地分支

    git branch

前面的 “*” 表示当前所在分支。

### 查看分支与远程关系

    git branch -vv

- “-v”：显示每个分支指向的最新提交；
- “-vv”：同时显示它跟踪的远程分支，以及是否领先或落后。

### 查看提交历史

    git log --oneline --decorate --graph --all

- “log”：查看历史；
- “--oneline”：每个提交显示一行；
- “--decorate”：显示分支名；
- “--graph”：显示分支线；
- “--all”：显示所有本地和远程跟踪分支。

### 查看当前分支比 main 多了什么

    git diff origin/main...HEAD --stat

- “origin/main”：GitHub 上 main 的远程记录；
- “HEAD”：当前分支当前所在的最新提交；
- “...” ：按共同起点比较；
- “--stat”：只显示统计，不展开全文。

## 三、开始一个新任务

如果以后开始完全新的任务，建议：

    cd /Users/liyuwen/Documents/ai-berkshire
    git switch main
    git pull --ff-only origin main
    git switch -c codex/new-task

### cd

    cd /Users/liyuwen/Documents/ai-berkshire

“cd” 是 change directory，意思是进入项目目录。Git 命令应该在项目目录中执行。

### git switch main

切换到 main。它不会删除其他分支。

### git pull --ff-only origin main

- “pull”：从远程下载并整合更新；
- “origin”：你的 GitHub 仓库；
- “main”：远程目标分支；
- “--ff-only”：只允许安全的直线更新。如果本地和远程分叉，就停止，不擅自合并。

使用 “--ff-only” 是为了避免在不了解原因时自动合并两个不同版本。

### git switch -c codex/new-task

- “switch”：切换分支；
- “-c”：create，创建新分支并立即切换；
- “codex/new-task”：新分支名。

例如：

    git switch -c codex/update-dongfang-review

## 四、修改后如何提交和上传

标准流程：

    git status
    git diff
    git add 文件路径
    git diff --cached
    git commit -m "说明这次修改"
    git push -u origin 当前分支名

### git diff

查看已经修改、但还没有放入下一次提交的内容。

### git add 文件路径

把指定文件放入下一次提交清单。例如：

    git add tools/fundamental_review_radar.py
    git add tests/test_fundamental_review_radar.py

推荐指定文件，不要一开始使用 “git add -A”，因为它会把所有新增、修改和删除一起加入。

### git diff --cached

只查看已经 git add、准备提交的内容。提交前用它检查是否混入了无关文件。

### git commit -m

    git commit -m "feat: add local fundamental review batch"

- “commit”：创建一个本地版本快照；
- “-m”：message，提供提交说明；
- 引号中的文字：这次提交做了什么。

提交只发生在当前电脑，还没有上传 GitHub。

### git push -u origin 分支名

    git push -u origin codex/dongfang-fundamental-review-pilot

- “push”：上传提交；
- “-u”：建立本地分支和远程分支的跟踪关系；
- “origin”：上传到你的 GitHub；
- 最后是要上传的分支名。

第一次使用 “-u” 后，以后通常只需：

    git push

注意：推送到工作分支不会自动修改 main，也不会自动部署 VPS，除非项目另有自动部署规则明确监听这个分支。

## 五、另一台电脑如何同步

### 另一台电脑没有项目

    git clone https://github.com/yuzi1441/ai-berkshire.git
    cd ai-berkshire
    git fetch origin
    git switch --track origin/codex/dongfang-fundamental-review-pilot

### git clone

    git clone https://github.com/yuzi1441/ai-berkshire.git

“clone” 是第一次下载整个仓库，并自动设置远程名称 origin。

### git fetch origin

    git fetch origin

“fetch” 只下载 GitHub 上的最新分支和提交信息，不修改当前文件，比较安全。

### git switch --track

    git switch --track origin/codex/dongfang-fundamental-review-pilot

“--track” 会根据远程分支创建本地分支，并让本地分支跟踪它。

### 另一台电脑已经有项目

    cd /你的路径/ai-berkshire
    git fetch origin
    git switch codex/dongfang-fundamental-review-pilot
    git pull --ff-only

这会同步当前复核分支，但不会运行全量复核程序。

如果另一台电脑有自己的未提交修改，先运行 git status，不要直接 pull 覆盖它。

## 六、当前复核分支里有什么

当前工作分支：

    codex/dongfang-fundamental-review-pilot

它相对远程 main 增加了三类内容：

1. tools/fundamental_review_radar.py

   复核程序，包含单股试点、93 只 A 股本地复核、OpenCode 模型读取、规则手动锁定、原子保存和断点重试。

2. tests/test_fundamental_review_radar.py

   测试复核范围、任务结构、模型协议和原子保存。

3. local/fundamental-review-full/*.json

   93 个独立股票结果文件，没有统一的 all.json。

这些结果文件虽然位于 local/，但本次已经加入并提交到当前分支，因此另一台电脑 pull 后可以看到它们。

## 七、原子保存是什么意思

每只股票的保存过程是：

    先写同目录临时文件
          │
    写完并 fsync
          │
    os.replace 替换正式 JSON

它保证：

- 一只股票失败，不会破坏其他股票；
- 中途中断，不会留下半个正式 JSON；
- “--resume” 可以跳过已完成结果；
- 之前失败的股票可以单独重试。

原子保存和 Git 提交不是一回事。原子保存是程序如何安全写文件；Git 提交是如何保存和同步文件。

## 八、复核命令的含义

### 单股

    python3 tools/fundamental_review_radar.py --ticker 000682.SZ --output result.json

- “python3”：使用 Python 3 运行；
- 程序路径：tools/fundamental_review_radar.py；
- “--ticker 000682.SZ”：指定股票；
- “--output result.json”：指定结果文件。

### 全量

    python3 tools/fundamental_review_radar.py --all-a-shares --repo-root . --output-dir local/fundamental-review-full --workers 4

- “--all-a-shares”：复核 93 只 A 股；
- “--repo-root .”：项目根目录是当前目录，点号代表当前目录；
- “--output-dir”：逐股票结果目录；
- “--workers 4”：最多同时处理 4 只。

另一台电脑如果只想查看结果，不要执行全量命令。同步分支不会自动运行它。

### 断点继续

    python3 tools/fundamental_review_radar.py --all-a-shares --repo-root . --output-dir local/fundamental-review-full --workers 4 --resume

“--resume” 会跳过完整结果，只重试之前标记为 error 的股票。

## 九、什么时候合并到 main

正常关系是：

    工作分支 → push → GitHub Pull Request → 检查 → 合并到 main

当前复核分支可以独立查看和同步，但还不等于已经合并进 main。

没有明确确认时，不要使用下面这些高风险命令：

    git push --force
    git reset --hard
    git checkout -- 文件名

它们可能覆盖或丢失其他修改。

## 十、每天只记住这几条

    git status
    git add 文件名
    git commit -m "说明"
    git push
    git pull --ff-only

它们分别是：

    status  看当前状态
    add     选择要保存的文件
    commit  保存到本地历史
    push    上传到 GitHub
    pull    从 GitHub 下载

分支的核心理解是：

    main = 稳定版本
    工作分支 = 当前任务的独立版本
    commit = 一个保存点
    GitHub = 远程同步位置

