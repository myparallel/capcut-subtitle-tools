---
name: 音生文字幕器
description: "从一段音频（MP3/WAV等）+ 一段文案稿（TXT）出发，通过STT获取精确时间轴，再用文案稿逐句校正STT错字，生成可直接导入剪映（CapCut）的上英下中双语字幕SRT，且字幕时间轴与音频严格对齐。触发场景：用户说'帮我根据这个音频做字幕'、'给这段音频配字幕'、'音频+文案生成字幕'、'音频转字幕用文案校准'、提供音频文件和文案稿要求做双语字幕、提到有录音文件和文字稿需要合成为对齐的字幕、或处理口播配音需要生成精确同步的双语字幕。也适用于已有音频和文案，要求字幕时间轴精确、文字正确的场景。"
---

# 音生文字幕器

从一段音频 + 一段文案稿出发，生成与音频时间轴严格对齐的**上英下中**双语字幕。

## 核心原则

经过反复迭代验证，以下原则不可违反：

1. **STT定时间轴** — 先用 STT 语音识别获取精确的句段划分和起止时间
2. **零改动时间轴** — 输出的 SRT 必须与 STT 的句段数、每段起止时间完全一致。**永远不要合并或拆分 STT 的段落**
3. **文案校正内容** — 用用户提供的文案稿替换 STT 识别错误的文字
4. **禁止文字溢出** — 校正后的每段文字，必须严格限定在该时间窗口内实际说出的内容。如果文案稿的一句话被 STT 切成了两段，校正时也要切成两段，不能把整句塞进前一段
5. **保留原始 STT** — 将原始 STT 提取稿作为时间轴参照文件一并交付

## 工作流总览

```
音频文件 + 文案稿 (TXT)
    │
    ▼  步骤1 — STT 定时间轴
语音识别 → 带精确时间戳的原文段 ✓
    │  (此步骤确立：句段数N、每段起始/结束时间)
    │
    ▼  步骤2 — 文案逐句匹配
读文案稿 → 逐段对照 STT 原文
    │  标记每段需要修正的文字
    │
    ▼  步骤3 — 生成双语 SRT（核心）
对每段 STT 输出：
    - 保持原始时间点不变
    - 英文用文案稿的正确文字替换
    - 英文标点/大小写校正
    - 中文逐条翻译
    │  
    ▼  步骤4 — 交付检查
逐段验证：段数一致？时间点一致？文字范围不过界？
```

---

## 技能依赖

```powershell
pip list 2>$null | findstr faster-whisper
if ($?) { echo "faster-whisper OK" } else { pip install faster-whisper 2>&1 | out-null }
```

`faster-whisper` 首次运行时会自动下载模型文件（~500MB small 模型）。

技能自带脚本：
- `scripts/stt_to_segments.py` — 语音识别，输出带时间轴的原文段
- `scripts/build_bilingual_srt.py` — 从翻译后的 JSON 组装 SRT

---

## 步骤1：获取输入 + STT 定时间轴

### 1.1 获取输入文件

用户会提供：
- **音频文件**（MP3/WAV/M4A 等）— 口播录音、配音等
- **文案稿**（TXT）— 与音频内容对应的文字稿（用户提供的校准原始材料）

如果用户没有一次性给全，询问获取。

### 1.2 规划项目文件夹

从音频/文案内容提炼主题词 + 日期 `YYYYMMDD` 命名文件夹。

### 1.3 运行 STT

```powershell
python .opencode\skills\音生文字幕器\scripts\stt_to_segments.py --input 音频.mp3 --output _stt_raw.json --model small
```

输出 `_stt_raw.json` 包含：
- `source_language` — 检测到的语言
- `duration` — 音频总时长
- `segments` — 数组，每段有 `id`, `start`, `end`, `text`

**关键**：STT 输出的 `segments` 数组的长度 N 和每段的 `start`/`end` 就是最终 SRT 必须严格遵守的框架。

### 1.4 输出原始 STT 参照稿

用 `_stt_raw.json` 生成 `_STT原始提炼稿.srt`（只有英文，无中文，纯时间轴参照用）。

---

## 步骤2：文案校正（最关键的步骤）

### 2.1 读取文案稿

用 `Read` 工具读取用户提供的 TXT 文案稿。

### 2.2 逐段对照 + 校正

这是最关键的步骤，容易出错。严格按以下流程：

**对 STT 的每一条 segment：**
1. 读 `seg.text`（STT 识别出的文字，可能有错）
2. 在文案稿中找到对应的正确文字
3. 确定该时间窗口内实际说了哪些内容（**不要**把相邻窗口的内容拉进来）

**文字校正的边界规则（重要！）：**

```
STT 第12段 (104-119s): "For example, irrigation equipment for agriculture trip..."
文案对应文字:    "For example, irrigation equipment for agricultural drip irrigation, GPS tracking devices for livestock tracking and inventory management, and DTU communication products for special scenarios."

⚠️ 错误做法：把整句塞进第12段
  第12段文字中包含 "and DTU communication..." → 这在 104-119s 里没说！
  
✅ 正确做法： 
  第12段 (104-119s) → 只写到 "inventory management,"
  第13段 (119-125s) → "and DTU communication products for special scenarios."
  因为 STT 在第13段里才识别出 "And DTU..."，说明这是用户在第13段时间窗口内说的
```

**判断每段文字边界的可靠方法：**
- 看 STT 原文在该段识别出了什么文字 — 那就是该时间窗口内实际说的内容
- 校正时只修正识别错误的单词，不要扩大文字范围
- 如果文案稿的一句话被 STT 切成两段，校正时也要切成两段，断句位置参考 STT 的断点

### 2.3 常见错误修正参考

| STT 识别错误 | 正确文字 | 说明 |
|---|---|---|
| Jenna | Janine | 人名听错 |
| client-form | platform | 发音相近词 |
| ex-sales | ace sales | 发音相近词 |
| industry IOT | industrial IoT | 缩写误读 |
| Tigers | Tags | 产品名听错 |
| completely | the company | 整词听错 |
| agriculture trip | agricultural drip | 连读听错 |
| R&D development | R&D | 冗余词 |
| yuan | RMB | 货币单位 |

### 2.4 中文翻译

对校正后的英文逐条翻译成中文：
- 译文自然口语化
- 专业术语一致
- 每段中文文字长度控制在时间窗口可读完的范围内

---

## 步骤3：生成双语 SRT

### 3.1 严格保持 STT 框架

输出 SRT 必须满足：
- **句段数 = STT 的 segments 长度**
- **每段序号 = STT 的 id**
- **每段起始时间 = STT 的 start**
- **每段结束时间 = STT 的 end**
- **每段第1行 = 校正后的英文**
- **每段第2行 = 中文翻译**

### 3.2 生成 SRT

```powershell
python .opencode\skills\音生文字幕器\scripts\build_bilingual_srt.py --segments segments_bilingual.json --output 双语字幕_上英下中.srt
```

或者直接在 Python 中逐行组装，因为 SRT 格式简单，不依赖脚本也能完成。

### 3.3 交付检查清单

生成后逐条检查：

```
□ 段数 = STT 段数？
□ 每段 start = STT start？
□ 每段 end = STT end？
□ 英文已替换为文案稿的正确文字？
□ 中文翻译已添加？
□ 每段文字没有"溢出"到相邻窗口的范围？
```

---

## 步骤4：组织输出

项目文件夹内容：

```
项目名称_YYYYMMDD\
├── 原声_主题名.mp3            ← 输入的音频（改名后）
├── 文案稿_主题名.txt          ← 输入的文案稿
├── _STT原始提炼稿.srt         ← STT 原始识别（时间轴参照）
└── 双语字幕_上英下中.srt       ← 最终字幕 ✓（导入剪映用）
```

剪映导入方法：
1. 导入视频素材到时间轴
2. 「音频」→「导入音频」→ 选择原始音频文件
3. 「文本」→「导入字幕」→ 选择 `双语字幕_上英下中.srt`
4. 在轨道上选中字幕，右侧样式面板调整为上英下中双行显示

---

## 迭代历史 — 关键教训

本技能经过多次迭代才达到可靠效果，以下是解决过的关键问题：

| 问题 | 解决方式 |
|---|---|
| STT 文字有错，直接使用不准确 | 用用户提供的文案稿逐句校正 |
| 校正时误加相邻窗口文字，导致字幕不同步 | **核心教训**：每段文字必须严格限定在该时间窗口内实际说出的内容 |
| 输出 SRT 句段数与 STT 不一致 | **强制规则**：输出 SRT 的段数、时间点必须与 STT 原始输出完全一致 |
| 自动对齐算法不可靠 | 由 Claude 人工逐段对照文案稿和 STT，确保匹配准确 |
