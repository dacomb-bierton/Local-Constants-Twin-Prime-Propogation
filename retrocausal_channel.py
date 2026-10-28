"""Fixed-point channel used by the P-CTC consistency terminal.

The future bit is a boundary condition on a noisy loop, not a scripted reply.
The past bit is the unique fixed point of that loop. Finite readouts of the
fixed point are combined by majority vote.

The loop map on ``p = P(past bit = 0)`` is affine:

    f(p) = (1 - ε) * ((1 - κ) * p + κ * target) + ε / 2

``ε`` is noise, ``κ`` is modulation, and ``target`` is 1 when the future bit
is 0 and 0 when the future bit is 1. An earlier version of this map mixed
``p`` symmetrically and its only fixed point was 1/2 for every future bit, so
the decoder could not carry a message. This map's fixed point moves with the
future bit. Because ``f`` is affine, that point has a closed form.
"""

from __future__ import annotations

import math
import threading

import numpy as np

PHRASES = (
    "Hello this",
    "P-CTC link",
    "Fixed point",
    "Amber wave",
)

VARIATION_NAMES = {
    0: "identity",
    1: "single flip",
    2: "lsb flip",
    3: "rotate-3",
    4: "double flip",
}

RETRO_MIN_FIDELITY = 0.75
RETRO_MIN_POST = 0.60
RETRO_MIN_ACCURACY = 0.90

# Launch / recommended operating point. Soft fidelity is about 0.951 and a
# 7-read majority vote reconstructs short ASCII almost every time.
RECOMMENDED_NOISE = 0.08
RECOMMENDED_MODULATION = 0.80
RECOMMENDED_REPS = 7
RECOMMENDED_INTERVAL = 0.6


def text_to_binary(text: str) -> str:
    """UTF-8 bytes, MSB first. ASCII matches the historical 8-bit packing."""
    return "".join(f"{byte:08b}" for byte in text.encode("utf-8"))


def _printable_char(ch: str) -> bool:
    return ch in "\n\t" or ord(ch) >= 32


def bin_to_text(binstr: str) -> str | None:
    """Decode complete bytes.

    Valid UTF-8 made of printable characters is returned as text, so a clean
    round trip keeps accents and other multibyte characters. A damaged packet
    falls back to one glyph per byte: printable ASCII, or a middle dot.
    """
    if not isinstance(binstr, str) or len(binstr) < 8 or any(c not in "01" for c in binstr):
        return None
    usable = len(binstr) - (len(binstr) % 8)
    try:
        data = int(binstr[:usable], 2).to_bytes(usable // 8, "big")
    except (OverflowError, ValueError):
        return None
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError:
        decoded = None
    if decoded is not None and decoded and all(_printable_char(ch) for ch in decoded):
        return decoded
    glyphs = []
    readable = 0
    for byte in data:
        if 32 <= byte <= 126 or byte in (9, 10, 13):
            glyphs.append(chr(byte))
            readable += 1
        else:
            glyphs.append("·")
    if readable == 0:
        return None
    return "".join(glyphs)


def bin_to_hex(binstr: str) -> str:
    if not isinstance(binstr, str) or not binstr or any(c not in "01" for c in binstr):
        return "—"
    usable = len(binstr) - (len(binstr) % 4)
    if usable <= 0:
        return "—"
    return f"{int(binstr[:usable], 2):X}".zfill(usable // 4)


def apply_gentle_variation(base_bits: str, var_id: int, tick: int = 0) -> str:
    """Deterministic, reversible-looking edits used by continuous transmit.

    Identity leaves the packet alone. The other four modes each change the
    bits in a way the event log can name.
    """
    bits = list(base_bits)
    n = len(bits)
    var_id = int(var_id)
    if n == 0 or var_id == 0:
        return "".join(bits)
    if var_id == 1:
        pos = (int(tick) * 3) % n
        bits[pos] = "1" if bits[pos] == "0" else "0"
    elif var_id == 2:
        for index in range(7, n, 8):
            bits[index] = "1" if bits[index] == "0" else "0"
    elif var_id == 3 and n > 5:
        start = (int(tick) * 2) % (n - 3)
        bits[start : start + 3] = bits[start + 1 : start + 3] + [bits[start]]
    elif var_id == 4:
        first = (int(tick) * 4) % n
        second = (first + 5) % n
        for pos in (first, second):
            bits[pos] = "1" if bits[pos] == "0" else "0"
    return "".join(bits)


def _clip_unit(value: float) -> float:
    return float(min(1.0, max(0.0, float(value))))


def solve_fixed_point(future_bit: int, noise: float, modulation: float) -> dict:
    """Exact fixed point of the noisy loop for one future bit."""
    eps = _clip_unit(noise)
    kappa = _clip_unit(modulation)
    bit = 0 if int(future_bit) == 0 else 1
    target = 1.0 - bit

    def loop(prob: float) -> float:
        mixed = (1.0 - kappa) * prob + kappa * target
        return (1.0 - eps) * mixed + eps * 0.5

    denom = eps + kappa * (1.0 - eps)
    if denom < 1e-15:
        past_p0 = 0.5
    else:
        past_p0 = ((1.0 - eps) * kappa * target + 0.5 * eps) / denom
    past_p0 = float(min(1.0, max(0.0, past_p0)))
    p_correct = past_p0 if bit == 0 else 1.0 - past_p0
    post = (1.0 - eps) * p_correct + eps * (1.0 - p_correct)
    return {
        "future_bit": bit,
        "past_p0": past_p0,
        "fidelity": float(p_correct),
        "postselect_prob": float(post),
        "residual": float(abs(loop(past_p0) - past_p0)),
        "idle_gap": float(abs(loop(0.5) - 0.5)),
        "influence": float(abs(2.0 * past_p0 - 1.0)),
        "noise": eps,
        "modulation": kappa,
        "target": target,
    }


def consistency_landscape(noise: float, modulation: float, points: int = 97):
    """Squared consistency defect ``(p - f(p))^2`` for both future bits."""
    eps = _clip_unit(noise)
    kappa = _clip_unit(modulation)
    xs = np.linspace(0.0, 1.0, int(points))
    curves = []
    fixed = []
    for bit in (0, 1):
        solved = solve_fixed_point(bit, eps, kappa)
        target = solved["target"]
        mapped = (1.0 - eps) * ((1.0 - kappa) * xs + kappa * target) + eps * 0.5
        curves.append((xs - mapped) ** 2)
        fixed.append(solved["past_p0"])
    return xs, curves[0], curves[1], fixed[0], fixed[1]


def binary_mutual_info(source, decoded) -> float:
    """Plugin estimate of I(source; readout), in bits."""
    src = [1 if int(bit) else 0 for bit in source]
    dst = [1 if int(bit) else 0 for bit in decoded]
    n = len(src)
    if n == 0 or n != len(dst):
        return 0.0
    info = 0.0
    for a in (0, 1):
        px = src.count(a) / n
        if px <= 0.0:
            continue
        for b in (0, 1):
            py = dst.count(b) / n
            if py <= 0.0:
                continue
            pxy = sum(1 for s, d in zip(src, dst) if s == a and d == b) / n
            if pxy <= 0.0:
                continue
            info += pxy * math.log2(pxy / (px * py))
    return float(info)


def communication_quality(fidelity: float, postselect: float, influence: float) -> float:
    score = (
        float(fidelity) * 40.0
        + float(postselect) * 30.0
        + min(1.0, max(0.0, float(influence))) * 30.0
    )
    return float(max(0.0, min(100.0, score)))


def channel_warning(fidelity: float, accuracy: float, english: str | None) -> str:
    if not english:
        return "Readout is not printable text. Lower noise or raise redundancy."
    if accuracy < 1.0:
        return "Majority vote still has bit errors. Raise redundancy or lower noise."
    if fidelity < 0.80:
        return "Fixed point is shallow. Raise modulation or lower noise."
    return ""


def is_consistent_reception(fidelity: float, postselect: float, accuracy: float, english: str | None) -> bool:
    return bool(
        english
        and fidelity >= RETRO_MIN_FIDELITY
        and postselect >= RETRO_MIN_POST
        and accuracy >= RETRO_MIN_ACCURACY
    )


class PCTCChannel:
    """Solves the loop once per bit, then draws ``reps`` noisy readouts."""

    def __init__(self, noise: float = RECOMMENDED_NOISE, rng=None):
        self.noise = float(noise)
        self.rng = np.random.default_rng() if rng is None else rng
        self._lock = threading.Lock()

    def transmit_bit(self, future_bit: int, modulation: float, reps: int = 1, noise: float | None = None) -> dict:
        reps = max(1, int(reps))
        with self._lock:
            eps = self.noise if noise is None else float(noise)
            soft = solve_fixed_point(future_bit, eps, modulation)
            draws = np.asarray(self.rng.random(reps), dtype=float)
        zeros = int(np.count_nonzero(draws < soft["past_p0"]))
        ones = reps - zeros
        if zeros > ones:
            decoded = 0
        elif ones > zeros:
            decoded = 1
        else:
            decoded = 0 if soft["past_p0"] >= 0.5 else 1
        out = dict(soft)
        out["decoded"] = decoded
        out["readouts"] = reps
        return out


def parse_bits(bits) -> list[int]:
    if isinstance(bits, str):
        if any(ch not in "01" for ch in bits):
            raise ValueError("bit string must contain only 0 and 1")
        return [1 if ch == "1" else 0 for ch in bits]
    parsed = [1 if int(bit) else 0 for bit in bits]
    return parsed


def run_transmission(channel: PCTCChannel, bits, modulation: float, reps: int = 1, noise: float | None = None) -> dict:
    """Send every bit through the same noise and modulation snapshot."""
    source = parse_bits(bits)
    if not source:
        raise ValueError("no bits to send")
    if noise is None:
        noise = float(channel.noise)
    reps = max(1, int(reps))
    results = [channel.transmit_bit(bit, modulation, reps=reps, noise=noise) for bit in source]
    decoded = [int(item["decoded"]) for item in results]
    decoded_str = "".join(str(bit) for bit in decoded)
    source_str = "".join(str(bit) for bit in source)
    when_0 = [item["past_p0"] for item, bit in zip(results, source) if bit == 0]
    when_1 = [item["past_p0"] for item, bit in zip(results, source) if bit == 1]
    return {
        "source_bits": source_str,
        "decoded_bits": decoded_str,
        "english": bin_to_text(decoded_str),
        "accuracy": float(sum(a == b for a, b in zip(source, decoded)) / len(source)),
        "fidelity": float(np.mean([item["fidelity"] for item in results])),
        "postselect": float(np.mean([item["postselect_prob"] for item in results])),
        "residual": float(np.max([item["residual"] for item in results])),
        "idle_gap": float(np.mean([item["idle_gap"] for item in results])),
        "influence": float(np.mean([item["influence"] for item in results])),
        "mi": float(binary_mutual_info(source, decoded)),
        "p0_given_0": None if not when_0 else float(np.mean(when_0)),
        "p0_given_1": None if not when_1 else float(np.mean(when_1)),
        "correct": decoded_str == source_str,
        "noise": float(results[-1]["noise"]),
        "modulation": float(results[-1]["modulation"]),
        "bits": len(source),
        "reps": reps,
    }
