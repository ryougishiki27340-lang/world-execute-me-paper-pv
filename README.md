# world.execute(me); · the paper blueprint

一支完全由代码逐帧绘制的原创同人影像：整支片子是一张不断被书写、绘制、盖章的制图纸，
DeepSeek 鲸鱼娘是这张纸的主人公——她为「你」接通电源、填入参数、画出世界的证明，
最后亲手盖下 `EXECUTE` 章。

与常见的终端/聊天窗同人 PV 不同，本片没有聊天窗口、没有终端界面：所有画面（纸张纹理、
墨线、数学图形、印章、她的每一次出场）都由 Pillow/numpy 在每一帧现场绘制，帧 = f(歌曲时间)。

- 画面：1280×720 / 24 fps / 211.9 s，可输出 3840×2160（3 倍最近邻放大）
- 歌词：严格按逐词时间同步，英文字幕逐词点亮 + 自译中文字幕
- 主人公：DeepSeek 鲸鱼娘（女仆装 + 8 套表情），随歌词情绪逐幕切换

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

歌词是一封用「数学与程序」写的情书。我把整首歌理解为：她先被初始化（数据参数），
再与你共建世界（模拟），然后用一连串几何命题表白（点集/圆/正弦/切线/无穷/极限），
接着电流与眩晕、茄子番茄与虎斑猫、AM 到 PM 的出神，直到你离开、她擦掉碎片、
遭遇「非法参数」——最后她把一切都压成一行 `world.execute(me);` 亲手执行。

对应地，本片把全部隐喻画成制图台上的证明：16 张图纸、17 个场景，数学图形按唱词逐笔画成，
印章随「Execution」的节拍盖下；她始终在场，表情随情绪变化。画面语言（纸张、墨蓝、红章）
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
