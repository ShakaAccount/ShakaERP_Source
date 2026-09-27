"""WCAG 2.x contrast for every MASTER.md colour pair, light and dark.

    .venv/bin/python design-system/shaka-erp/tools/contrast.py

Translucent colours are composited over the background they sit on before
measuring. Prints a markdown table and exits 1 if any pair misses its floor
(text 4.5, icon/focus/UI 3.0; "deco" pairs are reported, not gated).
"""
import re
import sys

PALETTE = {
    "light": {
        "action": "#0071E3", "on-action": "#FFFFFF", "link": "#0066CC",
        "bg": "#F5F5F7", "surface": "#FFFFFF",
        "label": "#1D1D1F", "secondary": "#6A6A6F",
        "separator": "#D2D2D7", "fill": "rgba(118,118,128,.12)",
        "focus": "#0066CC",
        "success": "#1F7F37", "warning": "#C93400", "danger": "#D70015", "danger-fill": "#D70015",
        "gold": "#B5925F", "gold-deep": "#8A6A3B",
        "thin": "rgba(255,255,255,.6)", "regular": "rgba(255,255,255,.88)", "thick": "rgba(255,255,255,.94)",
        "success-tint": "rgba(31,127,55,.08)", "warning-tint": "rgba(201,52,0,.08)", "danger-tint": "rgba(215,0,21,.08)",
    },
    "dark": {
        "action": "#0071E3", "on-action": "#FFFFFF", "link": "#2997FF",
        "bg": "#1C1C1E", "surface": "#2C2C2E",
        "label": "#F5F5F7", "secondary": "#AEAEB2",
        "separator": "#38383A", "fill": "rgba(118,118,128,.24)",
        "focus": "#2997FF",
        "success": "#30D158", "warning": "#FF9F0A", "danger": "#FF7B73", "danger-fill": "#D70015",
        "gold": "#B5925F", "gold-deep": "#C9A774",
        "thin": "rgba(44,44,46,.6)", "regular": "rgba(44,44,46,.72)", "thick": "rgba(44,44,46,.85)",
        "success-tint": "rgba(48,209,88,.12)", "warning-tint": "rgba(255,159,10,.12)", "danger-tint": "rgba(255,123,115,.12)",
    },
}

# (foreground, background, kind). kind: text 4.5 | ui 3.0 | deco (no floor).
PAIRS = [
    ("label", "bg", "text"), ("label", "surface", "text"), ("label", "fill@surface", "text"),
    ("secondary", "bg", "text"), ("secondary", "surface", "text"), ("secondary", "fill@surface", "text"),
    ("link", "bg", "text"), ("link", "surface", "text"),
    ("on-action", "action", "text"),
    ("focus", "bg", "ui"), ("focus", "surface", "ui"),
    ("success", "surface", "text"), ("warning", "surface", "text"), ("danger", "surface", "text"),
    ("success", "bg", "text"), ("warning", "bg", "text"), ("danger", "bg", "text"),
    ("success", "success-tint@surface", "text"), ("warning", "warning-tint@surface", "text"),
    ("danger", "danger-tint@surface", "text"),
    ("on-action", "danger-fill", "text"),
    ("gold-deep", "surface", "ui"), ("gold-deep", "bg", "ui"),
    ("gold", "surface", "deco"), ("gold", "#000000", "deco"),
    # materials over what realistically scrolls beneath them: the page, and a
    # selected (action-filled) row; blur only lowers contrast further toward the mean
    ("label", "thin@bg", "text"), ("secondary", "thin@bg", "text"),
    ("label", "regular@action", "text"), ("secondary", "regular@action", "text"),
    ("label", "thick@action", "text"), ("secondary", "thick@action", "text"),
    ("separator", "surface", "deco"),
]
FLOOR = {"text": 4.5, "ui": 3.0, "deco": 0}


def rgba(s):
    if s.startswith("#"):
        return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5)) + (1.0,)
    r, g, b, a = re.findall(r"[\d.]+", s)
    return int(r), int(g), int(b), float(a)


def over(fg, bg):
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def resolve(pal, name):
    if name.startswith("#"):
        return rgba(name)
    if "@" in name:  # translucent fill composited over a base
        top, base = name.split("@")
        return over(rgba(pal[top]), resolve(pal, base))
    return rgba(pal[name])


def main():
    fails = 0
    print("| Pair | Kind | Light | Dark |\n|---|---|---|---|")
    for fg, bg, kind in PAIRS:
        cells = []
        for scheme in ("light", "dark"):
            pal = PALETTE[scheme]
            b = resolve(pal, bg)
            r = ratio(over(resolve(pal, fg), b), b)
            ok = r >= FLOOR[kind]
            fails += not ok
            cells.append(f"{r:.2f}{'' if ok else ' ✗'}")
        print(f"| {fg} on {bg} | {kind} | {cells[0]} | {cells[1]} |")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
