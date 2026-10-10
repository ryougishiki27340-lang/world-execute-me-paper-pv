# input/：你自己准备的东西

本目录除本说明外均被 Git 忽略。

## song.mp3（混音时需要）

自备合法取得的 Mili《world.execute(me);》音频，任意采样率的 MP3/WAV 均可。
画面时间轴按 `data/timeline.json`（片长 211.9 秒）编排；若你的音源片头多出静音，
唱词会整体漂移，可用 ffmpeg 裁齐起唱点：

```text
ffmpeg -i 你的歌曲.mp3 -ss 0.0 -t 211.9 -ar 44100 input/song.mp3
```

然后运行 `python build.py mix --song input/song.mp3`。
