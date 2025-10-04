import re
from typing import Dict, List


DEFAULT_PROFILE = "default"


def _intent(intent: str, entities: List[Dict[str, str]]):
    return {"intent": intent, "entities": entities}


def text_to_intents(text: str, profile: str = DEFAULT_PROFILE) -> List[Dict]:
    t = (text or "").strip().lower()
    out: List[Dict] = []
    if not t:
        return out

    # Profile-specific overrides
    if profile == "premiere":
        # In Adobe Premiere Pro, "cut" at playhead is typically CTRL+K
        if t in ("cut", "split", "add edit"):
            out.append(_intent("Chord", [{"type": "chord", "value": "CTRL+K"}]))
            return out

    # Keys
    if t in ("space", "spacebar"):
        out.append(_intent("Key", [{"type": "key", "value": "space"}]))
        return out
    if t == "enter":
        out.append(_intent("Key", [{"type": "key", "value": "enter"}]))
        return out
    if t in ("escape", "esc"):
        out.append(_intent("Key", [{"type": "key", "value": "escape"}]))
        return out

    # Edit commands
    if t == "cut":
        out.append(_intent("Chord", [{"type": "chord", "value": "CTRL+X"}]))
        return out
    if t == "copy":
        out.append(_intent("Chord", [{"type": "chord", "value": "CTRL+C"}]))
        return out
    if t == "paste":
        out.append(_intent("Chord", [{"type": "chord", "value": "CTRL+V"}]))
        return out
    if t == "undo":
        out.append(_intent("Chord", [{"type": "chord", "value": "CTRL+Z"}]))
        return out
    if t == "redo":
        out.append(_intent("Chord", [{"type": "chord", "value": "CTRL+Y"}]))
        return out

    # Flight sim style
    if re.fullmatch(r"gear up", t):
        out.append(_intent("Key", [{"type": "key", "value": "g"}]))
        return out
    if re.fullmatch(r"gear down", t):
        out.append(_intent("Key", [{"type": "key", "value": "g"}]))
        return out
    if re.fullmatch(r"flaps (up|down)", t):
        step = t.split(" ")[1]
        out.append(_intent("FlapsSet", [{"type": "step", "value": step}]))
        return out

    # Mouse/fire
    if t in ("fire", "shoot", "click"):
        out.append(_intent("FirePrimary", []))
        return out
    if t in ("mouse hold", "hold mouse"):
        out.append(_intent("MouseHold", [{"type": "duration_ms", "value": "300"}]))
        return out
    if t in ("mouse release", "release mouse"):
        out.append(_intent("MouseRelease", []))
        return out

    # Throttle adjust e.g., "throttle up 20" or "throttle down 10"
    m = re.fullmatch(r"throttle (up|down)(?: (\d+))?", t)
    if m:
        direction = m.group(1)
        amount = int(m.group(2) or 10)
        delta = amount if direction == "up" else -amount
        out.append(_intent("ThrottleAdjust", [{"type": "delta", "value": str(delta)}]))
        return out

    # Default: no intent recognized
    return out
