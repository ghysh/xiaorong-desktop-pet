# 第三阶段：透明基础素材处理与质量记录

## 范围和输入

- 唯一视觉输入：`D:\DesktopPet\ori_figure.png` 的项目内只读副本
  `assets/original/character_original.png`。
- 原图基线：346 × 346、RGB、SHA-256
  `CCF0AABC6D1DD7AFF61590E40BBEF7C0E2411B6524CF47C72D6BC10BDE900DB3`。
- 本阶段默认逻辑显示尺寸为 240 × 240，备选为 280 × 280。
- 本阶段仅交付一张透明静态基础图；不新增动画帧、不重绘、不扩图、不补画画外内容，也不实现透明窗口或交互。

## 可复现的本地处理方法

入口：

```powershell
conda run -n dp python scripts/build_transparent_character.py --stage all
```

脚本仅在本地使用 Pillow、NumPy 与 OpenCV 的经典图像处理：

1. 校验项目内原图的 SHA-256、尺寸和 RGB 模式，并校验第二阶段记录的白色边缘背景候选；
2. 以与画布边缘连通的近白像素作为背景种子；
3. 用 GrabCut 的显式掩码初始化生成前景候选；
4. 由 `assets/processed/masks/mask_corrections.json` 施加可追溯的前景保护和右下背景碎片清理；
5. 输出 0 / 128 / 255 三值 Trimap，并只在 3 像素以内的半透明边缘执行去污染；
6. 将 346 × 346 RGBA 候选居中置入 410 × 410 透明运行时主图，不缩放原始像素。

处理不调用网络、云端服务或生成式模型。任何 alpha=255 的像素 RGB 与原图逐像素相同；只允许半透明边缘 RGB 去污染。

本机用于该流程的新增开发依赖版本：NumPy 2.4.6、OpenCV Python 5.0.0（`opencv-python-headless` 5.0.0.93）。两者仅被 `scripts/build_transparent_character.py` 导入，运行时包 `src/desktop_pet/` 不依赖 OpenCV。

## 产物与用途

- `assets/processed/base/character_cutout_rgba.png`：346 × 346、RGBA、源坐标透明抠图。
- `assets/processed/base/character_runtime_master.png`：410 × 410、RGBA、带 32 像素透明安全边距的后续运行时主图。
- `assets/processed/masks/character_trimap.png`：0 / 128 / 255 Trimap。
- `assets/processed/masks/character_alpha_mask.png`：单通道 Alpha 掩码。
- `assets/processed/masks/mask_corrections.json`：人工修正区域、理由和每次应用统计。
- `assets/processed/previews/`：240、280、白底、浅灰、深灰、黑底、棋盘格、边缘放大与综合复检图。
- `assets/analysis/transparency/`：背景种子、GrabCut 标签、二值前景、去污染前后诊断图。
- `assets/processed/reports/asset_manifest.json`：每个 PNG 的项目相对路径、SHA-256、尺寸、模式和用途。

## 本轮人工质量复检

| 项目 | 结果 |
| --- | --- |
| 黑底 / 深灰底白边 | 通过；未见明显白色光晕 |
| 棋盘格残留背景 | 通过；右下外侧背景线条已由记录的确定背景修正清理 |
| 发丝边缘 | 通过；右侧细发丝、非硬边轮廓保留 |
| 眼睛、脸部、腮红 | 通过；未被近白背景规则误抠除 |
| 手部、袖口、红色点缀、深色服装 | 通过；保护区和主体色彩保留 |
| 240 / 280 显示可读性 | 通过；两种尺寸均已生成供用户比较 |
| 原图完整性 | 通过；源文件和项目内原图副本哈希未改变 |

## 已知限制与后续限制

- 原图角色触及左、右、下画布边缘；没有也不会推断画外头发、身体、服装或动作。
- 细边缘仍需用户最终肉眼确认；当前状态为“透明基础素材候选，待确认”。
- 第四阶段之前不得把本阶段图用于透明窗口、桌宠逻辑、动画帧、姿势变化或局部重绘。
- 如需更大画幅、完整身体或新动作，必须先取得用户明确授权并以新的已确认素材为依据。

## 用户确认点

1. 是否认可当前透明边缘、右侧细发丝与右下袖口外缘？
2. 后续运行时默认尺寸使用 240 × 240 还是 280 × 280？
3. 是否将 `character_runtime_master.png` 定为后续桌宠运行时主图？
4. 是否允许下一阶段开始透明窗口原型（仍不新增动画）？
5. 是否有需要在进入下一阶段前调整的显示尺寸、透明边缘或留白？
