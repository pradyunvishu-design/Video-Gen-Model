"""Deterministic, evidence-grounded source pointers; no dialogue captions or camera motion."""
from __future__ import annotations

import math
import re
from pathlib import Path


def normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9$%]+", "", text.casefold())


def exact_word_box(line: dict, quote: str) -> list[float]:
    """Resolve whole OCR words only, never approximate a box from string length."""
    expected = normalized(quote)
    matches = []
    words = line['words']
    for start in range(len(words)):
        value = ''
        for end in range(start, len(words)):
            value += normalized(words[end]['text'])
            if value == expected:
                boxes = [w['box'] for w in words[start:end+1]]
                x, y = min(b[0] for b in boxes), min(b[1] for b in boxes)
                matches.append([x, y, max(b[0]+b[2] for b in boxes)-x,
                                max(b[1]+b[3] for b in boxes)-y])
            if len(value) >= len(expected):
                break
    if not expected or len(matches) != 1:
        raise ValueError(f'Expected one exact visible phrase, found {len(matches)}: {quote}')
    return matches[0]


def validate(cues: list[dict], seconds: float) -> None:
    previous_end = 0.0
    for cue in sorted(cues, key=lambda c: c['start']):
        x, y, w, h = cue['box']
        if not all(math.isfinite(v) for v in (x,y,w,h,cue['start'],cue['end'])):
            raise ValueError('Non-finite source annotation')
        if not (0 <= x < x+w <= 1920 and 0 <= y < y+h <= 1010):
            raise ValueError('Cue would leave source area or overlap source credit')
        if not cue.get('quote') or not cue.get('rationale'):
            raise ValueError('Every cue needs source text and narrative purpose')
        if not (previous_end <= cue['start'] < cue['end'] <= seconds):
            raise ValueError('Cues must be sequential and remain inside the shot')
        if cue['kind'] not in ('cursor', 'underline'):
            raise ValueError('Unsupported pointer type')
        if cue['kind'] == 'underline' and (w > 640 or h > 62 or len(cue['quote'].split()) > 12):
            raise ValueError('Use a cursor for long or multiline evidence')
        if cue['kind'] == 'cursor' and (x < 175 or y+h/2 > 890):
            raise ValueError('Not enough clear margin for the cursor path')
        previous_end = cue['end']


def smootherstep(value: float) -> float:
    t = min(1., max(0., value))
    return t*t*t*(t*(t*6-15)+10)


def ass_time(seconds: float) -> str:
    centis = round(seconds*100)
    return f'{centis//360000}:{centis//6000%60:02}:{centis//100%60:02}.{centis%100:02}'


def write_pointer_ass(cues: list[dict], seconds: float, destination: Path, fps: int = 30) -> Path:
    """Frame-sampled subpixel curves avoid cursor wobble and platform animation drift."""
    validate(cues, seconds)
    lines = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1920', 'PlayResY: 1080',
             'ScaledBorderAndShadow: yes', '', '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             'Style: Cue,Arial,20,&H00FFFFFF,&H00FFFFFF,&H00232628,&H60000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1',
             '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    # Conventional white cursor, mirrored to point up-right from the empty left margin.
    # Its top-right tip is nearest the text.
    cursor = 'm 58 0 l 13 31 34 31 23 53 34 58 44 35 58 47 58 0'
    for frame in range(math.ceil(seconds*fps)):
        t = frame/fps
        cue = next((c for c in cues if c['start'] <= t < c['end']), None)
        if cue is None:
            continue
        age = t-cue['start']
        alpha = round(255*(1-min(1., age/.12, (cue['end']-t)/.12)))
        x,y,w,h = cue['box']
        if cue['kind'] == 'underline':
            width = max(.1, w*smootherstep(age/.42))
            tags = f'\\pos({x:.2f},{y+h+4:.2f})\\1c&H454DB8&\\bord0\\shad0'
            drawing = f'm 0 0 l {width:.2f} 0 {width:.2f} 3.5 0 3.5 0 0'
        else:
            progress = smootherstep(age/.72)
            # Tip stops 12px left of first word. Cursor body stays in the margin.
            tip_x = x-12-95*(1-progress)
            tip_y = y+h/2+34*(1-progress)
            tags = f'\\pos({tip_x-58:.2f},{tip_y:.2f})\\1c&HFFFFFF&\\3c&H222426&\\bord2.8\\shad1.5'
            drawing = cursor
        body = '{\\an7'+tags+f'\\alpha&H{alpha:02X}&\\p1'+'}'+drawing
        lines.append(f'Dialogue: 0,{ass_time(t)},{ass_time(min(seconds,(frame+1)/fps))},Cue,,0,0,0,,{body}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return destination


def ass_filter(path: Path) -> str:
    value = path.resolve().as_posix().replace(':', r'\:').replace("'", r"\'")
    return f"ass='{value}'"
