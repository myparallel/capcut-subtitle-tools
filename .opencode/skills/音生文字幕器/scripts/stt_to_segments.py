"""
Speech-to-Text: transcribe audio to timed segments using faster-whisper.

Usage:
    python stt_to_segments.py --input audio.mp3 --output segments_raw.json [--model small]

    --input    Audio file (mp3, wav, m4a, etc.)
    --output   Output JSON with timed segments
    --model    Whisper model size: tiny, base, small, medium, large (default: small)
    --lang     Force language (en/zh). Auto-detect if omitted.
"""

import argparse
import json
import os
import sys
import time
from faster_whisper import WhisperModel


def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    cs = int((s - int(s)) * 1000)
    return f"{h:02d}:{m:02d}:{int(s):02d},{cs:03d}"


def main():
    parser = argparse.ArgumentParser(description="STT to timed segments")
    parser.add_argument("--input", required=True, help="Audio file path")
    parser.add_argument("--output", default="segments_raw.json", help="Output JSON")
    parser.add_argument("--model", default="small", help="Model size: tiny/base/small/medium/large")
    parser.add_argument("--lang", default=None, help="Force language: en or zh")
    parser.add_argument("--device", default="auto", help="Device: auto/cpu/cuda")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误：找不到音频文件 {args.input}")
        sys.exit(1)

    # Resolve device
    device = args.device
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    compute_type = "float16" if device == "cuda" else "int8"

    print(f"加载 Whisper 模型 ({args.model}, {device})...")
    t0 = time.time()
    model = WhisperModel(args.model, device=device, compute_type=compute_type)
    print(f"模型加载完成 ({time.time()-t0:.1f}s)")

    print(f"转写音频: {args.input}")
    t0 = time.time()
    segments, info = model.transcribe(args.input, language=args.lang, beam_size=5)
    lang = info.language
    duration = info.duration
    print(f"检测到语言: {lang}, 音频时长: {duration:.2f}s ({time.time()-t0:.1f}s)")

    seg_list = []
    for i, seg in enumerate(segments, 1):
        seg_list.append({
            "id": i,
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
        })
        if i <= 3 or i % max(1, len(seg_list)//5) == 0:
            print(f"  [{i}] {format_time(seg.start)} --> {format_time(seg.end)}  {seg.text.strip()[:60]}")

    output = {
        "source_language": lang,
        "duration": round(duration, 3),
        "segments": seg_list,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n完成！共 {len(seg_list)} 条片段")
    print(f"输出: {args.output}")
    print(f"\n下一步：请将 {args.output} 中的每条 text 翻译后添加 translation 字段，")
    print(f"然后运行 build_bilingual_srt.py 生成 SRT 文件。")


if __name__ == "__main__":
    main()
