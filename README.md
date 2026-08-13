# 小融

“小融”是一款面向 Windows 10 / 11 x64 的透明桌面宠物。当前正式版本为 **1.2.0**。

正式角色资源为 `assets/fullbody/final/fullbody_runtime_master.png`。该 1024 × 1536 RGBA 主图的固定 SHA-256 为：

```text
6FD2E4CA948E250926A22428AA633AF83F487971086ABA92B1017C3599747A64
```

构建和运行过程不得修改、覆盖或重新编码该图片。

> 面向 GPT 和开发者的项目阅读导航见 [`docs/GPT_PROJECT_CONTEXT.md`](docs/GPT_PROJECT_CONTEXT.md)。

## 下载与使用

普通用户只需要：

1. 下载 `小融-1.2.0-win64.exe`。
2. 双击 EXE。
3. 桌宠会直接出现在桌面上。

无需安装 Python、Conda 或任何第三方依赖，也不需要打开命令行。发布目录只有一个单文件程序：

```text
release/
└─ 小融-1.2.0-win64.exe
```

程序未进行数字签名，Windows 可能显示“未知发布者”提示。

## 当前功能

- 透明、无边框、始终置顶的桌宠窗口。
- 左键拖拽与多显示器位置恢复。
- 基于角色 Alpha 通道的有效点击判定，透明区域不会被当作角色点击。
- 单击角色随机显示中文对白气泡，支持颜文字保护、整体居中和屏幕边缘自适应。
- 单击挤压反馈与低风险待机变换。
- 自然眨眼动画。
- 自主行为状态机，以及唯一 30 FPS 动画更新计时器。
- `drowsy_sleep_cycle` 自主打瞌睡动作：盘腿坐下、闭眼睡眠、轻微点头、苏醒、起身、伸懒腰、打哈欠、揉眼并恢复默认站姿。
- 独立于人物 PNG 的动漫鼻涕泡动画，可随睡眠点头帧的鼻尖锚点移动。
- 右键菜单和系统托盘共享操作状态。
- `自主动作 → 打瞌睡 → 开 / 关 / 演示`；开关会持久化，演示不会改变持久化状态。
- 小、默认、大三档显示尺寸，以及置顶、动画、互动和行为设置。
- 桌宠位置、显示器、尺寸、自主打瞌睡开关等设置持久化。
- 系统托盘显示、隐藏、设置、重置位置和安全退出。

设置写入当前 Windows 用户可写的本地配置目录，不写入 EXE、PyInstaller 临时解压目录或程序所在目录，因此不需要管理员权限。

## 基本操作

- 左键单击角色：显示随机对白并触发点击反馈。
- 按住左键拖动：移动桌宠。
- 右键角色：打开功能菜单。
- 右键托盘图标：打开共享菜单。
- 完全退出：选择“退出桌宠”。

## 发布内容边界

v1.2.0 使用 PyInstaller onefile。EXE 只内置当前运行所需资源：

- 正式角色主图。
- `blink_normal` manifest 和 4 张眨眼帧。
- `drowsy_sleep_cycle` manifest 及其当前引用的动作帧。
- 单击对白文本与对白气泡 PNG。
- 正式 ICO 图标。
- PySide6 实际运行需要的 Qt DLL、Windows platform plugin 和图片解码组件。

不会打包测试、文档、脚本、Git 数据、缓存、日志、诊断图片、原始故事板、image_gen 中间产物、淘汰候选图、`source_notes.md`、旧发布物或尚未启用的规划动作资源。

## 源码开发

开发环境要求 Python 3.11 和 Conda 环境 `dp`。普通用户不需要执行本节命令。

安装开发依赖：

```powershell
conda run -n dp python -m pip install -r requirements-dev.txt
```

运行源码：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\DesktopPet\desktop_pet\run.ps1"
```

也可以在已经打开的 PowerShell 窗口中运行：

```powershell
& "D:\DesktopPet\desktop_pet\run.ps1"
```

`run.ps1` 会自动切换到项目目录、查找 Conda，并使用 `dp` 环境启动小融。底层等价启动命令为：

```powershell
conda run -n dp python -m desktop_pet
```

测试和代码检查：

```powershell
conda run -n dp python -m pytest tests -q
conda run -n dp python -m ruff check .
git diff --check
```

正式 Windows 构建：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\build_xiaorong_1_2_0.ps1
```

该入口会校验版本与资源、运行测试和静态检查、执行 PyInstaller onedir/onefile 构建、隔离路径烟雾测试、发布内容审计，并生成 `release/小融-1.2.0-win64.exe`。

## 项目结构

```text
src/desktop_pet/       应用源码与入口
tests/                 自动化回归测试
docs/                  架构与开发文档
scripts/               检查、诊断和发布脚本
packaging/windows/     PyInstaller、Windows manifest 与版本资源
assets/actions/        对白、眨眼、打瞌睡和规划动作素材
assets/fullbody/final/ 受保护的正式角色主图
assets/icons/          正式应用图标
```

行走、自动桌面移动、提醒和舞蹈仍属于后续规划，不作为 v1.2.0 已完成功能。

## 后续路线图

- 10A：高级交互架构和动作素材规范，已完成。
- 10B：通用动作播放、自然眨眼和有效点击对白，已完成。
- 10C：左右行走、转身和桌面自主移动，规划中。
- 10D：更通用的坐下、睡眠和苏醒动作库，规划中；v1.2.0 已独立实现 `drowsy_sleep_cycle`。
- 10E：喝水和休息提醒，规划中。
- 10F：用户可选舞蹈动作库，规划中。
- 10G：高级动作整合、长期稳定性和性能优化，规划中。
