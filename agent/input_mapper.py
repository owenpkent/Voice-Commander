import logging
from typing import Dict, Any, List
import time

try:
    import keyboard  # type: ignore
    import mouse  # type: ignore
except Exception as e:
    raise RuntimeError(
        "Failed to import input libraries. Ensure 'keyboard' and 'mouse' are installed."
    ) from e


logger = logging.getLogger(__name__)


def _press_key(key: str):
    keyboard.press_and_release(key)


def _press_combo(combo: List[str]):
    seq = "+".join(combo)
    keyboard.press_and_release(seq)


def _mouse_click(button: str = "left"):
    button = (button or "left").lower()
    if button not in ("left", "right", "middle"):
        button = "left"
    mouse.click(button)


def apply_intent(msg: Dict[str, Any]):
    """
    Handle both legacy schema and new schema.

    Legacy schema examples:
      {"intent":"key.press", "payload": {"key":"space"}}
      {"intent":"key.combo", "payload": {"combo":["ctrl","x"]}}
      {"intent":"mouse.click", "payload": {"button":"left"}}

    New schema examples:
      {"intent":"Key", "entities":[{"type":"key","value":"space"}]}
      {"intent":"Chord", "entities":[{"type":"chord","value":"CTRL+K"}]}
      {"intent":"FirePrimary", "entities":[]}
      {"intent":"FlapsSet", "entities":[{"type":"step","value":"down"}]}
      {"intent":"ThrottleAdjust", "entities":[{"type":"delta","value":"+10"}]}
      {"intent":"MouseHold", "entities":[{"type":"duration_ms","value":"300"}]}
      {"intent":"MouseRelease", "entities":[]}
    """

    intent = msg.get("intent")

    # Legacy handling
    if isinstance(msg.get("payload"), dict) and intent:
        payload = msg.get("payload", {})
        if intent == "key.press":
            key = payload.get("key")
            if not key:
                logger.warning("key.press missing 'key' in payload")
                return
            logger.info(f"Press key: {key}")
            _press_key(str(key))
            return
        if intent == "key.combo":
            combo = payload.get("combo")
            if not isinstance(combo, list) or not combo:
                logger.warning("key.combo missing 'combo' list in payload")
                return
            logger.info(f"Press combo: {'+'.join(combo)}")
            _press_combo([str(k) for k in combo])
            return
        if intent == "mouse.click":
            button = payload.get("button", "left")
            logger.info(f"Mouse click: {button}")
            _mouse_click(str(button))
            return

    # New schema handling
    ents = msg.get("entities") or []
    itype = str(intent or "").strip()

    def get_entity(et: str) -> Any:
        for e in ents:
            if (e.get("type") or "").lower() == et.lower():
                return e.get("value")
        return None

    if itype == "Key":
        key = get_entity("key")
        if key:
            logger.info(f"Key: {key}")
            _press_key(str(key).lower())
            return

    if itype == "Chord":
        chord = get_entity("chord")
        if chord:
            # Normalize e.g., "CTRL+K" -> "ctrl+k"
            seq = "+".join([t.strip().lower() for t in str(chord).split("+") if t.strip()])
            logger.info(f"Chord: {seq}")
            _press_combo(seq.split("+"))
            return

    if itype == "FirePrimary":
        logger.info("Mouse click: left (FirePrimary)")
        _mouse_click("left")
        return

    if itype == "MouseHold":
        dur_ms = get_entity("duration_ms")
        try:
            dur = float(dur_ms) / 1000.0 if dur_ms is not None else 0.3
        except Exception:
            dur = 0.3
        logger.info(f"Mouse hold left for {dur:.3f}s")
        mouse.press("left")
        time.sleep(dur)
        mouse.release("left")
        return

    if itype == "MouseRelease":
        logger.info("Mouse release left")
        try:
            mouse.release("left")
        except Exception:
            pass
        return

    if itype == "FlapsSet":
        step = str(get_entity("step") or "").lower()
        key = "f6" if step == "up" else "f7"
        logger.info(f"FlapsSet: {step} -> {key}")
        _press_key(key)
        return

    if itype == "ThrottleAdjust":
        delta = get_entity("delta")
        logger.info(f"ThrottleAdjust: {delta} (no-op stub)")
        # Stub: integrate with sim connect or send repeated keypresses if desired
        return

    logger.debug(f"Unhandled intent: {intent} / message: {msg}")
