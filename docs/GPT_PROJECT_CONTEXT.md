# 小融项目上下文

## 项目定位

小融是使用 Python 3.11 和 PySide6 开发的 Windows 桌面宠物。仓库面向源码阅读、测试和继续开发，不存放 EXE、构建缓存、用户配置或日志。

## 当前功能

- 透明无边框、始终置顶的桌宠窗口
- 三档尺寸和左键拖拽
- Alpha 可见像素点击检测
- 呼吸、浮动、轻摇等低风险变换动画
- 行为状态机与拖拽优先级
- 点击挤压反馈和随机对白气泡
- `blink_normal` 自然眨眼
- 右键菜单、系统托盘、设置和位置持久化

## 核心入口

- `src/desktop_pet/__main__.py`
- `src/desktop_pet/app.py`

## 核心模块

- `ui/`：透明窗口、绘制、菜单、托盘和设置界面
- `animation/`：唯一高频动画控制器、缓动与变换
- `behavior/`：状态、调度与动画配置
- `interaction/`：拖拽、Alpha 命中和点击反馈
- `dialogue/`：对白读取、选择、气泡及生命周期
- `actions/`：ActionClip 清单、缓存、仲裁与 ActionPlayer
- `blink/`：自然眨眼调度
- `settings/`：设置模型、服务与 INI 持久化

## 正式角色素材

运行时唯一正式全身角色主图：

`assets/fullbody/final/fullbody_runtime_master.png`

SHA-256：

`6FD2E4CA948E250926A22428AA633AF83F487971086ABA92B1017C3599747A64`

该文件不得修改、重新编码、压缩或替换。角色身份、不对称发型、红色装饰、服装、比例与脚底锚点均应保持一致。

## 对白

`assets/actions/click_reply/dialogue.txt`

规则：一行一句；运行时只读并按进程缓存。修改对白属于单独的内容变更，不应与无关代码修改混合。

## 动画架构

`AnimationController` 持有唯一的高频 30 FPS `QTimer`。`ActionPlayer` 使用同一时间源推进动作，不应创建第二个高频 timer，也不应逐帧读取或缩放磁盘素材。运行时当前只注册 `blink_normal`；其余动作 Manifest 是禁用的规划资料。

## 高级互动计划

- 10A：ActionClip、ActionPlayer、优先级和资源规范已经建立
- 10B：通用动作播放与自然眨眼已经实现
- 10C：左右独立行走、转身和窗口移动
- 10D：盘腿坐姿、睡眠与唤醒
- 10E：喝水和休息提醒
- 10F：用户选择的舞蹈动作
- 10G：高级互动整合、长期测试和优化

10C～10G 尚未实现，不得从目录中的规划 Manifest 推断为已发布功能。

## 重要设计约束

- 左右动作不得自动镜像；角色设计包含有意义的不对称特征。
- 拖拽优先级高于自主行为，交互结束后再恢复状态机控制。
- 不逐帧读取磁盘；图片解码与尺寸缓存集中管理。
- 用户设置、日志、源码资源和构建产物相互分离。
- frozen 路径由 `src/desktop_pet/paths.py` 统一解析，运行时不得依赖开发机绝对路径。
- 显示名为“小融”，内部 Python 包名和历史配置目录标识继续保持稳定。

## 开发环境

Conda 环境：`dp`

本地项目路径示例：`D:\DesktopPet\desktop_pet`

该路径只用于开发命令示例，不应成为运行时依赖。常用检查：

```powershell
& "D:\anaconda3\Scripts\conda.exe" run --no-capture-output -n dp python -m pytest tests -q
& "D:\anaconda3\Scripts\conda.exe" run --no-capture-output -n dp python -m ruff check .
```

## 建议阅读顺序

1. `README.md`
2. 本文件
3. `src/desktop_pet/app.py`
4. `src/desktop_pet/ui/pet_window.py`
5. `src/desktop_pet/animation/controller.py`
6. `src/desktop_pet/behavior/controller.py`
7. `src/desktop_pet/actions/` 与 `docs/advanced_interaction_architecture.md`
8. 对应模块的 `tests/`
