# 动作 Manifest 规范

机器可读定义位于 `assets/actions/schema/action_clip.schema.json`。阶段 10B 将 schema 扩展为 planned、draft、ready 和 disabled；状态与运行标志通过条件规则绑定，不能只修改一个布尔值绕过门禁。

## 核心字段

| 字段 | 约束 |
|---|---|
| `schema_version` | 当前为 1 |
| `action_id` | 稳定的小写英文 snake_case 标识 |
| `display_name` | 中文用户显示名 |
| `status` | `planned`、`draft`、`ready` 或 `disabled` |
| `runtime_enabled` | 只有审核通过的 ready 动作可为 true |
| `assets_complete` | ready 动作必须为 true；planned 必须为 false |
| `category` | 六种 `ActionCategory` 之一 |
| `loop_mode` | `ONCE`、`LOOP`、`PING_PONG`、`HOLD_LAST_FRAME` |
| `interrupt_policy` | 四种剪辑内打断边界之一 |
| `priority` | 集中优先级对应的正整数 |
| `default_loop_count` | 正整数；实际用户动作仍可由请求覆盖 |
| `mirror_allowed` | 正式角色默认且当前必须为 false |
| `source_asset_sha256` | 必须等于方案 B 正式母版哈希 |
| `canvas` | 统一 1024 × 1536 坐标空间 |
| `feet_anchor` | 0～1 归一化坐标；当前规划基准约 `(0.5, 0.9733)` |
| `tags` | 唯一、稳定英文标识数组 |
| `frames` | planned 必须为空；ready 至少一帧且必须通过实际文件校验 |
| `planning` | 帧数、FPS 预算和非运行说明 |

未来每个 frame 至少包含相对 PNG 路径、正整数 `duration_ms`、归一化局部锚点和可选稳定事件名。禁止绝对路径、反斜杠、`..` 路径和非 PNG 运行帧。

## 目录约定

每个未来可制作动作目录使用：

```text
manifest.json
frames/
preview/
source_notes.md
```

`frames/` 才能成为运行资源；`preview/` 永不打包。`source_notes.md` 记录母版哈希、人工绘制/审核过程、左右方向决策和用户批准。当前 `frames/`、`preview/` 只有 `.gitkeep`。

## 运行门禁

planned manifest 可以解析并进入 `ActionPlanRegistry`，但：

- `ActionManifest.to_clip()` 必须失败；
- 不能导入到 `app.py` 或 `PetWindow`；
- 不能进入 UI `ActionRegistry`；
- 不得打包到当前 1.0.0 运行资源。

只有 `status=ready`、`runtime_enabled=true`、`assets_complete=true`、所有帧存在并通过哈希/画布/锚点/视觉审核时，才能创建并注册 `ActionClip`。draft 和 disabled 也不能注册。阶段 10B 只有 `blink_normal` 通过此门禁，其他八份 manifest 继续保持 planned。
