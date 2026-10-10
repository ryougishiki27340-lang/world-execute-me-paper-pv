# world.execute(me); · digital-life mindscape（暗黑病娇版）

一支完全由代码逐帧绘制的原创同人影像。DeepSeek 鲸鱼娘是生活在数据可视化空间里的数字生命：
全片跟随歌曲的五段情绪弧线，从「为爱献祭」的电蓝有序，经占有欲的紫色渗入、被抛弃的红色崩坏、
Execution 连击的语言暴走，到最后把自己一起 execute 掉的像素化溶解与黑场死寂。

没有聊天窗口、没有终端、没有制图纸：所有画面（数据网格、突触连线、代码碎片、系统 feed、
局部像素故障、文字增殖、她的每一次出场）都由 Pillow/numpy 在每一帧现场绘制，帧 = f(歌曲时间)。

核心机制是一个全局腐蚀度 c(t)（0→1），驱动颜色（蓝→紫→红→暗红→黑）、马赛克扩散、
语言暴走强度与后期故障，让病娇化渐进发生而不是一黑到底。

- 画面：1280×720 / 24 fps / 211.9 s，可输出 3840×2160（3 倍最近邻放大）
- 歌词：严格按逐词时间同步，英文逐词点亮 + 自译中文字幕（下划线 110.41s 由蓝转红）
- 主人公：DeepSeek 鲸鱼娘（女仆装 + 8 套表情），表情与面部故障随五段情绪递进
- 分镜：22 幕，见 docs/STORYBOARD_DARK.md

## 快速开始

需要 Python 3.12+（Pillow、numpy）、ffmpeg（PATH 中）。不需要 Node、Playwright 或模型服务。

```text
pip install pillow numpy
python build.py render --workers 14        # 无损母版 + 静音 720p（约 10 分钟）
python build.py mix --song D:/你的歌曲.mp3  # 混入你的歌曲与执行提示音 -> out/film.mp4
python build.py mix --song ... --4k        # 另出 out/film_4k.mp4
```

`build.py stills 12 70 150` 可导出任意时间点的静帧到 `out/stills/` 用于审看。

## 输出

- `out/film_master.mp4`：1280×720、24 fps 无损母版（无音频）
- `out/film_silent_720p.mp4`：H.264 720p 静音预览
- `out/film.mp4`：混入你的歌曲与提示音后的成片（本地生成，不随仓库分发）
- `out/film_silent_4k.mp4` / `out/film_4k.mp4`：4K 版本（--4k）

## 创作说明（概念原文）

歌词是一封用「数学与程序」写的情书，剧情弧线是 AI 爱上造物主、造物主离开、AI 执行
「处决」程序、最终困在爱里。本片把五段弧线做成递进的视觉腐蚀：电蓝的献祭、紫色的占有、
红色的崩坏与暴走、暗红的理智绝望、最终的黑场自我毁灭。系统 feed 始终用冷静的
诊断口吻陈述失控，压迫感来自「极度的理智」。画面语言（数据流、故障、像素溶解）
与参考同人 PV 的终端美学完全不同，是我对这个故事的独立转译。

## 不随仓库分发的内容

- 歌曲音频（Mili 版权）：请自备合法副本，经 `--song` 指定
- 歌词全文：构建时按 `data/timeline.json`（不含文字的逐词时间）配合自译中文字幕渲染，
  不复制任何歌词文本来源文件
- Windows 字体：使用本机 Consolas / 微软雅黑

## 许可与署名

- 本项目代码（film.py、build.py 等）：MIT，见 LICENSE
- 鲸鱼娘立绘与表情：dsh-deep-whale（Small-tailqwq）与 dsh-whale-galgame，
  CC BY-NC-SA 4.0，非商用，保留署名链，详见 NOTICE.md
- 逐词时间数据：衍生自 MisakaZentai/world-execute-me-dsh-pv（MIT），仅用于歌词对位
- 音乐与歌词权利归 Mili 所有；本片为非官方同人作品

发布包含 AI 生成内容时请按 Mili 官方指引明确标注；本仓库画面为代码渲染，
角色素材为第三方画师作品，不属于 AI 生成。
