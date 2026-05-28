"""
Build bilingual SRT (上英下中) from enriched segments JSON.

Usage:
    python build_bilingual_srt.py --segments segments_bilingual.json --output 双语字幕_上英下中.srt

Input JSON format (after Claude adds translation):
{
  "source_language": "zh",
  "target_language": "en",
  "duration": 47.65,
  "segments": [
    {
      "id": 1,
      "start": 0.0,
      "end": 5.28,
      "text": "在这个宁静的夜晚...",
      "translation": "On this quiet night..."
    }
  ]
}

Output SRT format (上英下中 = English line first, Chinese second):
1
00:00:00,000 --> 00:00:05,280
On this quiet night...
在这个宁静的夜晚...

The ordering rule:
- If source_language == "zh": EN line 1st, ZH line 2nd
- If source_language == "en": EN line 1st, ZH line 2nd
- Always: English on top, Chinese below
"""

import argparse
import json


def ms_to_srt(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    parser = argparse.ArgumentParser(description="Build bilingual SRT from segments JSON")
    parser.add_argument("--segments", required=True, help="Enriched segments JSON")
    parser.add_argument("--output", default="双语字幕_上英下中.srt", help="Output SRT file")
    args = parser.parse_args()

    with open(args.segments, "r", encoding="utf-8") as f:
        data = json.load(f)

    src_lang = data.get("source_language", "unknown")
    segments = data.get("segments", [])

    lines = []
    for seg in segments:
        lines.append(str(seg["id"]))
        lines.append(f"{ms_to_srt(seg['start'])} --> {ms_to_srt(seg['end'])}")
        # Always: EN first, ZH second
        if src_lang == "zh":
            lines.append(seg["translation"])
            lines.append(seg["text"])
        else:
            lines.append(seg["text"])
            lines.append(seg["translation"])
        lines.append("")

    content = "\n".join(lines)
    with open(args.output, "w", encoding="utf-8-sig") as f:
        f.write(content)

    total_end = segments[-1]["end"] if segments else 0
    print(f"已生成: {args.output}")
    print(f"  条数: {len(segments)}")
    print(f"  时长: {total_end:.2f}s")
    print(f"  格式: 上英下中双语")


if __name__ == "__main__":
    main()
