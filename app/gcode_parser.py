"""
Parses PrusaSlicer-generated gcode to extract print estimates.
Mirrors the logic from the Flutter app's gcode_metadata_parser.dart.
"""

import re
from dataclasses import dataclass, field


@dataclass
class FilamentEstimate:
    filament_id: int
    profile_name: str
    filament_type: str
    weight_g: float
    color: str | None = None


@dataclass
class PlateEstimate:
    plate_id: int
    print_time_hours: float
    filaments: list[FilamentEstimate] = field(default_factory=list)
    layer_height: float | None = None
    nozzle_diameter: float | None = None


@dataclass
class SliceEstimate:
    model_name: str
    plates: list[PlateEstimate] = field(default_factory=list)
    total_weight_g: float = 0.0
    total_time_hours: float = 0.0


def parse_gcode(gcode_content: str, file_name: str = "model") -> PlateEstimate:
    """Parse a single gcode file and extract print estimates."""
    plate_id = _extract_plate_id(file_name)
    filaments = _extract_filaments(gcode_content)
    print_time = _extract_print_time(gcode_content)
    layer_height = _extract_float(gcode_content, r";\s*layer_height\s*=\s*([\d.]+)")
    nozzle_diameter = _extract_float(gcode_content, r";\s*nozzle_diameter\s*=\s*([\d.]+)")

    return PlateEstimate(
        plate_id=plate_id,
        print_time_hours=print_time,
        filaments=filaments,
        layer_height=layer_height,
        nozzle_diameter=nozzle_diameter,
    )


def _extract_plate_id(file_name: str) -> int:
    match = re.search(r"plate_(\d+)", file_name)
    return int(match.group(1)) if match else 1


def _extract_filaments(content: str) -> list[FilamentEstimate]:
    """Extract filament info from gcode comments."""
    filaments: list[FilamentEstimate] = []

    # Get filament weights: "filament used [g] = 12.34" or list "12.34;56.78"
    weights: list[float] = []
    weight_match = re.search(
        r";\s*(?:total\s+)?filament\s+(?:used|weight)\s*\[g\]\s*=\s*(.+)", content
    )
    if weight_match:
        raw = weight_match.group(1).strip()
        for val in raw.split(";"):
            val = val.strip()
            if val:
                try:
                    weights.append(float(val))
                except ValueError:
                    pass

    # Filament types
    types: list[str] = []
    type_match = re.search(r";\s*filament_type\s*=\s*(.+)", content)
    if type_match:
        types = [t.strip() for t in type_match.group(1).strip().split(";") if t.strip()]

    # Filament profile names
    profiles: list[str] = []
    profile_match = re.search(r";\s*filament_settings_id\s*=\s*(.+)", content)
    if profile_match:
        profiles = [
            p.strip() for p in profile_match.group(1).strip().split(";") if p.strip()
        ]

    # Filament colors
    colors: list[str] = []
    color_match = re.search(r";\s*filament_colour\s*=\s*(.+)", content)
    if color_match:
        colors = [
            c.strip() for c in color_match.group(1).strip().split(";") if c.strip()
        ]

    # Build filament list from the longest list
    count = max(len(weights), len(types), len(profiles), 1)
    for i in range(count):
        weight = weights[i] if i < len(weights) else 0.0
        if weight <= 0:
            continue
        filaments.append(
            FilamentEstimate(
                filament_id=i + 1,
                profile_name=profiles[i] if i < len(profiles) else f"Filament {i + 1}",
                filament_type=types[i] if i < len(types) else "PLA",
                weight_g=weight,
                color=colors[i] if i < len(colors) else None,
            )
        )

    return filaments


def _extract_print_time(content: str) -> float:
    """Extract print time in hours from gcode comments."""
    # Format: "estimated printing time (normal mode) = 1d 2h 30m 15s"
    # or "model printing time = 1d 2h 30m 15s"
    dhms_match = re.search(
        r";\s*(?:estimated printing time.*?|model printing time)\s*=\s*(.+)", content
    )
    if dhms_match:
        time_str = dhms_match.group(1).strip()
        hours = 0.0
        d = re.search(r"(\d+)\s*d", time_str)
        h = re.search(r"(\d+)\s*h", time_str)
        m = re.search(r"(\d+)\s*m", time_str)
        s = re.search(r"(\d+)\s*s", time_str)
        if d:
            hours += int(d.group(1)) * 24
        if h:
            hours += int(h.group(1))
        if m:
            hours += int(m.group(1)) / 60
        if s:
            hours += int(s.group(1)) / 3600
        if hours > 0:
            return round(hours, 4)

    # Format: "print_time = 3600" (seconds)
    seconds_match = re.search(r";\s*print_time\s*=\s*(\d+)", content)
    if seconds_match:
        return round(int(seconds_match.group(1)) / 3600, 4)

    # Format: "time cost = 01:30:00"
    hms_match = re.search(r";\s*time\s+cost\s*=\s*(\d+):(\d+):(\d+)", content)
    if hms_match:
        h, m, s = int(hms_match.group(1)), int(hms_match.group(2)), int(hms_match.group(3))
        return round(h + m / 60 + s / 3600, 4)

    return 0.0


def _extract_float(content: str, pattern: str) -> float | None:
    match = re.search(pattern, content)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None
