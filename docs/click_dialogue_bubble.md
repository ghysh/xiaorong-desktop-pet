# 阶段 10B-0：单击随机对白气泡

## 功能范围

本阶段仅为角色可见 Alpha 区域的有效左键单击增加随机对白气泡。一次有效单击同时保留原有 260 ms `CLICK_REACTION` 挤压反馈。气泡不是 `PetState`、`ActionClip` 或点击子状态，不改变行为状态机，也不加入动作帧、声音、网络或窗口自动移动。

## 对白文件与只读规则

运行路径由 `desktop_pet.paths.CLICK_DIALOGUE_FILE` 统一解析为 `assets/actions/click_reply/dialogue.txt`，支持项目目录外运行、editable install 及后续 frozen 资源根目录。运行代码没有开发机绝对路径。

`DialogueRepository` 每个进程只读取文件一次并缓存不可变 `tuple`：

- 一行始终是一句对白，`#` 不是注释；
- 去除行首尾空白，保留句子内部空格和中文标点；
- 忽略空行，不拆分句内标点；
- 先严格尝试 `utf-8-sig`，失败后严格尝试 `gb18030`；
- 不使用系统默认编码或 `errors="ignore"`；
- 不修改、补写、删除或重排源文件。

文件缺失、不可读、编码失败或没有非空对白时，应用仅输出一次明确警告并禁用气泡。原 Alpha 点击、拖拽和点击挤压仍可工作，不会生成虚假默认对白。运行中删除文件不会影响已缓存内容；文本变更需重启应用才会重新读取。

## 随机选择

`DialogueSelector` 把仓库结果复制为不可变元组，使用自己的 `random.Random`，不会读取或修改全局随机状态。生产环境由 `secrets.randbits(64)` 生成一次 64 位 seed；测试可注入固定 seed。只在有效点击时选择，多于一句时从排除上一索引的候选中选择，保证不立即重复；只有一句时始终返回该句。seed 仅用于诊断，不进入设置文件。

## 有效点击与 CLICK_REACTION

唯一判定仍位于原有 `PetWindow` 和 `InteractionController` 链路。`character_clicked` 只在左键按下和释放均命中 Alpha >= 16、移动距离小于 `QApplication.startDragDistance()`、按住不超过 500 ms、未拖拽、未打开右键菜单且状态不是 `PAUSED`/`STOPPED` 时，在释放阶段发出一次。

透明留白、拖拽释放、右键、长按、暂停和停止均不发出信号。`click_reaction_enabled=false` 时仍可完成内部手势识别，但 `InteractionController` 不进入 `CLICK_REACTION`，`DialogueController` 也不显示气泡；拖拽不受影响。本阶段不改变 settings schema，未来可再拆分独立 `dialogue_enabled` 设置。

## 气泡窗口与样式

应用只创建一个可复用 `DialogueBubble(QWidget)`。窗口 flags 为 `FramelessWindowHint | Tool | WindowDoesNotAcceptFocus`，并随桌宠设置同步 `WindowStaysOnTopHint`。窗口启用 `WA_TranslucentBackground`、`WA_ShowWithoutActivating`、`WA_TransparentForMouseEvents` 和 `NoFocus`，因此没有标题栏、任务栏入口、键盘焦点、鼠标菜单或托盘图标，也不会调用 Win32 API。

气泡使用 `QPainter` 绘制浅灰紫半透明背景、柔和灰紫 1 像素边框、14 像素圆角和方向可变的 11 像素尾部；文字为深灰色常规字重。程序优先选用系统已有的 `Microsoft YaHei UI`、`Microsoft YaHei`、`Noto Sans SC` 或 `SimHei`，不打包字体文件。

`QTextLayout` 按字体真实度量执行 `WrapAtWordBoundaryOrAnywhere`，支持中文无空格换行和中英文混排，不按字符数估算宽度。默认总宽度为 120～320 逻辑像素，高度随内容变化；异常超长文本仅在 UI 显示层省略并警告，不修改仓库原文。布局只在文字变化时重算，绘制帧不会重新解析文本。

## 定位、多屏与三档尺寸

锚点来自 `PetWindow.alpha_bounds_window` 的实际人物 Alpha 包围框，而不是透明窗口中心。候选顺序为上方居中、左上、右上、左侧、右侧和下方；选择第一个能完整进入当前屏幕 `availableGeometry()` 且保留 12 像素边距的位置。全部候选不足时将位置限制到可用区域，并按气泡与人物的相对方向调整尾部。

屏幕通过角色区域中心选择，中心不在屏幕时选择与人物交叠面积最大的屏幕。算法保留真实屏幕原点，因此支持负坐标副屏、任务栏可用区域、100%～200% 高 DPI 逻辑像素，以及 240×360、280×420、320×480 三档桌宠尺寸。

`PetWindow` 在 `moveEvent`、`resizeEvent`、常规 `showEvent` 和 `hideEvent` 发出低频事件。气泡只在桌宠移动、尺寸变化、位置恢复/重置或屏幕几何变化时重新定位，不逐帧轮询。桌宠隐藏会立即隐藏气泡并停止计时；再次显示不会恢复旧对白。改变置顶 flags 会保留同一气泡、当前文字、位置和剩余时间，且不触发桌宠暂停/恢复逻辑。

## 自动隐藏、连续点击与生命周期

气泡持有唯一一个 4500 ms `singleShot QTimer`。新点击在同一窗口中更新文字、重算布局和位置并重启此计时器，不叠加窗口或定时器。自动隐藏、禁用点击反馈、桌宠隐藏和应用退出都会停止计时器；退出还会关闭气泡。实现没有线程、`sleep()`、网络、逐帧磁盘读写或第二个高频定时器。

## 自动验证与诊断

`scripts/render_dialogue_bubble_diagnostics.py` 生成短句、中英文混排、长中文、屏幕边界、负坐标副屏、三档尺寸和浅/深桌面诊断图至 `assets/analysis/dialogue/`。这些文件不是运行资源。

`scripts/smoke_test_click_dialogue.py --offscreen` 使用临时对白文件，覆盖透明区域拒绝、可见像素点击、同一实例更新、计时器重启、移动/三档尺寸跟随、隐藏和无残留退出。专项自动化测试覆盖仓库编码/缓存/只读、局部随机、布局、定位、点击集成、设置和生命周期；阶段 1～10B 既有测试继续全量运行。

## 真实桌面验收与已知限制

自动测试可以验证结构、几何和资源完整性，但自然视觉、真实前台焦点、DPI/多显示器切换、托盘交互以及长时间 CPU/内存仍需用户运行 `run.ps1` 体验确认。

当前限制：对白仅在启动时读取，修改文本后需重启；没有对白分类或情绪标签；没有语音、输入框或对话历史。本阶段没有新增眨眼、行走、睡眠、提醒或舞蹈，也没有重新执行 PyInstaller。
