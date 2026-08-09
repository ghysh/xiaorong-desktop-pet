# 眨眼覆盖层来源记录

- 唯一来源：`assets/fullbody/final/fullbody_runtime_master.png`
- 来源 SHA-256：`6FD2E4CA948E250926A22428AA633AF83F487971086ABA92B1017C3599747A64`
- 生成脚本：`scripts/build_blink_overlay_assets.py`
- 画布：1024 × 1536 RGBA；只在双眼批准范围内具有非零 Alpha。
- `blink_open.png` 无损提取正式母版中不透明的原始眼部像素；合成差异为零。
- 半闭与闭眼帧使用边缘固定的本地眼睑形变展开原图上下眼睑，并在源坐标中人工定义抗锯齿睫线；OpenCV 仅用于开发期预生成，运行时不导入。
- 未调用在线图像服务、外部角色素材或水平镜像；正式母版未写入、未重编码。
- 放大诊断仍需关注局部纹理拉伸，正式闭眼弧线等待用户在真实桌面三档尺寸下确认。

Runtime-ready in Stage 10B only. The other eight action manifests remain planned and disabled.
