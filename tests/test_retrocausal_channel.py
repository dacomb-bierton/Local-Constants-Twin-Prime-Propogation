"""The fixed-point channel has to move with the future bit and round-trip text."""

import os

import numpy as np
import pytest

from retrocausal_channel import (
    PHRASES,
    RECOMMENDED_MODULATION,
    RECOMMENDED_NOISE,
    PCTCChannel,
    apply_gentle_variation,
    bin_to_hex,
    bin_to_text,
    channel_warning,
    communication_quality,
    consistency_landscape,
    is_consistent_reception,
    run_transmission,
    solve_fixed_point,
    text_to_binary,
)

# The packet hardcoded in v0.31. It is "Hello this" and nothing else.
HELLO_BITS = (
    "0100100001100101011011000110110001101111"
    "0010000001110100011010000110100101110011"
)


def test_hello_bits_match_the_old_packet():
    assert text_to_binary("Hello this") == HELLO_BITS
    assert bin_to_text(HELLO_BITS) == "Hello this"


def test_text_roundtrip_includes_short_and_unicode():
    for text in ("A", "Hi", "Hello this", "P-CTC link", "café", "line\nbreak"):
        assert bin_to_text(text_to_binary(text)) == text


def test_bin_to_text_rejects_garbage_and_keeps_damaged_ascii():
    assert bin_to_text("") is None
    assert bin_to_text("010") is None
    assert bin_to_text("0100000x") is None
    # A lone non-ASCII byte is not readable text. Mixed damage keeps a dot.
    assert bin_to_text("11001000") is None
    assert bin_to_text("0100100011001000") == "H·"
    assert bin_to_hex("01001000") == "48"
    assert bin_to_hex("") == "—"
    assert bin_to_hex("102") == "—"


def test_fixed_point_matches_closed_form_and_is_not_one_half():
    # p = ((1-ε) κ target + ε/2) / (ε + κ (1-ε))
    # ε=0.1, κ=0.7, target=1 → 0.68/0.73
    solved = solve_fixed_point(0, 0.1, 0.7)
    assert solved["past_p0"] == pytest.approx(0.68 / 0.73)
    assert solved["past_p0"] > 0.9
    assert solved["residual"] < 1e-12
    assert solved["idle_gap"] == pytest.approx(0.5 * 0.7 * 0.9)
    other = solve_fixed_point(1, 0.1, 0.7)
    assert other["past_p0"] == pytest.approx(1.0 - solved["past_p0"])
    assert other["fidelity"] == pytest.approx(solved["fidelity"])


def test_zero_modulation_and_zero_noise_are_the_extremes():
    idle = solve_fixed_point(0, 0.2, 0.0)
    assert idle["past_p0"] == pytest.approx(0.5)
    assert idle["influence"] == pytest.approx(0.0)
    perfect = solve_fixed_point(1, 0.0, 0.4)
    assert perfect["past_p0"] == pytest.approx(0.0)
    assert perfect["fidelity"] == pytest.approx(1.0)
    assert solve_fixed_point(0, 0.0, 0.0)["past_p0"] == pytest.approx(0.5)


def test_fidelity_falls_as_noise_rises():
    quiet = solve_fixed_point(0, 0.02, 0.8)["fidelity"]
    loud = solve_fixed_point(0, 0.4, 0.8)["fidelity"]
    assert quiet > loud
    assert loud > 0.5


def test_landscape_minimum_is_the_fixed_point():
    xs, y0, y1, p0, p1 = consistency_landscape(0.1, 0.7)
    assert abs(float(xs[int(np.argmin(y0))]) - p0) < 0.02
    assert float(np.min(y0)) < 1e-4
    assert abs(float(xs[int(np.argmin(y1))]) - p1) < 0.02


def test_recommended_point_is_the_value_the_terminal_quotes():
    solved = solve_fixed_point(0, RECOMMENDED_NOISE, RECOMMENDED_MODULATION)
    assert solved["past_p0"] == pytest.approx(0.776 / 0.816)
    assert f"{solved['past_p0']:.3f}" == "0.951"
    quality = communication_quality(solved["fidelity"], solved["postselect_prob"], solved["influence"])
    assert quality == pytest.approx(91.462745098, rel=1e-9)
    assert is_consistent_reception(solved["fidelity"], solved["postselect_prob"], 1.0, "Hello this")
    assert channel_warning(solved["fidelity"], 1.0, "Hello this") == ""
    assert "bit errors" in channel_warning(solved["fidelity"], 0.9, "Hello this")


class _ScriptedRng:
    def __init__(self, values):
        self._values = iter(values)

    def random(self, count):
        return np.array([next(self._values) for _ in range(count)], dtype=float)


def test_majority_vote_uses_the_fixed_point_distribution():
    # Recommended p(past=0 | future=0) is about 0.951.
    # Three draws above that threshold are read as 1, so the vote is wrong.
    channel = PCTCChannel(noise=RECOMMENDED_NOISE, rng=_ScriptedRng([0.99, 0.99, 0.99]))
    bit = channel.transmit_bit(0, RECOMMENDED_MODULATION, reps=3)
    assert bit["decoded"] == 1
    # A 1–1 tie falls back to the side of 1/2 the fixed point is on.
    channel.rng = _ScriptedRng([0.1, 0.99])
    tie = channel.transmit_bit(0, RECOMMENDED_MODULATION, reps=2)
    assert tie["decoded"] == 0
    # Zero noise forces p=1, so even a draw of 0.999 is a 0.
    perfect = PCTCChannel(noise=0.0, rng=_ScriptedRng([0.999, 0.999, 0.999]))
    assert perfect.transmit_bit(0, 1.0, reps=3)["decoded"] == 0


def test_noise_free_message_round_trip():
    channel = PCTCChannel(noise=0.0, rng=_ScriptedRng([0.2] * 80))
    result = run_transmission(channel, text_to_binary("Hello this"), modulation=0.5, reps=1, noise=0.0)
    assert result["correct"]
    assert result["english"] == "Hello this"
    assert result["accuracy"] == 1.0
    assert result["p0_given_0"] == pytest.approx(1.0)
    assert result["p0_given_1"] == pytest.approx(0.0)
    assert result["mi"] > 0.5


def test_variations_are_deterministic_and_visible():
    bits = text_to_binary("Hello this")
    assert apply_gentle_variation(bits, 0, 3) == bits
    flipped = apply_gentle_variation(bits, 1, 0)
    assert sum(a != b for a, b in zip(bits, flipped)) == 1
    assert bin_to_text(apply_gentle_variation(bits, 2, 0)) == "Idmmn!uihr"
    rotated = apply_gentle_variation("010011", 3, 0)
    assert rotated == "100011"
    doubled = apply_gentle_variation(bits, 4, 1)
    assert sum(a != b for a, b in zip(bits, doubled)) == 2
    assert apply_gentle_variation(bits, 2, 5) == apply_gentle_variation(bits, 2, 5)


def test_phrases_survive_a_noise_free_channel():
    channel = PCTCChannel(noise=0.0, rng=np.random.default_rng(0))
    for phrase in PHRASES:
        result = run_transmission(channel, text_to_binary(phrase), modulation=0.8, reps=1, noise=0.0)
        assert result["english"] == phrase


def test_empty_packet_is_rejected():
    with pytest.raises(ValueError):
        run_transmission(PCTCChannel(), "", modulation=0.5)


@pytest.mark.skipif(os.environ.get("DISPLAY") is None, reason="needs a display")
def test_gui_self_test():
    pytest.importorskip("tkinter")
    pytest.importorskip("matplotlib")
    from retrocausal_gui import self_test

    assert self_test() == 0
