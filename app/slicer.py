"""
Wrapper around PrusaSlicer CLI for headless slicing.
"""

import asyncio
import os
import tempfile
import zipfile
from pathlib import Path

from .gcode_parser import PlateEstimate, SliceEstimate, parse_gcode

SLICE_TIMEOUT = int(os.environ.get("SLICE_TIMEOUT_SECONDS", "120"))
PRUSA_SLICER_BIN = os.environ.get("PRUSA_SLICER_BIN", "prusa-slicer")
DEFAULT_PROFILE = Path(__file__).parent.parent / "config" / "default_profile.ini"


class SlicingError(Exception):
    pass


async def slice_3mf(file_bytes: bytes, file_name: str) -> SliceEstimate:
    """
    Slice a .3mf file using PrusaSlicer CLI and return estimates.

    The .3mf from MakerWorld contains an embedded print profile from the creator.
    PrusaSlicer will use that profile if present, otherwise fall back to default.
    """
    with tempfile.TemporaryDirectory(prefix="makercycle_slicer_") as tmpdir:
        input_path = Path(tmpdir) / file_name
        input_path.write_bytes(file_bytes)

        # First, try to slice using the embedded profile in the .3mf
        output_path = Path(tmpdir) / "output.gcode"
        result = await _run_prusaslicer(input_path, output_path, use_default_profile=False)

        # If that fails, try with default profile
        if result is None:
            result = await _run_prusaslicer(input_path, output_path, use_default_profile=True)

        if result is None:
            raise SlicingError("PrusaSlicer failed to slice the model")

        # Parse the generated gcode(s)
        plates = _collect_plates(tmpdir, output_path)

        if not plates:
            raise SlicingError("No plate data could be extracted from sliced output")

        model_name = _extract_model_name(file_name)
        total_weight = sum(
            f.weight_g for p in plates for f in p.filaments
        )
        total_time = sum(p.print_time_hours for p in plates)

        return SliceEstimate(
            model_name=model_name,
            plates=plates,
            total_weight_g=round(total_weight, 2),
            total_time_hours=round(total_time, 4),
        )


async def _run_prusaslicer(
    input_path: Path,
    output_path: Path,
    use_default_profile: bool,
) -> str | None:
    """Run PrusaSlicer CLI and return stdout, or None on failure."""
    cmd = [
        PRUSA_SLICER_BIN,
        "--export-gcode",
        str(input_path),
        "--output", str(output_path),
    ]

    if use_default_profile and DEFAULT_PROFILE.exists():
        cmd.extend(["--load", str(DEFAULT_PROFILE)])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=SLICE_TIMEOUT
        )

        if proc.returncode == 0:
            return stdout.decode("utf-8", errors="replace")

        # Log stderr for debugging
        err_msg = stderr.decode("utf-8", errors="replace")
        print(f"PrusaSlicer stderr: {err_msg[:500]}")
        return None

    except asyncio.TimeoutError:
        proc.kill()
        raise SlicingError(f"Slicing timed out after {SLICE_TIMEOUT} seconds")
    except FileNotFoundError:
        raise SlicingError("PrusaSlicer binary not found. Check PRUSA_SLICER_BIN env var.")


def _collect_plates(tmpdir: str, primary_output: Path) -> list[PlateEstimate]:
    """
    Collect plate data from generated gcode files.

    PrusaSlicer may output:
    - A single output.gcode for single-plate models
    - Multiple output_plate_N.gcode for multi-plate models
    - Or the gcode might be embedded in a .3mf output
    """
    plates: list[PlateEstimate] = []
    tmpdir_path = Path(tmpdir)

    # Look for plate-specific gcode files first
    plate_files = sorted(tmpdir_path.glob("*plate*.gcode"))
    if not plate_files:
        plate_files = sorted(tmpdir_path.glob("*.gcode"))

    for gcode_file in plate_files:
        content = gcode_file.read_text(encoding="utf-8", errors="replace")
        if len(content) < 100:
            continue
        plate = parse_gcode(content, gcode_file.name)
        if plate.filaments or plate.print_time_hours > 0:
            plates.append(plate)

    # Also check for .gcode.3mf output (some PrusaSlicer versions output this)
    for threemf_file in tmpdir_path.glob("*.3mf"):
        try:
            with zipfile.ZipFile(threemf_file, "r") as zf:
                for name in sorted(zf.namelist()):
                    if name.endswith(".gcode") and "plate" in name.lower():
                        content = zf.read(name).decode("utf-8", errors="replace")
                        plate = parse_gcode(content, name)
                        if plate.filaments or plate.print_time_hours > 0:
                            plates.append(plate)
        except (zipfile.BadZipFile, KeyError):
            continue

    return plates


def _extract_model_name(file_name: str) -> str:
    """Extract a clean model name from the file name."""
    name = Path(file_name).stem
    # Remove common suffixes
    for suffix in [".gcode", ".3mf", "_plate", "_fixed"]:
        name = name.replace(suffix, "")
    return name.strip("_- ")
