"""Spring motion tokens as CSS linear() easings, from Apple's damping + response.

    .venv/bin/python design-system/shaka-erp/tools/springs.py

A spring has no duration; the token's duration is the settle time (the
moment the value stays within SETTLE of the target). Damping 1.0 is
critically damped: no overshoot, and its normalised curve is the same at every
response, so the tokens are one easing plus a duration per response. Prints the
markdown table and CSS MASTER.md carries.
"""
import math

SETTLE = 0.002   # 0.2% of the travel: under half a pixel on a 200px move
POINTS = 20      # samples in the linear() curve (plus 0 and 1)

# name: (damping ratio, response in s, use)
SPRINGS = {
    "press":  (1.0, 0.15, "press feedback, toggles, checks"),
    "snappy": (1.0, 0.25, "menus, popovers, tooltips, autocomplete"),
    "":       (1.0, 0.35, "dialogs, tabs pill, accordion, palette"),
    "gentle": (1.0, 0.50, "large surfaces: card resize, sheet height"),
}


def position(t, zeta, response):
    """Normalised spring step response, 0 -> 1."""
    w = 2 * math.pi / response
    if zeta >= 1:  # critically damped (treat >1 as 1: Apple never over-damps UI)
        return 1 - (1 + w * t) * math.exp(-w * t)
    wd = w * math.sqrt(1 - zeta ** 2)
    return 1 - math.exp(-zeta * w * t) * (math.cos(wd * t) + zeta * w / wd * math.sin(wd * t))


def settle_time(zeta, response):
    t, dt, last_out = 0.0, 0.0005, 0.0
    while t < 5:
        if abs(1 - position(t, zeta, response)) > SETTLE:
            last_out = t
        t += dt
    return last_out + dt


def token(zeta, response):
    dur = settle_time(zeta, response)
    pts = [position(dur * i / POINTS, zeta, response) for i in range(1, POINTS)]
    body = ", ".join(f"{p:.3f}".rstrip("0").rstrip(".") for p in pts)
    return round(dur * 1000), f"linear(0, {body}, 1)"


def main():
    print("| Token | Damping | Response | Duration | Use |\n|---|---|---|---|---|")
    rows = []
    for name, (z, r, use) in SPRINGS.items():
        ms, ease = token(z, r)
        tok = f"--shaka-spring{'-' + name if name else ''}"
        print(f"| `{tok}` | {z} | {r}s | {ms}ms | {use} |")
        rows.append((name, ms, ease))
    print()
    curves = {}
    for name, ms, ease in rows:
        curves.setdefault(SPRINGS[name][0], ease)  # same damping = same curve
        print(f"--shaka-spring{'-' + name if name else ''}-dur: {ms}ms;")
    for zeta, ease in curves.items():
        suffix = "" if zeta >= 1 else f"-{round(zeta * 100)}"
        print(f"--shaka-spring{suffix}: {ease};")


if __name__ == "__main__":
    main()
