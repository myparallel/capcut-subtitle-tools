"""
TTS from bilingual SRT — generates natural-speed voiceover audio + corrected timestamps.

Usage:
    python tts_from_srt.py --input 双语字幕_上英下中.srt --lang 1

    --input   Bilingual SRT file (上英下中 format, each entry = EN line + ZH line)
    --lang    Language for TTS: 1=English, 2=Chinese
             (can also set LANG_CHOICE env var)
    --prefix  Output filename prefix (optional)
"""

import asyncio
import edge_tts
import subprocess
import os
import re
import shutil
import sys
import argparse
from pathlib import Path

if sys.stdout.encoding.lower() in ("gbk", "gb2312", "gb18030"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FFMPEG_DIR = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" / "ffmpeg-8.1.1-full_build" / "bin"
os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

TEMP_DIR = Path("_tts_temp")
GAP_MS = 300

VOICE_MAP = {
    "1": {"name": "英文", "voice": "en-US-JennyNeural", "line": 0},
    "2": {"name": "中文", "voice": "zh-CN-XiaoxiaoNeural", "line": 1},
}

def parse_args():
    parser = argparse.ArgumentParser(description="TTS from bilingual SRT")
    parser.add_argument("--input", default=os.environ.get("SRT_INPUT", "双语字幕_上英下中.srt"),
                        help="Input bilingual SRT file")
    parser.add_argument("--lang", default=os.environ.get("LANG_CHOICE", ""),
                        help="Language: 1=English, 2=Chinese")
    parser.add_argument("--prefix", default=os.environ.get("OUTPUT_PREFIX", ""),
                        help="Output filename prefix")
    return parser.parse_args()

def ms_to_srt_time(ms):
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    f = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{f:03d}"

def parse_srt(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    blocks = re.split(r"\n\s*\n", content.strip())
    segments = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        match = re.match(
            r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})",
            lines[1],
        )
        if not match:
            continue
        segments.append({
            "index": int(lines[0]),
            "text_lines": [l for l in lines[2:] if l.strip()],
        })
    return segments

async def generate_tts(voice, text, output_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))

def get_audio_duration_ms(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    return int(float(result.stdout.strip()) * 1000)

def update_srt_timestamps(segments, output_path):
    lines = []
    for seg in segments:
        lines.append(str(seg["index"]))
        lines.append(f"{ms_to_srt_time(seg['start_ms'])} --> {ms_to_srt_time(seg['end_ms'])}")
        lines.extend(seg["text_lines"])
        lines.append("")
    with open(output_path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines))

async def main():
    args = parse_args()
    choice = args.lang
    srt_path = args.input
    prefix = args.prefix

    if choice not in ("1", "2"):
        print("请选择朗读语种：")
        print("  1 - 英文 (English)")
        print("  2 - 中文 (Chinese)")
        print()
        while choice not in ("1", "2"):
            choice = input("请输入 1 或 2: ").strip()

    lang = VOICE_MAP[choice]
    voice = lang["voice"]
    label = lang["name"]
    line_idx = lang["line"]
    print(f"已选择: {label}朗读，字幕保持上英下中双语\n")

    segments = parse_srt(srt_path)
    print(f"解析到 {len(segments)} 条字幕\n")

    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
    TEMP_DIR.mkdir(parents=True)

    for seg in segments:
        idx = seg["index"]
        text = seg["text_lines"][line_idx]
        mp3_path = TEMP_DIR / f"seg_{idx:03d}.mp3"
        wav_path = TEMP_DIR / f"seg_{idx:03d}.wav"

        print(f"  [{idx}/{len(segments)}] 朗读: {text[:50]}...")
        try:
            await generate_tts(voice, text, mp3_path)
        except Exception as e:
            print(f"    TTS 失败: {e}，默认 2s")
            seg["dur_ms"] = 2000
            seg["audio_path"] = None
            continue

        subprocess.run(
            ["ffmpeg", "-y", "-i", str(mp3_path), str(wav_path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        dur = get_audio_duration_ms(wav_path)
        seg["dur_ms"] = dur
        seg["audio_path"] = wav_path
        print(f"    时长: {dur}ms ({dur/1000:.2f}s)")

    cursor_ms = 0
    for seg in segments:
        seg["start_ms"] = cursor_ms
        seg["end_ms"] = cursor_ms + seg["dur_ms"]
        cursor_ms = seg["end_ms"] + GAP_MS

    total_dur_ms = cursor_ms - GAP_MS

    out_label = f"{prefix}_{label}" if prefix else label
    srt_output = f"配音字幕_双语_配音{out_label}.srt"
    update_srt_timestamps(segments, srt_output)
    print(f"\n字幕已生成: {srt_output}（上英下中双语）")

    print("合成最终音频...")
    concat_lines = []
    for seg in segments:
        if seg["audio_path"] and seg["audio_path"].exists():
            concat_lines.append(f"file '{seg['audio_path'].resolve()}'")
        else:
            silence = TEMP_DIR / f"silence_{seg['index']:03d}.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i",
                 f"anullsrc=r=24000:cl=mono",
                 "-t", f"{seg['dur_ms']/1000:.3f}", str(silence)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            concat_lines.append(f"file '{silence.resolve()}'")
        gap_file = TEMP_DIR / f"gap_{seg['index']:03d}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i",
             f"anullsrc=r=24000:cl=mono",
             "-t", f"{GAP_MS/1000:.3f}", str(gap_file)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        concat_lines.append(f"file '{gap_file.resolve()}'")

    concat_lines = concat_lines[:-1]

    concat_list = TEMP_DIR / "concat.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for line in concat_lines:
            f.write(line + "\n")

    audio_output = f"配音_{out_label}.mp3"
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(concat_list), "-c", "copy", str(TEMP_DIR / "raw_concat.wav")],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  concat 警告: {result.stderr[:200]}")

    subprocess.run(
        ["ffmpeg", "-y", "-i", str(TEMP_DIR / "raw_concat.wav"),
         "-b:a", "192k", str(audio_output)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    final_dur = get_audio_duration_ms(audio_output)
    print(f"音频已生成: {audio_output}")
    print(f"  音频总时长: {final_dur/1000:.2f}s")
    print(f"  字幕总时长: {total_dur_ms/1000:.2f}s")
    print(f"  语速自然，未做变速处理\n")

    shutil.rmtree(TEMP_DIR)
    print("完成！请将以下两个文件配对导入剪映：")
    print(f"  字幕 -> {srt_output}")
    print(f"  音频 -> {audio_output}")

if __name__ == "__main__":
    asyncio.run(main())
