#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "yt-dlp>=2024.10.0",
#   "requests>=2.31",
#   "python-dotenv>=1.0",
#   "faster-whisper>=1.0",
# ]
# ///
"""
Fetch the N newest videos from a YouTube channel, pull their (Chinese, with
English fallback) transcripts, and ask DeepSeek to extract conditional trading
strategies in the form "WHEN <condition> THEN <action>". Renders an HTML report.

Usage:
    ./extract_strategies.py <channel_url_or_handle> [--n 5] [-o report.html]

Reads DEEPSEEK_API_KEY from the environment or from a .env file in CWD / next
to the script.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# Prefer Chinese (Mandarin, all variants) then English, then any auto track.
SUBTITLE_LANG_PRIORITY = [
    "zh", "zh-Hans", "zh-CN", "zh-SG",
    "zh-Hant", "zh-TW", "zh-HK",
    "en", "en-US", "en-GB",
]

SYSTEM_PROMPT = (
    "你是一個從財經 / 交易影片逐字稿中萃取具體交易策略的助手。"
    "輸入可能是中文或英文。一個「策略」是條件式規則："
    "「當 <可觀察的市場條件> 發生時，執行 <具體動作>」。"
    "一支影片通常包含多條這類規則，請把講者明確陳述或清楚暗示的每一條都列出。"
    "不要捏造一般性的建議。若逐字稿中沒有可執行的規則，請回傳空列表。"
    "\n\n"
    "**精確性要求（非常重要）**：策略必須是可被別人在沒看影片的情況下執行的。"
    "請從逐字稿中**逐字抓出講者真的講出口的數字**，包括：\n"
    "  • 價位（例如 80,000 / 78,500 / 0.0234）\n"
    "  • 百分比（例如 +5% / -3%）\n"
    "  • 時間框架（日線 / 4 小時 / 週線）\n"
    "  • 指標數值（資金費率 +0.01% / RSI 70 / 成交量 X 倍）\n"
    "  • 商品代號（BTC / ETH / TSLA / SPY）\n"
    "禁止使用「某條線」「關鍵價位」「某個水平」「重要支撐」這類含糊用詞——"
    "若逐字稿真的沒有給數字，請在欄位最後標註「（講者未明確給出數值）」，"
    "而不是用模糊詞混過去。逐字稿提到的所有具體數字都應該被引用到對應的策略中。"
    "\n\n"
    "所有輸出（trigger / action / rationale / caveats）都必須使用「繁體中文（zh-TW）」。"
    "只回傳 JSON，不要有其他文字。"
)

USER_PROMPT_TEMPLATE = """請從以下逐字稿中萃取每一條交易策略。

回傳 JSON，格式必須完全如下：

{{
  "strategies": [
    {{
      "trigger":  "市場條件 / 訊號 / 事件，必須包含講者講出的具體數字（價位、百分比、時間框架、指標值）",
      "action":   "具體交易動作：含商品代號、方向、進場價、出場/止盈價、止損價、倉位大小（若有）",
      "rationale": "講者的理由，一句話；若無則填空字串",
      "caveats":  "停損、時間框架、失效條件、風險提醒；若無則填空字串"
    }}
  ]
}}

若無任何具體規則，回傳 {{"strategies": []}}。

**再次強調**：trigger 與 action 中所有講者提到的數字（價位、百分比、指標值、時間週期）
都必須原樣寫進去；若講者只說「某個價位」「重要關卡」而沒給出數字，請在該句末
加上「（講者未明確給出數值）」字樣，不可自行用「關鍵支撐線」「某個水平」這種
含糊詞代替。所有欄位內容請務必使用繁體中文（zh-TW）。

影片標題：{title}
頻道：{uploader}
發佈日期：{upload_date}

逐字稿：
\"\"\"
{transcript}
\"\"\"
"""

# Bumped whenever the prompt changes — invalidates cached LLM responses.
PROMPT_VERSION = "v2-precise"


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

CACHE_DIR = Path(__file__).resolve().parent / "cache"
TRANSCRIPT_DIR = CACHE_DIR / "transcripts"
STRATEGY_DIR = CACHE_DIR / "strategies"


def _ensure_cache_dirs() -> None:
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)


def _prompt_fingerprint() -> str:
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode())
    h.update(b"\0")
    h.update(SYSTEM_PROMPT.encode("utf-8"))
    h.update(b"\0")
    h.update(USER_PROMPT_TEMPLATE.encode("utf-8"))
    h.update(b"\0")
    h.update(DEEPSEEK_MODEL.encode())
    return h.hexdigest()[:12]


def transcript_cache_path(video_id: str) -> Path:
    return TRANSCRIPT_DIR / f"{video_id}.json"


def strategy_cache_path(video_id: str, transcript: str) -> Path:
    h = hashlib.sha256()
    h.update(_prompt_fingerprint().encode())
    h.update(b"\0")
    h.update(transcript.encode("utf-8"))
    digest = h.hexdigest()[:16]
    return STRATEGY_DIR / f"{video_id}__{digest}.json"


def load_cached_transcript(video_id: str) -> dict | None:
    p = transcript_cache_path(video_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_cached_transcript(video_id: str, payload: dict) -> None:
    transcript_cache_path(video_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_cached_strategies(video_id: str, transcript: str) -> list[dict] | None:
    p = strategy_cache_path(video_id, transcript)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("strategies")
    except (OSError, json.JSONDecodeError):
        return None


def save_cached_strategies(video_id: str, transcript: str,
                           strategies: list[dict]) -> None:
    strategy_cache_path(video_id, transcript).write_text(
        json.dumps({"strategies": strategies, "prompt": _prompt_fingerprint()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")


# ---------------------------------------------------------------------------
# yt-dlp helpers
# ---------------------------------------------------------------------------

def normalize_channel_url(arg: str) -> str:
    if arg.startswith(("http://", "https://")):
        url = arg
    elif arg.startswith("@"):
        url = f"https://www.youtube.com/{arg}"
    else:
        url = f"https://www.youtube.com/@{arg}"
    if "/videos" not in url and "/channel/" not in url and "playlist" not in url:
        url = url.rstrip("/") + "/videos"
    return url


def list_recent_videos(channel_url: str, n: int) -> list[dict]:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlistend": n,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
    entries = info.get("entries") or []
    if not entries:
        raise SystemExit(f"No videos found at {channel_url}")
    return entries[:n]


def _pick_lang(available: dict, priority: list[str]) -> str | None:
    """Pick the highest-priority lang code present in `available` (dict from
    yt-dlp's `subtitles` / `automatic_captions`). Falls back to a prefix match."""
    keys = list(available.keys())
    lower = {k.lower(): k for k in keys}
    for lang in priority:
        if lang.lower() in lower:
            return lower[lang.lower()]
    # Prefix fallback (avoid translation tracks like "en-zh").
    for prefix in ("zh", "en"):
        for k in keys:
            if k.lower().startswith(prefix) and "-" not in k.removeprefix(prefix + "-").removeprefix(prefix):
                return k
        # Last resort: any key starting with the prefix, even hyphenated.
        for k in keys:
            if k.lower().startswith(prefix):
                return k
    return None


def fetch_transcript(video_id: str, workdir: Path,
                     verbose: bool = False) -> tuple[str, str, dict]:
    """Return (plain-text transcript, lang code used, full metadata).

    Strategy:
      1. Probe metadata (1 request) to see what subtitle tracks exist.
      2. Pick the best available lang from manual > auto.
      3. Download just that one track. Retry once on 429 with backoff.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"

    probe_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with YoutubeDL(probe_opts) as ydl:
        meta = ydl.extract_info(url, download=False)

    manual = meta.get("subtitles") or {}
    auto = meta.get("automatic_captions") or {}

    chosen_lang = _pick_lang(manual, SUBTITLE_LANG_PRIORITY)
    track_kind = "manual"
    if not chosen_lang:
        chosen_lang = _pick_lang(auto, SUBTITLE_LANG_PRIORITY)
        track_kind = "auto"
    if not chosen_lang:
        if verbose:
            print(f"    available manual: {sorted(manual.keys())[:8]}", flush=True)
            print(f"    available auto:   {sorted(auto.keys())[:8]}", flush=True)
        return "", "", meta

    out_tmpl = str(workdir / "%(id)s.%(ext)s")
    dl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "skip_download": True,
        "writesubtitles": track_kind == "manual",
        "writeautomaticsub": track_kind == "auto",
        "subtitleslangs": [chosen_lang],
        "subtitlesformat": "vtt",
        "outtmpl": out_tmpl,
    }

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with YoutubeDL(dl_opts) as ydl:
                ydl.extract_info(url, download=True)
            last_err = None
            break
        except DownloadError as ex:
            last_err = ex
            msg = str(ex)
            if "429" in msg or "Too Many Requests" in msg:
                wait = 8 * (attempt + 1)
                if verbose:
                    print(f"    429 received; sleeping {wait}s before retry", flush=True)
                time.sleep(wait)
                continue
            break
    if last_err is not None:
        raise last_err

    files = list(workdir.glob(f"{video_id}*.vtt"))
    if not files:
        return "", chosen_lang, meta
    text = vtt_to_text(files[0].read_text(encoding="utf-8", errors="ignore"))
    # Clean up so we don't accidentally re-pick this file for the next video.
    for f in files:
        try:
            f.unlink()
        except OSError:
            pass
    return text, f"{chosen_lang} ({track_kind})", meta


# ---------------------------------------------------------------------------
# Whisper fallback (faster-whisper)
# ---------------------------------------------------------------------------

_WHISPER_MODEL = None  # lazy-loaded singleton.


def _load_whisper(model_size: str, device: str, compute_type: str | None = None):
    """Lazy-import & cache a faster-whisper WhisperModel."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL
    from faster_whisper import WhisperModel  # heavy import, defer it.
    if compute_type is None:
        compute_type = "float16" if device == "cuda" else "int8"
    print(f"  loading whisper model={model_size} device={device} "
          f"compute={compute_type} (one-time)…", flush=True)
    _WHISPER_MODEL = WhisperModel(model_size, device=device, compute_type=compute_type)
    return _WHISPER_MODEL


def download_audio(video_id: str, workdir: Path) -> Path:
    """Download bestaudio for a YouTube video and return the local path."""
    out_tmpl = str(workdir / "%(id)s.%(ext)s")
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "format": "bestaudio/best",
        "outtmpl": out_tmpl,
    }
    url = f"https://www.youtube.com/watch?v={video_id}"
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)
            last_err = None
            break
        except DownloadError as ex:
            last_err = ex
            if "429" in str(ex) or "Too Many Requests" in str(ex):
                time.sleep(8 * (attempt + 1))
                continue
            break
    if last_err is not None:
        raise last_err

    files = [p for p in workdir.iterdir() if p.stem == video_id]
    if not files:
        raise RuntimeError(f"audio download produced no file for {video_id}")
    return files[0]


def transcribe_with_whisper(audio_path: Path, model_size: str, device: str,
                            language: str = "zh") -> str:
    """Run Whisper STT on an audio file; return concatenated transcript text."""
    model = _load_whisper(model_size, device)
    t0 = time.time()
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        beam_size=5,
        condition_on_previous_text=False,  # avoids hallucination loops on repeats.
    )
    parts: list[str] = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            parts.append(text)
    dur = time.time() - t0
    audio_dur = info.duration if info else 0.0
    print(f"  whisper: detected lang={info.language} "
          f"audio={audio_dur:.0f}s wall={dur:.1f}s "
          f"chars={sum(len(p) for p in parts)}", flush=True)
    return " ".join(parts)


_TS_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3} --> ")
_TAG_RE = re.compile(r"<[^>]+>")


def vtt_to_text(vtt: str) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if _TS_RE.match(line) or "-->" in line:
            continue
        line = _TAG_RE.sub("", line)
        if not line or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return " ".join(lines)


# ---------------------------------------------------------------------------
# DeepSeek
# ---------------------------------------------------------------------------

def call_deepseek(api_key: str, title: str, uploader: str, upload_date: str,
                  transcript: str) -> list[dict]:
    max_chars = 60_000
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + " …[truncated]"

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                title=title, uploader=uploader, upload_date=upload_date,
                transcript=transcript,
            )},
        ],
        "temperature": 0.2,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=180,
    )
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Salvage anything that looks like JSON.
        m = re.search(r"\{.*\}", content, re.S)
        data = json.loads(m.group(0)) if m else {"strategies": []}
    items = data.get("strategies") or []
    # Defensive normalization.
    return [
        {
            "trigger":  str(s.get("trigger", "")).strip(),
            "action":   str(s.get("action", "")).strip(),
            "rationale": str(s.get("rationale", "")).strip(),
            "caveats":  str(s.get("caveats", "")).strip(),
        }
        for s in items if isinstance(s, dict)
    ]


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

HTML_HEAD = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>交易策略 — {channel}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.5 system-ui, sans-serif; max-width: 900px; margin: 2rem auto;
         padding: 0 1rem; }}
  h1 {{ margin-bottom: .25rem; }}
  .meta {{ color: #888; font-size: 13px; margin-bottom: 2rem; }}
  .video {{ border: 1px solid #ccc4; border-radius: 8px; padding: 1rem 1.25rem;
            margin: 1.25rem 0; background: #8881; }}
  .video h2 {{ margin: 0 0 .25rem; font-size: 18px; }}
  .video h2 .idx {{ color: #888; font-weight: normal; margin-right: .5em; }}
  .video .sub {{ color: #888; font-size: 12px; margin-bottom: .9rem; }}
  .video a {{ color: inherit; }}
  ol.strategies {{ padding-left: 1.2rem; margin: 0; }}
  ol.strategies > li {{ margin: .6rem 0; padding: .6rem .8rem;
                        background: #fff2; border-radius: 6px; }}
  .row {{ margin: .15rem 0; }}
  .row b {{ display: inline-block; min-width: 80px; color: #4a90e2; }}
  .empty {{ color: #888; font-style: italic; }}
  .skip {{ color: #c66; font-style: italic; }}
</style>
<h1>交易策略整理</h1>
<div class="meta">頻道：<a href="{channel_url}">{channel}</a> · 最新 {n} 支影片 · 產生日期 {date}</div>
"""

HTML_TAIL = "</html>\n"


def render_strategy(s: dict) -> str:
    parts = [
        f'<div class="row"><b>觸發條件</b> {html.escape(s["trigger"])}</div>',
        f'<div class="row"><b>執行動作</b> {html.escape(s["action"])}</div>',
    ]
    if s["rationale"]:
        parts.append(f'<div class="row"><b>理由</b> {html.escape(s["rationale"])}</div>')
    if s["caveats"]:
        parts.append(f'<div class="row"><b>注意事項</b> {html.escape(s["caveats"])}</div>')
    return "<li>" + "".join(parts) + "</li>"


def render_video(idx: int, total: int, title: str, vid: str, uploader: str,
                 upload_date: str, lang: str, strategies: list[dict],
                 note: str = "") -> str:
    head = (
        f'<section class="video">'
        f'<h2><span class="idx">{idx}/{total}</span>'
        f'<a href="https://www.youtube.com/watch?v={vid}" target="_blank" rel="noopener">'
        f'{html.escape(title)}</a></h2>'
        f'<div class="sub">{html.escape(uploader)} · {html.escape(upload_date)}'
        f'{" · subs: " + html.escape(lang) if lang else ""}</div>'
    )
    if note:
        body = f'<div class="skip">{html.escape(note)}</div>'
    elif not strategies:
        body = '<div class="empty">未找到可執行的交易策略。</div>'
    else:
        body = "<ol class=\"strategies\">" + "".join(render_strategy(s) for s in strategies) + "</ol>"
    return head + body + "</section>"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def fmt_date(d: str | None) -> str:
    if not d or len(d) != 8:
        return d or "unknown"
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("channel", help="Channel URL, @handle, or handle")
    ap.add_argument("--n", type=int, default=5, help="How many recent videos (default 5)")
    ap.add_argument("-o", "--output", default="strategies.html",
                    help="HTML output file (default: strategies.html)")
    ap.add_argument("--no-cache", action="store_true",
                    help="Ignore cached transcripts and LLM responses")
    ap.add_argument("--refresh-llm", action="store_true",
                    help="Reuse cached transcripts but re-call DeepSeek")
    ap.add_argument("--no-whisper", action="store_true",
                    help="Skip the Whisper STT fallback for videos without subtitles")
    ap.add_argument("--whisper-model", default="large-v3",
                    help="faster-whisper model size (tiny|base|small|medium|"
                         "large-v3|large-v3-turbo). Default: large-v3")
    ap.add_argument("--whisper-device", default="auto",
                    help="auto|cuda|cpu (default: auto-detect)")
    ap.add_argument("--whisper-lang", default="zh",
                    help="Language hint for Whisper (zh|en|...). Default: zh")
    args = ap.parse_args()
    _ensure_cache_dirs()

    # Load .env from CWD and from next-to-script, without overriding real env.
    load_dotenv()
    load_dotenv(Path(__file__).resolve().parent / ".env")

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY is not set (env or .env)", file=sys.stderr)
        return 2

    channel_url = normalize_channel_url(args.channel)
    print(f"# Channel: {channel_url}", flush=True)

    entries = list_recent_videos(channel_url, args.n)
    total = len(entries)

    sections: list[str] = []
    channel_label = entries[0].get("channel") or args.channel

    use_cache = not args.no_cache

    whisper_device = args.whisper_device
    if whisper_device == "auto":
        try:
            import ctypes  # noqa
            # Cheap way: ask faster-whisper's underlying ctranslate2.
            from ctranslate2 import get_cuda_device_count  # type: ignore
            whisper_device = "cuda" if get_cuda_device_count() > 0 else "cpu"
        except Exception:
            whisper_device = "cpu"

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        fetched_from_youtube = 0  # only sleep between live fetches.
        for i, e in enumerate(entries, 1):
            vid = e.get("id")
            title = e.get("title") or vid
            print(f"[{i}/{total}] {title}", flush=True)

            transcript = ""
            lang = ""
            uploader = ""
            upload_date = ""

            cached = load_cached_transcript(vid) if use_cache else None
            if cached:
                transcript = cached.get("transcript", "")
                lang = cached.get("lang", "")
                uploader = cached.get("uploader", "")
                upload_date = cached.get("upload_date", "")
                title = cached.get("title", title)
                print(f"  [cache] transcript: lang={lang} chars={len(transcript)}",
                      flush=True)
            else:
                if fetched_from_youtube > 0:
                    time.sleep(2)  # be polite to YouTube; avoids 429.
                try:
                    transcript, lang, meta = fetch_transcript(vid, workdir, verbose=True)
                    fetched_from_youtube += 1
                except Exception as ex:
                    msg = f"transcript fetch failed: {ex}"
                    print("  ! " + msg, flush=True)
                    sections.append(render_video(i, total, title, vid, "", "", "", [], note=msg))
                    continue

                uploader = meta.get("uploader") or meta.get("channel") or ""
                upload_date = fmt_date(meta.get("upload_date"))

                if not transcript:
                    if args.no_whisper:
                        msg = "no Chinese or English subtitles available (whisper disabled)"
                        print("  ! " + msg, flush=True)
                        sections.append(render_video(i, total, title, vid, uploader,
                                                     upload_date, "", [], note=msg))
                        continue
                    print(f"  no subs — falling back to whisper "
                          f"({args.whisper_model} on {whisper_device})", flush=True)
                    try:
                        audio_path = download_audio(vid, workdir)
                        transcript = transcribe_with_whisper(
                            audio_path, args.whisper_model, whisper_device,
                            language=args.whisper_lang)
                        try:
                            audio_path.unlink()
                        except OSError:
                            pass
                        lang = f"whisper:{args.whisper_model}:{args.whisper_lang}"
                    except Exception as ex:
                        msg = f"whisper fallback failed: {ex}"
                        print("  ! " + msg, flush=True)
                        sections.append(render_video(i, total, title, vid, uploader,
                                                     upload_date, "", [], note=msg))
                        continue
                    if not transcript:
                        msg = "whisper produced empty transcript"
                        print("  ! " + msg, flush=True)
                        sections.append(render_video(i, total, title, vid, uploader,
                                                     upload_date, "", [], note=msg))
                        continue

                save_cached_transcript(vid, {
                    "title": title, "uploader": uploader,
                    "upload_date": upload_date, "lang": lang,
                    "transcript": transcript,
                })
                print(f"  lang={lang}  chars={len(transcript)}", flush=True)

            channel_label = uploader or channel_label

            cached_strats: list[dict] | None = None
            if use_cache and not args.refresh_llm:
                cached_strats = load_cached_strategies(vid, transcript)
            if cached_strats is not None:
                strategies = cached_strats
                print(f"  [cache] {len(strategies)} strateg"
                      f"{'y' if len(strategies)==1 else 'ies'}", flush=True)
            else:
                try:
                    strategies = call_deepseek(api_key, title, uploader, upload_date, transcript)
                except requests.HTTPError as ex:
                    msg = f"DeepSeek error: {ex.response.status_code} {ex.response.text[:200]}"
                    print("  ! " + msg, flush=True)
                    sections.append(render_video(i, total, title, vid, uploader,
                                                 upload_date, lang, [], note=msg))
                    continue
                except Exception as ex:
                    msg = f"DeepSeek error: {ex}"
                    print("  ! " + msg, flush=True)
                    sections.append(render_video(i, total, title, vid, uploader,
                                                 upload_date, lang, [], note=msg))
                    continue
                save_cached_strategies(vid, transcript, strategies)
                print(f"  → {len(strategies)} strateg"
                      f"{'y' if len(strategies)==1 else 'ies'}", flush=True)

            sections.append(render_video(i, total, title, vid, uploader,
                                         upload_date, lang, strategies))

    from datetime import date
    out = Path(args.output).expanduser().resolve()
    out.write_text(
        HTML_HEAD.format(channel=html.escape(channel_label),
                         channel_url=html.escape(channel_url),
                         n=total, date=date.today().isoformat())
        + "\n".join(sections)
        + HTML_TAIL,
        encoding="utf-8",
    )
    print(f"\nWrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
