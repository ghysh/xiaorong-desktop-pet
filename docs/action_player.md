# 阶段 10B：通用动作播放器

## 组件边界

- `ActionRequest` 是不可变请求，只保存稳定动作 ID、集中优先级、来源、单调时间和原因。
- `ActionArbiter` 只比较 `PetState`、优先级与剪辑打断策略，不加载图片、不播放帧、不修改状态。
- `ActionPlayer` 是无定时器的 `QObject`，保存当前剪辑、绝对开始时间、帧位置、循环和待处理边界。
- `PlaybackTimeline` 是纯 Python 时间线，负责四种循环模式和帧/循环边界。
- `ActionAssetCache` 只接受通过 ready 门禁的动作，预加载源 `QImage`，按需缓存三档 `QPixmap`。
- `AnimationController` 继续拥有唯一 30 FPS `QTimer`，每次 tick 更新行为、点击、眨眼请求与播放器。

播放器不知道 QWidget、托盘、设置、鼠标位置、提醒或窗口移动。`PetWindow` 只消费缓存好的当前覆盖帧并在正式主图之后绘制。

## 绝对时间模型

播放器使用注入的单调 `elapsed_seconds`。帧位置由 `(elapsed - clip_started) × 1000` 和每帧整数毫秒时长计算，不使用 `frame_index += 1` 作为时钟。因此延迟 tick 会直接跳到应显示的帧，不会永久拖慢剪辑；相同时间输入不会重复发出相同 `frame_changed`。

ONCE 在精确总时长结束并清空；LOOP 按指定循环次数运行；PING_PONG 使用 `0…N-1…1`，不重复两个端点；HOLD_LAST_FRAME 保持末帧直到被替换。时间校验拒绝负数、NaN、无穷值和倒退输入，并覆盖了非常大的 elapsed。

## 打断与排队

四种剪辑策略为：

- `IMMEDIATE`：高优先级请求立即切换；
- `FINISH_FRAME`：按当前帧绝对结束边界切换；
- `FINISH_CYCLE`：按当前循环结束边界切换；
- `NOT_INTERRUPTIBLE`：普通请求拒绝，停止和拖拽仍拥有全局终止权。

自主眨眼低于点击、拖拽、暂停和停止。重复眨眼请求不会堆积；点击、拖拽、隐藏、暂停和退出会清除半闭覆盖层。

## 资源门禁与缓存

运行注册同时要求 `status=ready`、`runtime_enabled=true`、`assets_complete=true`。缓存再次验证帧路径只能位于对应 `frames/`，文件必须存在、可解码、为 1024×1536 RGBA PNG 且有非空 Alpha。planned、draft、disabled、preview、diagnostics、缺帧、错误尺寸/模式和未批准来源哈希均不能进入运行注册表。

运行时注册 `blink_normal` 与 `drowsy_sleep_cycle`。动作源图在启动时各读一次；绘制 tick 不读取文件、不缩放、不计算哈希、不扫描 Alpha。`FRAME_SEQUENCE` 关键帧替换默认人物层；睡眠动作只在首次进入坐下和最终恢复正式主图时使用 140 ms 短淡化，中段关键帧始终以正常不透明度直接播放。鼻涕泡保持为独立绘制层。缓存提供 `clear_action()` 和 `clear_all()`，保留显式生命周期。

## Tick 与性能

当前顺序为：更新 BehaviorController → 更新 InteractionController → 应用状态抢占 → BlinkController 提交请求 → 仲裁 → ActionPlayer 绝对时间更新 → 计算并发出原有变换。眨眼帧改变时只通知窗口重绘。

自动测试覆盖四种循环、四种打断、延迟 tick、暂停、信号去重、资源门禁、三档缓存、单一高频 QTimer、无线程、无窗口位移及阶段 1～10A 回归。烟雾脚本为 `scripts/smoke_test_action_player.py --offscreen`。
