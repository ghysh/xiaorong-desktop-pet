# 阶段 10A：高级互动架构

## 当前架构审计

| 层 | 当前职责 | 10A 结论 |
|---|---|---|
| `PetWindow` | 缓存正式主图、Alpha 命中、绘制、拖拽、菜单入口 | 不加入动作播放器、提醒或窗口运动逻辑 |
| `AnimationController` | 唯一 30 FPS `QTimer`，组合待机、行为、拖拽和点击变换 | 未来可驱动 `ActionPlayer.update(elapsed)`，本阶段不改 |
| `AnimationTransform` | 不可变局部偏移、缩放、旋转 | 继续服务轻量变换，不承载逐帧素材 |
| `BehaviorController` | 无定时器；高层状态、自动调度和生命周期 | 未来只选择高层意图，不保存动作帧索引 |
| `InteractionController` | 无定时器；Alpha 点击反馈及拖拽抢占 | 未来发出动作请求，拖拽保持全局抢占 |
| `UserSettings` / `SettingsService` | 不可变设置、显式持久化 | 10A 不增加提醒或动作设置字段 |
| UI `ActionRegistry` | 窗口与托盘共享九个 `QAction` | 10A 不加入舞蹈菜单；未来共享舞蹈动作入口 |

正式素材仍是 `assets/fullbody/final/fullbody_runtime_master.png`。高级动作规划不改变当前 `PetState`、运行入口、窗口位置、菜单、设置或发布包。

## 四层边界

### PetState

表示高层、可观察的行为阶段，例如未来的 `WALKING`、`SLEEPING`、`DANCING`。不能把 `walk_left_loop`、`turn_right` 或每支舞分别塞入枚举，否则转换表和优先级会随素材数量膨胀。10A 不增加任何运行状态。

### ActionClip

表示具体播放内容：帧、时长、循环、锚点、打断策略和来源哈希。它是不可变、Qt-free 数据，不知道窗口、菜单或调度器。当前 planned manifest 不能转换为 `ActionClip`。

### ActionPlayer（阶段 10B）

未来只负责当前剪辑、帧索引、帧剩余时间、循环/往返、事件、打断边界、预加载和缓存。它复用现有动画 tick，不创建第二个 30 FPS 定时器，不移动 QWidget。

### WindowMotionController（阶段 10C）

未来只负责行走期间的 QWidget 坐标、速度、`availableGeometry()`、负坐标副屏、边缘转身和拖拽抢占。它不选择动作、不绘制图片、不管理提醒。

### ReminderController（阶段 10E）

未来只负责下一事件时间、静默时段、延后、当天暂停和持久化，并发出提醒请求。使用低频 single-shot 或绝对下次时间，不参与 30 FPS 绘制。

## 请求与仲裁流程

1. 用户输入、自动行为或提醒控制器产生 `ActionRequest`（未来类型）。
2. 单一仲裁器比较集中定义的 `ActionPriority`。
3. 全局规则先处理 `STOPPED`、`PAUSED`、`DRAGGING`；剪辑策略只决定其余请求在当前帧或当前循环何时切换。
4. `BehaviorController` 记录高层状态；`ActionPlayer` 记录具体剪辑；两者不互相复制状态。
5. 行走剪辑的步态事件交给 `WindowMotionController`；播放器本身不直接移动窗口。
6. 绘制层只消费缓存好的当前图像和现有变换。

优先级从高到低为：停止、暂停、拖拽、用户舞蹈、提醒展示、睡眠转换、自主行走、自主睡眠、点击反馈、眨眼、待机。退出可打断一切；拖拽可打断行走、睡眠和舞蹈；自动行为不能覆盖用户动作。

## 分阶段接入

- 10B：实现播放器和眼部覆盖层，仍不移动窗口。
- 10C：新增高层行走状态、左右/转身剪辑及独立窗口运动控制器。
- 10D：新增坐下、睡眠、醒来高层流程。
- 10E：新增低频提醒控制器和设置迁移。
- 10F：把已批准舞蹈接入共享 UI ActionRegistry。
- 10G：整合、长期测试、资源预算审计并重新打包。

每阶段必须重新验证正式母版哈希、单一高频定时器、拖拽/退出抢占和 planned/ready 资源门禁。
