# 犯困睡觉动作素材说明

- 唯一正式角色参考：`assets/fullbody/final/fullbody_runtime_master.png`
- 正式主图 SHA-256：`6FD2E4CA948E250926A22428AA633AF83F487971086ABA92B1017C3599747A64`
- 生成方式：内置 `image_gen`。每组补帧同时参考正式主图与动作前后相邻关键姿势，提示词统一声明“仅改变完成动作所必需的身体部位，其余人物特征、服装、头发、比例、位置和画风保持不变”。
- 透明化方式：生成纯绿色键背景后，使用 imagegen 技能自带的 `remove_chroma_key.py` 转换为 RGBA PNG。
- 后处理方式：使用 `scripts/prepare_drowsy_sleep_frames.py` 处理单帧或故事板候选，基于 Alpha 边界框把人物统一到 1024×1536 RGBA 画布、水平中心 `x=512`、底边 `y=1497`，并按动作阶段指定目标人物高度。
- 脚本会拒绝触边裁切、过大的断开透明残片、主体宽度异常，以及与前后帧在中心、底边、宽高变化上超过阈值的候选。
- 视觉抽检中存在裁切、残片、人物尺度突变或姿态不连续的候选帧不会进入运行清单。
- 没有修改或覆盖正式角色主图。
- `default_standing.png` 是正式主图的逐字节只读副本，用于平滑进入和退出动作。
- 鼻涕泡不属于任何人物 PNG，由 `PetWindow` 在人物帧之后独立绘制。

## 关键姿势

- `sleep_base.png`：盘腿、闭眼、安静睡眠。
- `sleep_nod.png`：保留的旧版轻微低头端点；新时间轴使用同一组 `sleep_nod_10/25/33/42/51/60/66/72/79/85` 连续帧，不再打包此旧端点。
- `wake_seated.png`：鼻涕泡消失后的半睁眼苏醒。
- `stretch_local_compact_peak.png`：紧凑屈肘的站立伸展顶点；保持人物原比例，避免直臂上举造成缩小或裁切。
- `yawn.png`：站立轻轻打哈欠。
- `rub_eye.png`：站立揉眼。
- `default_standing.png`：起身和返回默认状态的正式角色帧。

## 补间帧分组

- 坐下：新增 `sit_down_knees_50`、`sit_down_lower_50`、`sit_down_fold_75`，插入既有屈膝、下沉、收腿关键姿势之间。
- 入睡与点头：新增 `sleep_eyes_quarter`、`sleep_head_droop`，并补齐 `sleep_nod_10/33/51/66/79`，三次点头复用 10 个深度等级。
- 苏醒与起身：新增 `wake_eyes_10`、`wake_head_lift`、`rise_prepare`、`rise_unfold_mid`、`rise_low_support`、`rise_crouch_low`、`rise_near_stand`。
- 伸展：使用 `stretch_local_prepare/arms_low/waist/chest/elbow_mid/chest_to_shoulders/shoulders/upper/open_high/compact_peak/end` 共 11 个统一姿势，构成 20 帧抬臂、顶点停留和回落序列。
- 哈欠与揉眼：新增 `yawn_mouth_quarter`、`yawn_mouth_wide`、`yawn_close_small`、`rub_eye_touch`、`rub_hand_down`。

当前共接入 61 张新增补间 PNG；先前素材轮次使用 image_gen 新增并接入 26 张。另将 `wake_seated`、`yawn_hand_raise`、`yawn`、`rub_eye` 仅做 Alpha 边界框缩放与平移对齐，人物绘画内容不变。动作中段不使用人物交叉淡化。

伸懒腰专项优化额外生成 10 张候选，保留 6 张小步补帧，淘汰 4 张会造成抬臂跨度、构图或缩放不稳定的高位候选。最终 11 个 stretch 姿势全部统一为 1024×1536 RGBA、Alpha 高度 1453 px、水平中心 x=512、底边 y=1497，并以固定画布腿部采样带检查主体比例，避免手臂抬高改变整张人物缩放。

鼻涕泡继续是独立图层；点头阶段按 `sleep_base` 和每个 `nod_xx` 事件使用独立归一化鼻尖偏移，深度越大锚点越向下，回程按同一组锚点反向返回。
