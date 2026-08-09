# 小融

小融是面向 Windows 10 / 11 x64 的透明桌面伙伴。当前发布版本为 **1.1.0**，正式角色资源是 `assets/fullbody/final/fullbody_runtime_master.png`；该 1024 × 1536 RGBA 主图的固定 SHA-256 为 `6FD2E4CA948E250926A22428AA633AF83F487971086ABA92B1017C3599747A64`，构建和运行过程均不得修改或重新编码它。

> 面向 GPT 和开发者的高密度项目阅读导航见 [`docs/GPT_PROJECT_CONTEXT.md`](docs/GPT_PROJECT_CONTEXT.md)。

## 当前版本

1.1.0 冻结并发布现有功能：透明无边框窗口、置顶、拖拽、三档尺寸、低风险待机变换、行为状态切换、Alpha 点击判定、点击挤压与随机对白、自然眨眼、右键菜单、系统托盘、设置和位置持久化。

最终推荐发布物：

```text
release/小融-1.1.0-win64.exe
```

它采用 PyInstaller onefile，无需安装、Python 或 Conda。发布目录同时包含极简使用说明与 SHA-256 校验文件。程序未进行数字签名，Windows 可能显示未知发布者提示。

## 开发环境与运行

- Python 3.11.15，Conda 环境 `dp`
- PySide6：窗口、托盘与设置
- Pillow：PNG/ICO 完整性检查
- pytest、Ruff、PyInstaller：测试、规范检查与发布构建

从项目根目录运行源码：

```powershell
& "D:\anaconda3\Scripts\conda.exe" run --no-capture-output -n dp python -m desktop_pet
```

正式构建：

```powershell
Set-Location "D:\DesktopPet\desktop_pet"
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\build_xiaorong_1_1_0.ps1
```

测试：

```powershell
& "D:\anaconda3\Scripts\conda.exe" run --no-capture-output -n dp python scripts\check_environment.py
& "D:\anaconda3\Scripts\conda.exe" run --no-capture-output -n dp python -m pytest tests -v
& "D:\anaconda3\Scripts\conda.exe" run --no-capture-output -n dp python -m ruff check .
```

用户设置继续保存在原有的 Windows 本地配置目录，因此显示名变更不会丢失原有尺寸、位置、置顶与动画设置。程序不会把个人设置或日志打包进 EXE。

## 运行资源边界

发布包仅包含实际运行需要的正式主图、点击对白、指定 ICO，以及已接入的 `blink_normal` 清单和四张局部眨眼覆盖帧。原始图片、候选图、诊断素材、开发文档、测试、OpenCV、NumPy 和 8 个未启用的规划动作均不进入发布包。

阶段 10A 的动作架构与规划文档仍作为后续设计依据；阶段 10B 已实现通用动作播放器和自然眨眼。阶段 10C～10G 的行走、睡眠、提醒、舞蹈与后续集成仍未实现，不属于 1.1.0。

## 项目结构

```text
src/desktop_pet/       应用源码与模块入口
tests/                 自动化回归测试
docs/                  架构、约束与阶段文档
scripts/               检查、诊断和发布辅助脚本
packaging/windows/     PyInstaller 与 Windows 元数据
assets/actions/        对白、眨眼运行素材和高级动作规划
assets/fullbody/final/ 受保护的正式角色主图
assets/icons/          当前应用图标
```

GitHub 源码仓库不跟踪 `build/`、`dist/`、`release/`、EXE、用户设置、日志、诊断图、候选图或中间处理素材。它们可以保留在本机，但不属于源码提交。
