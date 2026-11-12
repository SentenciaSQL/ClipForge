/** Helpers for CapCut-like per-cue subtitle editing (clip-relative times). */

export interface SubtitleCue {
  text: string;
  start: number;
  end: number;
}

export function clipDurationSeconds(editStart: number, editEnd: number, fallback = 1): number {
  return Math.max(0.5, Number(editEnd) - Number(editStart) || fallback);
}

export function normalizeCue(
  cue: Partial<SubtitleCue>,
  options: { duration: number; minSpan?: number }
): SubtitleCue {
  const minSpan = options.minSpan ?? 0.12;
  const dur = Math.max(0.5, options.duration);
  let start = Math.max(0, Number(cue.start) || 0);
  let end = Math.max(start + minSpan, Number(cue.end) || start + minSpan);
  if (start > dur - minSpan) start = Math.max(0, dur - minSpan);
  if (end > dur) end = dur;
  if (end <= start) end = Math.min(dur, start + minSpan);
  return {
    text: String(cue.text || '').trim() || '…',
    start: round3(start),
    end: round3(end),
  };
}

export function sortCues(cues: SubtitleCue[]): SubtitleCue[] {
  return [...cues].sort((a, b) => a.start - b.start || a.end - b.end);
}

export function nudgeCue(
  cue: SubtitleCue,
  delta: number,
  options: { duration: number; minSpan?: number }
): SubtitleCue {
  const minSpan = options.minSpan ?? 0.12;
  const duration = options.duration;
  const span = Math.max(minSpan, cue.end - cue.start);
  let start = cue.start + delta;
  let end = cue.end + delta;
  if (start < 0) {
    end -= start;
    start = 0;
  }
  if (end > duration) {
    const overflow = end - duration;
    start = Math.max(0, start - overflow);
    end = duration;
  }
  if (end - start < span && end < duration) {
    end = Math.min(duration, start + span);
  }
  return normalizeCue({ ...cue, start, end }, { duration, minSpan });
}

export function nudgeAllCues(cues: SubtitleCue[], delta: number, duration: number): SubtitleCue[] {
  return sortCues(cues.map((cue) => nudgeCue(cue, delta, { duration })));
}

export function splitCueAt(
  cue: SubtitleCue,
  options: { atSeconds?: number; atChar?: number } = {}
): [SubtitleCue, SubtitleCue] | null {
  const text = cue.text.trim();
  if (!text) return null;
  const span = cue.end - cue.start;
  if (span < 0.3) return null;

  let splitChar = options.atChar;
  if (splitChar == null || splitChar <= 0 || splitChar >= text.length) {
    const mid = Math.floor(text.length / 2);
    const window = text.slice(Math.max(0, mid - 12), Math.min(text.length, mid + 12));
    const candidates = [
      window.lastIndexOf('. '),
      window.lastIndexOf('! '),
      window.lastIndexOf('? '),
      window.lastIndexOf(', '),
      window.lastIndexOf(' '),
    ].filter((idx) => idx >= 0);
    const local = candidates.length ? Math.max(...candidates) : -1;
    splitChar = local >= 0 ? Math.max(0, mid - 12) + local + 1 : mid;
  }
  while (splitChar < text.length && text[splitChar] === ' ') splitChar++;
  if (splitChar <= 0 || splitChar >= text.length) return null;

  const leftText = text.slice(0, splitChar).trim();
  const rightText = text.slice(splitChar).trim();
  if (!leftText || !rightText) return null;

  let splitTime =
    options.atSeconds != null &&
    options.atSeconds > cue.start + 0.08 &&
    options.atSeconds < cue.end - 0.08
      ? options.atSeconds
      : cue.start + span * (leftText.length / text.length);
  splitTime = Math.max(cue.start + 0.08, Math.min(cue.end - 0.08, splitTime));

  return [
    { text: leftText, start: round3(cue.start), end: round3(splitTime) },
    { text: rightText, start: round3(splitTime), end: round3(cue.end) },
  ];
}

export function mergeCues(a: SubtitleCue, b: SubtitleCue): SubtitleCue {
  const first = a.start <= b.start ? a : b;
  const second = a.start <= b.start ? b : a;
  return {
    text: `${first.text.trim()} ${second.text.trim()}`.trim(),
    start: round3(Math.min(first.start, second.start)),
    end: round3(Math.max(first.end, second.end)),
  };
}

export function cueAtTime(cues: SubtitleCue[], time: number, offset = 0): SubtitleCue | null {
  const t = time - offset;
  for (const cue of cues) {
    if (t >= cue.start - 0.01 && t < cue.end + 0.01) return cue;
  }
  return null;
}

export function cuesFromTranscriptionSegments(
  segments: Array<{ start: number; end: number; text: string }>,
  options: { clipStart: number; clipEnd: number }
): SubtitleCue[] {
  const duration = Math.max(0.5, options.clipEnd - options.clipStart);
  const out: SubtitleCue[] = [];
  for (const seg of segments || []) {
    const absStart = Number(seg.start);
    const absEnd = Number(seg.end);
    if (!(absEnd > options.clipStart) || !(absStart < options.clipEnd)) continue;
    const start = Math.max(0, absStart - options.clipStart);
    const end = Math.min(duration, Math.max(start + 0.12, absEnd - options.clipStart));
    const text = String(seg.text || '').trim();
    if (!text) continue;
    out.push(normalizeCue({ text, start, end }, { duration }));
  }
  return sortCues(out);
}

export function cuesFromPlainText(text: string, duration: number): SubtitleCue[] {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (!cleaned) return [];
  const parts = cleaned
    .split(/(?<=[.!?])\s+|\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
  const chunks = parts.length ? parts : [cleaned];
  const lines: string[] = [];
  for (const chunk of chunks) {
    const words = chunk.split(/\s+/);
    if (words.length <= 8) {
      lines.push(chunk);
      continue;
    }
    for (let i = 0; i < words.length; i += 6) {
      lines.push(words.slice(i, i + 6).join(' '));
    }
  }
  const totalChars = lines.reduce((sum, line) => sum + line.length, 0) || 1;
  const cues: SubtitleCue[] = [];
  let cursor = 0;
  for (const line of lines) {
    const share = Math.max(0.35, (line.length / totalChars) * duration);
    const start = cursor;
    const end = Math.min(duration, start + share);
    cues.push(normalizeCue({ text: line, start, end }, { duration }));
    cursor = end;
  }
  if (cues.length) cues[cues.length - 1].end = round3(duration);
  return cues;
}

function round3(value: number): number {
  return Math.round(value * 1000) / 1000;
}
