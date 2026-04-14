"""
METAR decoder — converts raw METAR strings into structured, human-readable data.

METAR format (approximate):
  [TYPE] ICAO DDHHMMz WIND VIS [WX] CLOUDS TEMP/DEW ALTIMETER [RMK ...]
"""

import re


# ── compass helpers ────────────────────────────────────────────────────────────

_COMPASS = [
    "N", "NNE", "NE", "ENE",
    "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW",
    "W", "WNW", "NW", "NNW",
]

def _degrees_to_compass(deg: int) -> str:
    return _COMPASS[round(deg / 22.5) % 16]

def _knots_to_mph(kts: float) -> int:
    return round(kts * 1.15078)

def _celsius_to_fahrenheit(c: int) -> int:
    return round(c * 9 / 5 + 32)


# ── weather-code tables ────────────────────────────────────────────────────────

_WX_DESCRIPTORS = {
    "MI": "shallow", "PR": "partial", "BC": "patches of",
    "DR": "low drifting", "BL": "blowing", "SH": "showers",
    "TS": "thunderstorm", "FZ": "freezing",
}

_WX_PHENOMENA = {
    "DZ": "drizzle", "RA": "rain", "SN": "snow", "SG": "snow grains",
    "IC": "ice crystals", "PL": "ice pellets", "GR": "hail",
    "GS": "small hail", "UP": "unknown precipitation",
    "BR": "mist", "FG": "fog", "FU": "smoke", "VA": "volcanic ash",
    "DU": "dust", "SA": "sand", "HZ": "haze", "PY": "spray",
    "PO": "dust/sand whirls", "SQ": "squalls",
    "FC": "funnel cloud / tornado", "SS": "sandstorm", "DS": "dust storm",
}

_CLOUD_COVER = {
    "SKC": "clear skies", "CLR": "clear skies",
    "NSC": "no significant clouds", "NCD": "no cloud detected",
    "FEW": "a few clouds",   # 1–2 oktas
    "SCT": "scattered clouds",  # 3–4 oktas
    "BKN": "broken clouds",     # 5–7 oktas
    "OVC": "overcast",          # 8 oktas
    "VV":  "sky obscured",
}


def _parse_wx_token(token: str) -> str:
    """Decode a single present-weather token like -RA, +TSRA, FZFG, VCSH …"""
    original = token
    intensity = ""
    if token.startswith("VC"):
        intensity = "in the vicinity"
        token = token[2:]
    elif token.startswith("-"):
        intensity = "light"
        token = token[1:]
    elif token.startswith("+"):
        intensity = "heavy"
        token = token[1:]

    descriptor = ""
    for code, label in _WX_DESCRIPTORS.items():
        if token.startswith(code):
            descriptor = label
            token = token[len(code):]
            break

    # If TS was stripped as a descriptor and nothing follows, that IS the phenomenon
    if descriptor == "thunderstorm" and not token:
        parts = [p for p in [intensity, "thunderstorm"] if p]
        return " ".join(parts) if parts else original

    # When TS is the descriptor and more phenomena follow, say "thunderstorm with …"
    if descriptor == "thunderstorm" and token:
        phenomena = _decode_phenomena(token)
        if phenomena:
            suffix = " and ".join(phenomena)
            parts = [p for p in [intensity, f"thunderstorm with {suffix}"] if p]
            return " ".join(parts) if parts else original

    phenomena = _decode_phenomena(token)
    parts = [p for p in [intensity, descriptor] + phenomena if p]
    return " ".join(parts) if parts else original


def _decode_phenomena(token: str) -> list:
    """Break a phenomena string into a list of readable labels."""
    result = []
    while token:
        matched = False
        for code, label in _WX_PHENOMENA.items():
            if token.startswith(code):
                result.append(label)
                token = token[len(code):]
                matched = True
                break
        if not matched:
            result.append(token)
            break
    return result


# ── main parser ────────────────────────────────────────────────────────────────

def parse_metar(raw: str) -> dict:
    """
    Parse a raw METAR string and return a dict with human-readable fields.

    Keys: station, time, wind, visibility, weather (list), clouds (list),
          temperature, dewpoint, altimeter, summary, raw.
    """
    result = {
        "station": "",
        "time": "",
        "wind": "",
        "visibility": "",
        "weather": [],
        "clouds": [],
        "temperature": "",
        "dewpoint": "",
        "altimeter": "",
        "summary": "",
        "raw": raw.strip(),
    }

    tokens = raw.strip().split()
    i = 0

    # Optional report type
    if tokens[i] in ("METAR", "SPECI"):
        i += 1

    # Station identifier
    if i < len(tokens):
        result["station"] = tokens[i]
        i += 1

    # Date/time  DDHHMMz
    if i < len(tokens) and re.fullmatch(r"\d{6}Z", tokens[i]):
        t = tokens[i]
        day, hour, minute = int(t[0:2]), int(t[2:4]), int(t[4:6])
        result["time"] = f"Day {day}, {hour:02d}:{minute:02d} UTC"
        i += 1

    # Optional modifier
    if i < len(tokens) and tokens[i] in ("AUTO", "COR"):
        i += 1

    # ── token-by-token parsing ─────────────────────────────────────────────────
    while i < len(tokens):
        token = tokens[i]

        # Stop at remarks
        if token == "RMK":
            break

        # Stop at trend groups
        if token in ("BECMG", "TEMPO", "NOSIG"):
            break

        # ── Wind ──────────────────────────────────────────────────────────────
        wind_m = re.fullmatch(
            r"(VRB|\d{3})(\d{2,3})(G(\d{2,3}))?(KT|MPS|KMH)", token
        )
        if wind_m:
            dir_raw  = wind_m.group(1)
            spd_raw  = int(wind_m.group(2))
            gust_raw = int(wind_m.group(4)) if wind_m.group(4) else None
            unit     = wind_m.group(5)

            def to_mph(v):
                if unit == "KT":  return _knots_to_mph(v)
                if unit == "MPS": return round(v * 2.237)
                return round(v * 0.621)  # KMH

            spd  = to_mph(spd_raw)
            gust = to_mph(gust_raw) if gust_raw else None

            if spd_raw == 0:
                result["wind"] = "Calm"
            else:
                if dir_raw == "VRB":
                    dir_str = "from a variable direction"
                else:
                    deg = int(dir_raw)
                    dir_str = f"from the {_degrees_to_compass(deg)} ({deg}°)"

                result["wind"] = f"{spd} mph {dir_str}"
                if gust:
                    result["wind"] += f", gusting to {gust} mph"

            # Optional variable-direction suffix  dddVddd
            if i + 1 < len(tokens) and re.fullmatch(r"\d{3}V\d{3}", tokens[i + 1]):
                v = tokens[i + 1]
                c1, c2 = _degrees_to_compass(int(v[0:3])), _degrees_to_compass(int(v[4:7]))
                result["wind"] += f", varying between {c1} and {c2}"
                i += 1
            i += 1
            continue

        # ── Visibility (statute miles) ─────────────────────────────────────────
        # Fractional: 1/4SM  3/4SM  M1/4SM
        frac_m = re.fullmatch(r"M?(\d+)/(\d+)SM", token)
        if frac_m:
            val = int(frac_m.group(1)) / int(frac_m.group(2))
            result["visibility"] = f"{frac_m.group(1)}/{frac_m.group(2)} mile — very poor"
            i += 1
            continue

        # Whole-number + optional fractional next token: "1 1/4SM"
        whole_m = re.fullmatch(r"(\d+)", token)
        if whole_m and i + 1 < len(tokens) and re.fullmatch(r"\d+/\d+SM", tokens[i + 1]):
            whole = int(whole_m.group(1))
            nxt = tokens[i + 1]
            nxt_m = re.fullmatch(r"(\d+)/(\d+)SM", nxt)
            val = whole + int(nxt_m.group(1)) / int(nxt_m.group(2))
            result["visibility"] = _vis_label(val)
            i += 2
            continue

        # Plain SM  e.g. 10SM  7SM
        sm_m = re.fullmatch(r"M?(\d+)SM", token)
        if sm_m:
            val = int(sm_m.group(1))
            result["visibility"] = _vis_label(val)
            i += 1
            continue

        # Metric visibility  9999 / 0800 etc.
        met_m = re.fullmatch(r"(\d{4})", token)
        if met_m and not result["visibility"]:
            metres = int(met_m.group(1))
            if metres == 9999:
                result["visibility"] = "10+ km (excellent)"
            else:
                miles = metres / 1609.34
                result["visibility"] = f"{metres} m ({miles:.1f} miles)"
            i += 1
            continue

        # CAVOK
        if token == "CAVOK":
            result["visibility"] = "10+ km (excellent)"
            result["clouds"].append("clear skies")
            i += 1
            continue

        # ── Cloud layers ───────────────────────────────────────────────────────
        cloud_m = re.fullmatch(r"(SKC|CLR|NSC|NCD|FEW|SCT|BKN|OVC|VV)(\d{3})?(CB|TCU)?", token)
        if cloud_m:
            cover      = cloud_m.group(1)
            height_str = cloud_m.group(2)
            ctype      = cloud_m.group(3)
            label      = _CLOUD_COVER.get(cover, cover)

            if cover in ("SKC", "CLR", "NSC", "NCD"):
                result["clouds"].append(label)
            else:
                ht = int(height_str) * 100 if height_str else None
                s = label
                if ht is not None:
                    s += f" at {ht:,} ft"
                if ctype == "CB":
                    s += " (cumulonimbus — thunderstorm potential)"
                elif ctype == "TCU":
                    s += " (towering cumulus)"
                result["clouds"].append(s)
            i += 1
            continue

        # ── Temperature / Dew point  TT/DD ────────────────────────────────────
        temp_m = re.fullmatch(r"(M?)(\d{2})/(M?)(\d{2})", token)
        if temp_m:
            tc = int(temp_m.group(2)) * (-1 if temp_m.group(1) == "M" else 1)
            dc = int(temp_m.group(4)) * (-1 if temp_m.group(3) == "M" else 1)
            result["temperature"] = f"{_celsius_to_fahrenheit(tc)}°F ({tc}°C)"
            result["dewpoint"]    = f"{_celsius_to_fahrenheit(dc)}°F ({dc}°C)"
            i += 1
            continue

        # ── Altimeter (inches Hg) ──────────────────────────────────────────────
        alt_m = re.fullmatch(r"A(\d{4})", token)
        if alt_m:
            result["altimeter"] = f"{int(alt_m.group(1)) / 100:.2f} inHg"
            i += 1
            continue

        # QNH (hPa)
        qnh_m = re.fullmatch(r"Q(\d{4})", token)
        if qnh_m:
            result["altimeter"] = f"{int(qnh_m.group(1))} hPa"
            i += 1
            continue

        # ── Present weather ────────────────────────────────────────────────────
        # Must come after cloud/temp/alt checks to avoid false positives.
        # Two sub-patterns: TS alone/with phenomena, or other descriptor + phenomena.
        wx_m = re.fullmatch(
            r"[-+]?(VC)?"
            r"(?:(TS)(DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|SQ|FC|SS|DS|PO)*"
            r"|(MI|PR|BC|DR|BL|SH|FZ)?(DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|SQ|FC|SS|DS|PO)+)",
            token,
        )
        if wx_m:
            result["weather"].append(_parse_wx_token(token))
            i += 1
            continue

        i += 1  # skip unrecognised token

    result["summary"] = _build_summary(result)
    return result


def _vis_label(miles: float) -> str:
    if miles >= 10:
        return f"{int(miles)}+ miles (excellent)"
    if miles >= 5:
        return f"{miles:.0f} miles (good)"
    if miles >= 3:
        return f"{miles:.0f} miles (moderate)"
    if miles >= 1:
        return f"{miles:.1f} miles (poor)"
    return f"{miles:.2f} miles (very poor)"


def _build_summary(r: dict) -> str:
    parts = []

    # Sky condition
    sky_map = {
        "clear": "Clear skies",
        "few": "Mostly clear with a few clouds",
        "scattered": "Partly cloudy",
        "broken": "Mostly cloudy",
        "overcast": "Overcast",
        "obscured": "Sky obscured",
        "no significant": "Clear skies",
    }
    if r["clouds"]:
        first = r["clouds"][0].lower()
        label = next((v for k, v in sky_map.items() if k in first), r["clouds"][0].capitalize())
        parts.append(label)

    # Weather phenomena
    if r["weather"]:
        parts.append(", ".join(r["weather"]))

    # Temperature
    if r["temperature"]:
        parts.append(r["temperature"])

    # Wind
    if r["wind"]:
        if r["wind"] == "Calm":
            parts.append("calm winds")
        else:
            parts.append(f"winds {r['wind']}")

    # Visibility
    if r["visibility"]:
        parts.append(f"visibility {r['visibility']}")

    return ". ".join(parts) + "." if parts else "Weather data could not be fully decoded."
