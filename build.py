"""Build entry point for the paper-blueprint film.

    python build.py stills [t ...]        single frames as PNG
    python build.py render [--workers N] [--4k]   lossless master + silent 720p (+4K)
    python build.py mix [--song PATH] [--4k]      mix your song + the execute chime into out/film.mp4
    python build.py all [--song PATH] [--workers N] [--4k]

The song is never distributed with the repository. Supply your own legally
acquired copy with --song (default input/song.mp3).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
TOOLCHAIN = Path("D:/aicode/.toolchain")


def tool(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    cand = TOOLCHAIN / f"{name}.exe"
    if cand.exists():
        return str(cand)
    raise SystemExit(f"missing tool: {name}")


def _env():
    import os
    e = dict(os.environ, PYTHONUTF8="1")
    e["PYTHONPATH"] = os.pathsep.join([str(ROOT)] + [p for p in [e.get("PYTHONPATH", "")] if p])
    return e


def run(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, env=_env(), **kw)


def _frames(a):
    import film
    return 0, int(round(film.END * film.FPS))


def render(a):
    import film
    OUT.mkdir(exist_ok=True)
    master = OUT / "film_master.mp4"
    if master.exists():
        raise SystemExit(f"refusing existing master: {master}")
    n0, n1 = _frames(a)
    workers = max(1, a.workers)
    seg = OUT / "_segments"
    seg.mkdir(exist_ok=True)
    k = max(1, min(workers * 2, n1 - n0))
    bounds = [n0 + (n1 - n0) * i // k for i in range(k + 1)]
    jobs = [(bounds[i], bounds[i + 1], seg / f"seg_{i:03d}.mp4") for i in range(k) if bounds[i + 1] > bounds[i]]
    started = time.time()
    with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(str(ROOT),)) as ex:
        list(ex.map(_chunk, jobs))
    lst = seg / "list.txt"
    lst.write_text("".join(f"file '{Path(x).as_posix()}'\n" for x in [j[2] for j in jobs]), encoding="utf8")
    run([tool("ffmpeg"), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c:v", "copy", "-movflags", "+faststart", str(master)])
    print(f"film_master.mp4: {n1 - n0} frames in {time.time() - started:.1f}s", flush=True)
    _encode_silent(a, master)


def _init(root: str):
    import sys
    sys.path.insert(0, root)
    import film  # noqa: F401  (warm fonts/timeline in the worker)


def _chunk(job):
    import film
    a, b, out = job
    ffmpeg = shutil.which("ffmpeg") or str(TOOLCHAIN / "ffmpeg.exe")
    cmd = [ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{film.W}x{film.H}", "-r", str(film.FPS), "-i", "-", "-an",
           "-c:v", "libx264rgb", "-qp", "0", "-preset", "veryfast", "-pix_fmt", "rgb24",
           "-threads", "2", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(a, b):
        proc.stdin.write(film.frame(n / film.FPS).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed on chunk {a}-{b}")
    return str(out)


def _encode_silent(a, master):
    tags = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
    run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(master),
         "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
         "-c:v", "libx264", "-crf", "16", "-preset", "slow", *tags,
         "-movflags", "+faststart", str(OUT / "film_silent_720p.mp4")])
    if a.k4:
        run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(master),
             "-vf", "scale=3840:2160:flags=neighbor:out_color_matrix=bt709:out_range=tv,format=yuv420p",
             "-c:v", "libx265", "-preset", "medium", "-crf", "16", *tags, "-tag:v", "hvc1",
             "-movflags", "+faststart", str(OUT / "film_silent_4k.mp4")])


def mix(a):
    import film
    song = Path(a.song) if a.song else ROOT / "input" / "song.mp3"
    if not song.exists():
        raise SystemExit(f"missing song: {song} (supply your own copy; the song is not distributed here)")
    master = OUT / "film_master.mp4"
    if not master.exists():
        raise SystemExit("missing master; run `python build.py render` first")
    chime = ROOT / "assets" / "chime.wav"
    audio = ["-i", str(song), "-i", str(chime), "-filter_complex",
             f"[1:a]atrim=0:{film.END},asetpts=PTS-STARTPTS[s];"
             f"[2:a]adelay={int(film.CHIME_T * 1000)}|{int(film.CHIME_T * 1000)}[c];"
             f"[s][c]amix=inputs=2:duration=first:normalize=0[a]",
             "-map", "0:v", "-map", "[a]"]
    tags = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
    run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(master), *audio,
         "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
         "-c:v", "libx264", "-crf", "16", "-preset", "slow", *tags,
         "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", "-shortest",
         str(OUT / "film.mp4")])
    if a.k4:
        run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(master), *audio,
             "-vf", "scale=3840:2160:flags=neighbor:out_color_matrix=bt709:out_range=tv,format=yuv420p",
             "-c:v", "libx265", "-preset", "medium", "-crf", "16", *tags, "-tag:v", "hvc1",
             "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", "-shortest",
             str(OUT / "film_4k.mp4")])
    print("done:", OUT / "film.mp4", flush=True)


def stills(a):
    import film
    out = OUT / "stills"
    out.mkdir(parents=True, exist_ok=True)
    for t in a.times:
        film.frame(t).save(out / f"still_{t:06.2f}.png")
        print(f"stills: {t:6.2f}s -> {out / f'still_{t:06.2f}.png'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["stills", "render", "mix", "all"])
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--song", help="path to your song mp3 (default input/song.mp3)")
    ap.add_argument("--4k", dest="k4", action="store_true")
    ap.add_argument("times", nargs="*", type=float)
    a = ap.parse_args()
    if a.step in ("render", "all"):
        render(a)
    if a.step in ("mix", "all"):
        mix(a)
    if a.step == "stills":
        stills(a)


if __name__ == "__main__":
    main()
