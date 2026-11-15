"""Shared pieces for the project diagrams, in the style of controllers_gamepad.svg: cream cards with an amber
border, the cartoon duck, the gamepad with a small neural net, soft flat colors, big plain labels, no hatching.

Each make_<name>.py in this folder builds one diagram from these pieces and writes <name>.svg next to it:

    python3 docs/media/diagrams/make_system_loop.py        # or: make_all.py for every diagram

Everything that carries text sits on a cream card or pill, so the diagrams read on light and dark pages.
Pieces are placed with (x, y, scale); a piece's own origin is its center (the duck's is its body center).
"""
from __future__ import annotations

import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# palette (from controllers_gamepad.svg)
CREAM, AMBER = "#FFF8EC", "#BA7517"
INK, INK2 = "#412402", "#633806"
BLUE_F, BLUE = "#B5D4F4", "#185FA5"
PURPLE, PURPLE_D = "#7F77DD", "#534AB7"
ORANGE, ORANGE_D = "#D85A30", "#993C1D"
GREEN, AMBER_F = "#1D9E75", "#EF9F27"
DUCK_F, DUCK_S = "#FAC775", "#854F0B"
PINK, EYE = "#993556", "#2C2C2A"
# card colors by role
TRAINED = {"fill": "#E3EEFC", "stroke": BLUE}          # parts we train
FROZEN = {"fill": "#DDF3EA", "stroke": GREEN}           # frozen, pretrained parts
WORLD = {"fill": CREAM, "stroke": AMBER}                # simulator and reward
FONT = 'font-family="Helvetica, Arial, sans-serif"'


def head(w: int, h: int, title: str) -> str:
    markers = "".join(
        f'<marker id="{i}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        f'<path d="M2 1L8 5L2 9" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></marker>'
        for i, c in (("arrow", PURPLE), ("arrowp", PINK), ("arrowb", BLUE), ("arrowo", ORANGE)))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">'
            f'<title>{title}</title>\n<defs>{markers}</defs>\n')


def save(name: str, w: int, h: int, title: str, body: list) -> str:
    path = os.path.join(OUT_DIR, f"{name}.svg")
    with open(path, "w") as f:
        f.write(head(w, h, title) + "\n".join(body) + "\n</svg>\n")
    return path


def g(x, y, s, inner: str) -> str:
    return f'<g transform="translate({x:g},{y:g}) scale({s:g})">{inner}</g>'


def rect(x, y, w, h, fill=CREAM, stroke=AMBER, rx=16, sw=1.5) -> str:
    return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx:g}" fill="{fill}" stroke="{stroke}" stroke-width="{sw:g}"/>'


def card(x, y, w, h, role=WORLD, rx=16) -> str:
    return rect(x, y, w, h, role["fill"], role["stroke"], rx)


def text(x, y, s, size=17, weight=600, fill=INK, anchor="middle", italic=False) -> str:
    st = ' font-style="italic"' if italic else ""
    return f'<text x="{x:g}" y="{y:g}" text-anchor="{anchor}" {FONT} font-size="{size:g}" font-weight="{weight}" fill="{fill}"{st}>{s}</text>'


def lines(x, y, rows, size=17, weight=600, fill=INK, lh=1.3, anchor="middle") -> str:
    return "".join(text(x, y + i * size * lh, r, size, weight, fill, anchor) for i, r in enumerate(rows))


def pill(cx, cy, label, size=15, fill=CREAM, stroke=AMBER, pad=14, weight=600, color=INK) -> str:
    w = len(label) * size * 0.56 + 2 * pad
    return rect(cx - w / 2, cy - size * 0.95, w, size * 1.9, fill, stroke, size * 0.95, 1.3) + text(cx, cy + size * 0.35, label, size, weight, color)


def arrow(x1, y1, x2, y2, color=PURPLE, width=2.5, dashed=False, marker="arrow") -> str:
    d = ' stroke-dasharray="5 4"' if dashed else ""
    return (f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" stroke="{color}" stroke-width="{width:g}" '
            f'stroke-linecap="round"{d} marker-end="url(#{marker})"/>')


def curve(d, color=PURPLE, width=2.5, dashed=False, marker="arrow", start=False) -> str:
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    ms = f' marker-start="url(#{marker})"' if start else ""
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width:g}" stroke-linecap="round"{dash}{ms} marker-end="url(#{marker})"/>'


# ── characters (copied from controllers_gamepad.svg) ──────────────────────────────────────────────────────────
_DUCK = ('<path d="M-12,15 L-12,26 M4,15 L4,26" stroke="#D85A30" stroke-width="2.5" stroke-linecap="round"/>'
         '<ellipse cx="0" cy="0" rx="22" ry="16" fill="#FAC775" stroke="#854F0B" stroke-width="1.5"/>'
         '<path d="M-10,-2 Q0,8 10,-2" fill="none" stroke="#854F0B" stroke-width="1.2"/>'
         '<circle cx="16" cy="-18" r="11" fill="#FAC775" stroke="#854F0B" stroke-width="1.5"/>'
         '<polygon points="26,-20 37,-16 26,-12" fill="#D85A30" stroke="#993C1D" stroke-width="1" stroke-linejoin="round"/>'
         '<circle cx="19" cy="-21" r="2" fill="#2C2C2A"/>'
         '<line x1="14" y1="-29" x2="12" y2="-36" stroke="#854F0B" stroke-width="1.5"/><circle cx="12" cy="-37" r="2.2" fill="#D85A30"/>')


def duck(x, y, s=1.0, flip=False) -> str:
    """The cartoon duck, body center at (x, y), facing right (or left when flip)."""
    return f'<g transform="translate({x:g},{y:g}) scale({-s if flip else s:g},{s:g})">{_DUCK}</g>'


def duck_fallen(x, y, s=1.0) -> str:
    """A duck that has fallen over: lying on its side."""
    return f'<g transform="translate({x:g},{y:g}) rotate(82) scale({s:g})">{_DUCK}</g>'


def score_pill(cx, cy, label, good=True, size=17) -> str:
    """A small round score tag: green for points, red for a penalty."""
    fill, stroke, ink = ("#DDF3EA", GREEN, "#0F6B4F") if good else ("#FBE3DC", ORANGE, ORANGE_D)
    w = len(label) * size * 0.62 + 22
    return rect(cx - w / 2, cy - size * 0.95, w, size * 1.9, fill, stroke, size * 0.95, 2) + text(cx, cy + size * 0.36, label, size, 700, ink)


_PAD = ('<path d="M-40,-14 Q-40,-22 -30,-22 L30,-22 Q40,-22 40,-14 L46,14 Q48,24 38,24 Q30,24 24,12 L-24,12 Q-30,24 -38,24 '
        'Q-48,24 -46,14 Z" fill="#B5D4F4" stroke="#185FA5" stroke-width="{sw}" stroke-linejoin="round"/>')
_NET_FULL = ('<rect x="-32" y="-6" width="10" height="3" rx="1" fill="#185FA5"/><rect x="-28.5" y="-9.5" width="3" height="10" rx="1" fill="#185FA5"/>'
             '<circle cx="26" cy="-9" r="2.6" fill="#D85A30"/><circle cx="32" cy="-3" r="2.6" fill="#1D9E75"/>'
             '<circle cx="26" cy="3" r="2.6" fill="#EF9F27"/><circle cx="20" cy="-3" r="2.6" fill="#7F77DD"/>'
             '<g stroke="#7F77DD" stroke-width="0.7"><line x1="-10" y1="-12" x2="0" y2="-15"/><line x1="-10" y1="-12" x2="0" y2="-7"/>'
             '<line x1="-10" y1="-12" x2="0" y2="1"/><line x1="-10" y1="-2" x2="0" y2="-15"/><line x1="-10" y1="-2" x2="0" y2="-7"/>'
             '<line x1="-10" y1="-2" x2="0" y2="1"/><line x1="0" y1="-15" x2="10" y2="-7"/><line x1="0" y1="-7" x2="10" y2="-7"/>'
             '<line x1="0" y1="1" x2="10" y2="-7"/></g>'
             + "".join(f'<circle cx="{a}" cy="{b}" r="2.2" fill="#534AB7"/>' for a, b in
                       ((-10, -12), (-10, -2), (0, -15), (0, -7), (0, 1), (10, -7))))
_NET_SMALL = ('<g stroke="#7F77DD" stroke-width="1"><line x1="-10" y1="-12" x2="0" y2="-7"/><line x1="-10" y1="-2" x2="0" y2="-7"/>'
              '<line x1="0" y1="-7" x2="10" y2="-7"/></g>'
              + "".join(f'<circle cx="{a}" cy="{b}" r="3" fill="#534AB7"/>' for a, b in ((-10, -12), (-10, -2), (0, -7), (10, -7))))


def gamepad(x, y, s=1.0, small=False) -> str:
    """The gamepad with a neural net on it: the full one (a big brain) or the small one (a copy)."""
    return g(x, y, s, _PAD.format(sw=2.2 if small else 1.5) + (_NET_SMALL if small else _NET_FULL))


def wire(x1, y1, x2, y2) -> str:
    """The blue cable from a gamepad down to a duck."""
    m = (y1 + y2) / 2
    return (f'<path d="M{x1:g},{y1:g} C{x1:g},{m:g} {x2:g},{m:g} {x2:g},{y2:g}" fill="none" stroke="{BLUE}" '
            f'stroke-width="2" stroke-linecap="round"/>')


# ── small illustrations (each centered on its origin) ─────────────────────────────────────────────────────────
def box(x, y, s=1.0) -> str:
    """The box the ducks push (28 x 10 cm), seen from the side: flat orange."""
    return g(x, y, s, '<rect x="-20" y="-9" width="40" height="18" rx="3" fill="#E8A36B" stroke="#9B5A22" stroke-width="1.5"/>'
                      '<line x1="-20" y1="-2" x2="20" y2="-2" stroke="#9B5A22" stroke-width="1"/>')


def target(x, y, s=1.0) -> str:
    """The target: a flat green pad."""
    return g(x, y, s, '<path d="M-22,6 L-14,-6 L22,-6 L14,6 Z" fill="#9FE1CB" stroke="#1D9E75" stroke-width="1.5" stroke-linejoin="round"/>')


def floor(x, y, w=110, h=44) -> str:
    """A flat floor tile for scenes (soft blue, with a few plain lines)."""
    return (f'<path d="M{x - w / 2 + 14:g},{y - h / 2:g} L{x + w / 2:g},{y - h / 2:g} L{x + w / 2 - 14:g},{y + h / 2:g} '
            f'L{x - w / 2:g},{y + h / 2:g} Z" fill="#D5E6F8" stroke="#8DB5E0" stroke-width="1.5" stroke-linejoin="round"/>')


def scoreboard(x, y, s=1.0, label="+10") -> str:
    return g(x, y, s, '<rect x="-36" y="-26" width="72" height="52" rx="8" fill="#FFFFFF" stroke="#BA7517" stroke-width="1.5"/>'
                      f'<text x="0" y="10" text-anchor="middle" {FONT} font-size="28" font-weight="700" fill="{GREEN}">{label}</text>')


def dial(x, y, s=1.0) -> str:
    return g(x, y, s, '<circle r="26" fill="#FFFFFF" stroke="#534AB7" stroke-width="2"/>'
                      '<path d="M-17,10 A20,20 0 1 1 17,10" fill="none" stroke="#B9B4F0" stroke-width="5" stroke-linecap="round"/>'
                      '<path d="M0,2 L12,-12" stroke="#D85A30" stroke-width="3" stroke-linecap="round"/>'
                      '<circle r="4" fill="#534AB7"/>')


def wrench(x, y, s=1.0, angle=-40, cut="#E3EEFC") -> str:
    """A flat wrench; cut is the color of whatever it sits on (the jaw is an opening)."""
    return g(x, y, s, f'<g transform="rotate({angle})"><rect x="-5" y="-4" width="10" height="36" rx="5" fill="#B5D4F4" stroke="#185FA5" stroke-width="1.8"/>'
                      '<circle cx="0" cy="-12" r="12" fill="#B5D4F4" stroke="#185FA5" stroke-width="1.8"/>'
                      f'<rect x="-5" y="-30" width="10" height="16" fill="{cut}"/>'
                      '<path d="M-5,-24 L-5,-14 M5,-24 L5,-14" stroke="#185FA5" stroke-width="1.8" stroke-linecap="round"/></g>')


def snowflake(x, y, s=1.0, color=GREEN) -> str:
    return g(x, y, s, "".join(f'<line x1="0" y1="-9" x2="0" y2="9" stroke="{color}" stroke-width="2.2" stroke-linecap="round" '
                              f'transform="rotate({a})"/>' for a in (0, 60, 120)))


def forward_arrow(x, y, s=1.0) -> str:
    return g(x, y, s, f'<path d="M0,22 L0,-14" stroke="{ORANGE}" stroke-width="5" stroke-linecap="round"/>'
                      f'<path d="M-11,-8 L0,-22 L11,-8 Z" fill="{ORANGE}" stroke="{ORANGE}" stroke-width="2" stroke-linejoin="round"/>')


def turn_arrow(x, y, s=1.0) -> str:
    return g(x, y, s, f'<path d="M-20,16 C-24,-12 8,-22 22,-6" fill="none" stroke="{PURPLE_D}" stroke-width="5" stroke-linecap="round"/>'
                      f'<path d="M14,-18 L28,-4 L10,0 Z" fill="{PURPLE_D}" stroke="{PURPLE_D}" stroke-width="2" stroke-linejoin="round"/>')


def chirp_waves(x, y, s=1.0, color=PINK, flip=False) -> str:
    """Three sound arcs, opening to the right (or left when flip)."""
    sx = -1 if flip else 1
    return g(x, y, s, f'<g transform="scale({sx},1)">' + "".join(
        f'<path d="M{6 + 11 * i},{-6 - 6 * i} Q{14 + 11 * i},0 {6 + 11 * i},{6 + 6 * i}" fill="none" stroke="{color}" '
        f'stroke-width="{3.2 - 0.5 * i:g}" stroke-linecap="round"/>' for i in range(3)) + "</g>")


def eye_cone(x, y, s=1.0, color="#CFE3F7", stroke="#8DB5E0") -> str:
    """A camera's field of view: a soft flat wedge opening to the right."""
    return g(x, y, s, f'<path d="M0,0 L60,-30 Q72,0 60,30 Z" fill="{color}" stroke="{stroke}" stroke-width="1.5" stroke-linejoin="round"/>')


def scroll(x, y, s=1.0) -> str:
    return g(x, y, s, '<rect x="-24" y="-30" width="48" height="60" rx="6" fill="#FFFFFF" stroke="#BA7517" stroke-width="1.5"/>'
                      + "".join(f'<line x1="-14" y1="{-18 + 11 * i}" x2="{10 - 6 * (i % 2)}" y2="{-18 + 11 * i}" stroke="#BA7517" stroke-width="2.5" stroke-linecap="round"/>'
                                for i in range(4)))


def folder(x, y, s=1.0) -> str:
    return g(x, y, s, '<path d="M-34,-18 L-34,22 Q-34,26 -30,26 L30,26 Q34,26 34,22 L34,-12 Q34,-16 30,-16 L4,-16 L-2,-24 L-30,-24 Q-34,-24 -34,-20 Z" '
                      'fill="#FAC775" stroke="#854F0B" stroke-width="1.5" stroke-linejoin="round"/>')


def exam(x, y, s=1.0) -> str:
    return g(x, y, s, '<rect x="-24" y="-30" width="48" height="60" rx="6" fill="#FFFFFF" stroke="#BA7517" stroke-width="1.5"/>'
                      + "".join(f'<path d="M-16,{-17 + 14 * i} l4,4 l8,-9" fill="none" stroke="{GREEN}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>'
                                f'<line x1="-2" y1="{-14 + 14 * i}" x2="16" y2="{-14 + 14 * i}" stroke="#BA7517" stroke-width="2.5" stroke-linecap="round"/>'
                                for i in range(3)))


def bars(x, y, s=1.0) -> str:
    return g(x, y, s, '<rect x="-30" y="-26" width="60" height="52" rx="8" fill="#FFFFFF" stroke="#BA7517" stroke-width="1.5"/>'
                      + "".join(f'<rect x="{-20 + 14 * i}" y="{18 - h}" width="10" height="{h}" rx="2" fill="{c}"/>'
                                for i, (h, c) in enumerate(((16, BLUE_F), (28, PURPLE), (38, GREEN))) if True))


def gear(x, y, s=1.0, color=PURPLE_D) -> str:
    teeth = "".join(f'<rect x="-4" y="-17" width="8" height="8" rx="1.5" fill="{color}" transform="rotate({a})"/>' for a in range(0, 360, 45))
    return g(x, y, s, f'{teeth}<circle r="12" fill="{color}"/><circle r="5" fill="#FFFFFF"/>')


def weight(x, y, s=1.0) -> str:
    return g(x, y, s, '<path d="M-15,18 L-9,-12 L9,-12 L15,18 Z" fill="#B5D4F4" stroke="#185FA5" stroke-width="1.8" stroke-linejoin="round"/>'
                      '<circle cx="0" cy="-17" r="5" fill="none" stroke="#185FA5" stroke-width="2.4"/>'
                      f'<text x="0" y="12" text-anchor="middle" {FONT} font-size="12" font-weight="700" fill="#185FA5">kg</text>')
