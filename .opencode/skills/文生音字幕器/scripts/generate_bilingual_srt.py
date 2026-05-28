"""
Generate bilingual SRT (上英下中) from text segments with estimated timings.

Usage:
    python generate_bilingual_srt.py --segments segments.json --output 双语字幕_上英下中.srt

    segments.json format:
    [
        {"en": "English text line 1", "zh": "中文第一行"},
        {"en": "English text line 2", "zh": "中文第二行"}
    ]

Timing estimation:
    - English: 2.5 words/sec
    - Chinese: 4 chars/sec
    - Minimum: 2.0s per segment
    - Gap between segments: 0.3s
"""

import json
import argparse
import re

GAP_MS = 300


def estimate_duration_ms(en_text, zh_text):
    en_words = len(en_text.split())
    zh_chars = len(zh_text)
    en_time = en_words / 2.5
    zh_time = zh_chars / 4.0
    return int(max(2.0, max(en_time, zh_time)) * 1000)


def ms_to_srt_time(ms):
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    f = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{f:03d}"


def generate_srt(segments, output_path, gap_ms=GAP_MS):
    cursor_ms = 0
    lines = []

    for i, seg in enumerate(segments, 1):
        dur_ms = estimate_duration_ms(seg["en"], seg["zh"])
        start_ms = cursor_ms
        end_ms = cursor_ms + dur_ms

        lines.append(str(i))
        lines.append(f"{ms_to_srt_time(start_ms)} --> {ms_to_srt_time(end_ms)}")
        lines.append(seg["en"])
        lines.append(seg["zh"])
        lines.append("")

        cursor_ms = end_ms + gap_ms

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8-sig") as f:
        f.write(content)

    total_sec = (cursor_ms - gap_ms) / 1000
    return len(segments), total_sec


def main():
    parser = argparse.ArgumentParser(description="Generate bilingual SRT")
    parser.add_argument("--segments", required=True,
                        help="JSON file with [{en, zh}, ...]")
    parser.add_argument("--output", default="双语字幕_上英下中.srt",
                        help="Output SRT file path")
    parser.add_argument("--gap", type=int, default=GAP_MS,
                        help="Gap between segments in ms")
    args = parser.parse_args()

    with open(args.segments, "r", encoding="utf-8") as f:
        segments = json.load(f)

    count, total_sec = generate_srt(segments, args.output, args.gap)
    print(f"已生成: {args.output}")
    print(f"  条数: {count}")
    print(f"  估算总时长: {total_sec:.2f}s")
    print(f"  格式: 上英下中双语")


if __name__ == "__main__":
    main()
