"""Immutable trajectory parameters transcribed from M5 F0–F9; no numerical helpers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Cycle:
    peak_deg: int
    rise_us: int
    hold_us: int
    return_us: int
    rest_us: int


@dataclass(frozen=True)
class Motion:
    cycles: tuple[Cycle, ...]
    end_us: int
    axis: str = "Y"
    sign: int = -1
    thorax: str = "fixed"
    analysis_start_us: int = 5_000_000
    analysis_end_us: int | None = None
    side: str = "left"


BASE = Cycle(90, 1_500_000, 1_000_000, 2_000_000, 1_000_000)
MOTIONS = {
    "QUIET": Motion((), 35_000_000),
    "F90": Motion((BASE,) * 3, 21_500_000),
    "AL90": Motion((BASE,) * 3, 21_500_000, axis="X", sign=1),
    "AR90": Motion((BASE,) * 3, 21_500_000, axis="X", side="right"),
    "VAR": Motion(
        (
            Cycle(70, 1_000_000, 500_000, 2_000_000, 1_000_000),
            Cycle(80, 1_500_000, 1_000_000, 1_000_000, 1_000_000),
            Cycle(90, 2_000_000, 1_500_000, 1_500_000, 1_000_000),
        ),
        21_000_000,
    ),
    "NOHOLD": Motion((Cycle(90, 1_500_000, 0, 2_000_000, 1_000_000),) * 3, 18_500_000),
    "WRONG": Motion((BASE,) * 3, 21_500_000, axis="X"),
    "PARTIAL": Motion((BASE,) * 3, 21_500_000, analysis_start_us=5_800_000, analysis_end_us=20_000_000),
    "T-EXT": Motion((BASE,) * 3, 21_500_000, thorax="extension"),
    "T-MIX": Motion((BASE,) * 3, 21_500_000, thorax="mixed"),
    "F90L": Motion((BASE,) * 55, 305_000_000),
    "F90-30": Motion((BASE,) * 6, 35_000_000),  # I-HD's frozen 30s cropped/repeated control
    "F90-NEXT": Motion((Cycle(100, 1_500_000, 1_000_000, 2_000_000, 1_000_000),) * 3, 21_500_000),
}
