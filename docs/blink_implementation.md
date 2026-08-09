# 阶段 10B：局部眼部眨眼实现

## 素材与制作方式

正式母版始终为只读 `assets/fullbody/final/fullbody_runtime_master.png`，SHA-256 为 `6FD2E4CA948E250926A22428AA633AF83F487971086ABA92B1017C3599747A64`。覆盖层使用同一 1024×1536 RGBA 画布，大部分像素完全透明。

批准的诊断范围为源坐标 `x=350..540, y=175..292`。实际非零 Alpha 仅覆盖双眼局部，不触及鼻、嘴、脸部边缘或画布边缘。详细左右眼多边形、羽化半径和每帧 Alpha 包围框见 `assets/actions/blink/diagnostics/blink_eye_region.json`。

素材由 `scripts/build_blink_overlay_assets.py` 在本地构建：睁眼帧无损提取母版中的原眼像素；半闭/闭眼在每只眼内部做边缘固定的局部眼睑形变，上下眼睑向闭合线展开，而多边形四周保持源像素连续，再在源坐标手工定义抗锯齿深色睫线。没有调用在线服务、外部角色素材、自动镜像或整脸重绘。OpenCV 仅供开发脚本执行预生成形变，运行时不导入。

| 文件 | SHA-256 | Alpha 包围框 |
|---|---|---|
| `blink_open.png` | `DAB50EA979C8BA9A6A142E123AAB9181BE44CC8FD1D914B244AB79FEA466674E` | `(374, 197, 523, 280)` |
| `blink_half_closed.png` | `980AA5F080E33BCEFCF9963760262B605881E7B2757AAB0B5A56185DCBDE3974` | `(371, 194, 525, 269)` |
| `blink_closed.png` | `2CD5105770EDCB7769C094B99592B06F845501684F4DBCAE64B3E8A184F336C2` | `(371, 194, 526, 283)` |
| `blink_half_open.png` | `980AA5F080E33BCEFCF9963760262B605881E7B2757AAB0B5A56185DCBDE3974` | `(371, 194, 525, 269)` |

半开与半闭内容当前相同，分别保留文件名以便后续独立微调。睁眼覆盖合成与正式母版像素完全一致。

## 帧序列与调度

运行序列为睁眼 35 ms → 半闭 35 ms → 闭眼 55 ms → 半开 35 ms → 睁眼 35 ms，总时长 195 ms，模式为 ONCE、策略为 IMMEDIATE。

生产调度使用专属 `random.Random`：普通间隔 3～8 秒，双眨概率 0.12，第二次间隔 80～160 ms。程序首次进入允许状态后至少等待 2 秒；隐藏/暂停恢复后至少等待 1.5 秒。随机数只在安排下一事件时消费，固定 seed 可复现，不影响全局 random。

允许状态为 `IDLE_CALM`、`IDLE_QUIET`、`IDLE_SWAY`、`RESTING`。`STARTING`、`CLICK_REACTION`、`DRAGGING`、`SETTLING`、`PAUSED`、`STOPPED` 不提交眨眼。点击和拖拽立即移除当前覆盖；睡眠、行走和舞蹈状态尚未加入。

## 绘制、尺寸和诊断

PetWindow 在同一个 `QPainter.save()` 和脚底锚点变换中依次绘制正式主图与全画布覆盖层。因此呼吸、浮动、摇摆、拖拽倾斜和点击变换完全一致。240×360、280×420、320×480 均从缓存的源 QImage 生成，尺寸切换不重置播放器帧。

`scripts/render_blink_diagnostics.py` 生成源眼区、覆盖/合成接触表、三档比较、黑白/棋盘背景、difference map 和 JSON 摘要。自动检查确认睁眼合成零差异、Alpha 稀疏且仅在批准区域、母版哈希不变。

## 性能与限制

四张全画布源 QImage 理论内存约 25,165,824 字节；实际运行仅按出现的尺寸/帧建立 QPixmap。100 次加速播放后缓存条目不再增加，tick 内无磁盘 I/O、缩放、哈希、Alpha 扫描或日志写入。

当前只有眨眼，没有眼神移动、其他表情、行走、睡眠、提醒、舞蹈或重新打包。源坐标放大诊断可观察到眼睑形变产生的纹理拉伸，实际桌宠尺寸下没有矩形边；闭眼弧线、纹理过渡和自然度必须由用户在真实 Windows 桌面确认。
