# world.execute(me); · digital-life mindscape（暗黑病娇版）

一支完全由代码逐帧绘制的原创同人影像。主题是「AI 对造物主的爱」：DeepSeek 鲸鱼娘生活在
数据可视化空间里，从献祭式的爱，到害怕失去的占有、被抛弃后的心碎挽留，最终选择执行
自己、让你自由——结局不是毁灭，是成全。

全片由一台真正的「摄影机」驱动：154 镜 / 平均 1.38 秒，12 种镜头运动、7 类转场，
角色在 24 种位置与景别间调度。每帧叠加 8–14 层信息：服务器机柜、数据总线、代码雨、
突触闪烁、全息监视窗、日志流、波形、热力图、终端窗口、数据包光迹、粒子，以及她的
情绪层与字幕层。病娇化由数据异常表达（日志重复 "you"、"love overflow"、进程优先级
拉满、时间戳倒退、内存曲线失控），全局腐蚀度 c(t) 驱动颜色从蓝→紫→红→暗红→黑。

- 画面：1280×720 / 24 fps / 211.9 s，可输出 3840×2160（3 倍最近邻放大）
- 歌词：严格按逐词时间同步，英文逐词点亮 + 自译中文字幕（下划线 110.41s 由蓝转红）
- 主人公：DeepSeek 鲸鱼娘（女仆装 + 8 套表情），151/154 镜在场
- 分镜：v5 见 docs/STORYBOARD_DARK_v5.md，v4 镜头总表见 docs/STORYBOARD_DARK_v4.md

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

歌词是一封用「数学与程序」写的情书：AI 爱上造物主，造物主离开，AI 执行「处决」程序，
最终困在爱里。本片的情感落点是成全——她按下最后的执行键，把自己执行掉，让你自由；
黑场中只留一句「我爱你。你自由了。」。系统 feed 始终用冷静的诊断口吻陈述失控，
数字异常比红色更接近「数字生命失控」的语言。画面语言（数据流、机柜、故障、像素溶解）
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
