"""
Training Zones Calculator

Computes personalised heart-rate training zones from CPET data
(HR max, VT1, VT2) or falls back to % HR max estimates.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrainingZones:
    hr_max: int
    vt1: int
    vt2: int
    # Zone boundaries (bpm)
    z1_ceiling: int   # Recovery  — below this
    z2_floor: int     # Base / Aerobic  — VT1 region
    z2_ceiling: int
    z3_floor: int     # Tempo / Threshold approach
    z3_ceiling: int
    z4_floor: int     # Threshold / VT2 region
    z4_ceiling: int
    z5_floor: int     # Max effort — above this
    source: str = "CPET"
    z1_floor: int = 0  # AYUN Zone 1 starts at 50% HF max (0 = not set)


def compute_zones(
    hr_max: int | float | None,
    vt1: int | float | None = None,
    vt2: int | float | None = None,
) -> TrainingZones | None:
    """
    Compute training zones.

    If VT1 and VT2 are provided (from CPET), zone boundaries are anchored to
    the measured thresholds. Otherwise we fall back to standard % HR max.

    Returns None if hr_max is missing or zero.
    """
    if not hr_max:
        return None

    hr_max = int(round(hr_max))

    if vt1 and vt2 and vt1 < vt2 <= hr_max:
        vt1 = int(round(vt1))
        vt2 = int(round(vt2))
        # Buffer zones around VT1/VT2
        z1_ceil  = max(vt1 - 15, int(hr_max * 0.55))
        z2_fl    = z1_ceil + 1
        z2_ceil  = vt1
        z3_fl    = vt1 + 1
        z3_ceil  = max(vt1 + 5, vt2 - 10)
        z4_fl    = z3_ceil + 1
        z4_ceil  = vt2
        z5_fl    = vt2 + 1
        source = "CPET (VT1/VT2)"
    else:
        # Fall back to the AYUN 5-zone model (% HF max):
        # Zone 1 Erholung 50–60%, 2 Leicht 60–70%, 3 Moderat 70–80%,
        # 4 Hart 80–90%, 5 Maximal 90–100%.
        z1_ceil  = int(hr_max * 0.60)
        z2_fl    = z1_ceil + 1
        z2_ceil  = int(hr_max * 0.70)
        z3_fl    = z2_ceil + 1
        z3_ceil  = int(hr_max * 0.80)
        z4_fl    = z3_ceil + 1
        z4_ceil  = int(hr_max * 0.90)
        z5_fl    = z4_ceil + 1
        vt1, vt2 = z2_ceil, z4_ceil  # estimates only; CPET thresholds are better
        source = "AYUN 5-zone model (% HF max)"

    return TrainingZones(
        hr_max=hr_max,
        vt1=vt1,
        vt2=vt2,
        z1_ceiling=z1_ceil,
        z2_floor=z2_fl,
        z2_ceiling=z2_ceil,
        z3_floor=z3_fl,
        z3_ceiling=z3_ceil,
        z4_floor=z4_fl,
        z4_ceiling=z4_ceil,
        z5_floor=z5_fl,
        source=source,
        z1_floor=int(hr_max * 0.50) if source.startswith("AYUN") else 0,
    )


def _z1(zones: TrainingZones) -> str:
    return f"{zones.z1_floor}–{zones.z1_ceiling}" if zones.z1_floor else f"< {zones.z1_ceiling}"


def format_zones(zones: TrainingZones) -> str:
    return (
        f"Training Zones ({zones.source}, HR max = {zones.hr_max} bpm):\n"
        f"  Zone 1 — Recovery:          {_z1(zones)} bpm\n"
        f"  Zone 2 — Aerobic Base:      {zones.z2_floor}–{zones.z2_ceiling} bpm  ← VT1 = {zones.vt1} bpm\n"
        f"  Zone 3 — Tempo:             {zones.z3_floor}–{zones.z3_ceiling} bpm\n"
        f"  Zone 4 — Threshold:         {zones.z4_floor}–{zones.z4_ceiling} bpm  ← VT2 = {zones.vt2} bpm\n"
        f"  Zone 5 — Max Effort:        > {zones.z5_floor} bpm\n"
    )


def zones_as_dict(zones: TrainingZones) -> dict:
    return {
        "source": zones.source,
        "hr_max": zones.hr_max,
        "vt1_bpm": zones.vt1,
        "vt2_bpm": zones.vt2,
        "zones": {
            "Zone 1 (Recovery)":     f"{_z1(zones)} bpm",
            "Zone 2 (Aerobic Base)": f"{zones.z2_floor}–{zones.z2_ceiling} bpm",
            "Zone 3 (Tempo)":        f"{zones.z3_floor}–{zones.z3_ceiling} bpm",
            "Zone 4 (Threshold)":    f"{zones.z4_floor}–{zones.z4_ceiling} bpm",
            "Zone 5 (Max Effort)":   f"> {zones.z5_floor} bpm",
        },
    }
