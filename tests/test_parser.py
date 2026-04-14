"""
Unit tests for metar_parser.py.

Every test passes a raw METAR string directly into parse_metar() and asserts
on specific fields of the returned dict.  No network calls, no Flask — pure
input/output verification.
"""

import pytest
from metar_parser import parse_metar


# ── Helpers ────────────────────────────────────────────────────────────────────

def parsed(raw):
    """Shorthand: strip and parse a raw METAR string."""
    return parse_metar(raw.strip())


# ── Station & time ─────────────────────────────────────────────────────────────

class TestStationAndTime:
    def test_station_extracted(self):
        r = parsed("METAR KHIO 141853Z 19014KT 10SM CLR 09/04 A3006")
        assert r["station"] == "KHIO"

    def test_station_without_metar_prefix(self):
        r = parsed("KJFK 141851Z 18016KT 10SM CLR 22/13 A2993")
        assert r["station"] == "KJFK"

    def test_speci_prefix_handled(self):
        r = parsed("SPECI KSFO 141856Z 26011KT 10SM CLR 14/07 A3022")
        assert r["station"] == "KSFO"

    def test_time_parsed(self):
        r = parsed("METAR KHIO 141853Z 19014KT 10SM CLR 09/04 A3006")
        assert "14" in r["time"]   # day
        assert "18:53" in r["time"]


# ── Wind ───────────────────────────────────────────────────────────────────────

class TestWind:
    def test_basic_wind_direction_and_speed(self):
        r = parsed("METAR KHIO 141853Z 18016KT 10SM CLR 09/04 A3006")
        assert "S" in r["wind"]          # 180° → South
        assert "18 mph" in r["wind"]     # 16 kts → 18 mph

    def test_gusting_wind(self):
        r = parsed("METAR KHIO 141853Z 19014G20KT 10SM CLR 09/04 A3006")
        assert "gusting" in r["wind"]
        assert "23 mph" in r["wind"]     # 20 kts gust → 23 mph

    def test_calm_wind(self):
        r = parsed("METAR KORD 141852Z 00000KT 10SM SKC 15/08 A3010")
        assert r["wind"] == "Calm"

    def test_variable_direction(self):
        r = parsed("METAR KORD 141852Z VRB03KT 10SM CLR 08/07 A2990")
        assert "variable" in r["wind"].lower()

    def test_variable_direction_range(self):
        # Wind varying between two headings: e.g. 350V080
        r = parsed("METAR KJFK 141851Z 01010KT 350V080 10SM CLR 20/10 A2993")
        assert "N" in r["wind"]
        assert "E" in r["wind"]          # variation covers NE sector

    def test_wind_in_mps(self):
        r = parsed("METAR EGLL 141850Z 27010MPS 10SM CLR 12/05 Q1015")
        assert "mph" in r["wind"]        # converted from m/s


# ── Visibility ─────────────────────────────────────────────────────────────────

class TestVisibility:
    def test_10sm(self):
        r = parsed("METAR KHIO 141853Z 19014KT 10SM CLR 09/04 A3006")
        assert "10+" in r["visibility"]
        assert "excellent" in r["visibility"]

    def test_5sm(self):
        r = parsed("METAR KORD 141852Z 27012KT 5SM CLR 20/10 A2985")
        assert "5" in r["visibility"]
        assert "good" in r["visibility"]

    def test_fractional_quarter_mile(self):
        r = parsed("METAR KORD 141852Z VRB03KT 1/4SM FG OVC005 08/07 A2990")
        assert "1/4" in r["visibility"]
        assert "poor" in r["visibility"]

    def test_metric_9999(self):
        r = parsed("METAR EGLL 141850Z 27010KT 9999 BKN020 12/05 Q1015")
        assert "10+" in r["visibility"]

    def test_metric_low_visibility(self):
        r = parsed("METAR EGLL 141850Z 27010KT 0600 FG OVC002 08/07 Q0995")
        assert "600" in r["visibility"]

    def test_cavok(self):
        r = parsed("METAR EGLL 141850Z 27005KT CAVOK 15/08 Q1020")
        assert "10+" in r["visibility"]
        assert any("clear" in c.lower() for c in r["clouds"])


# ── Cloud layers ───────────────────────────────────────────────────────────────

class TestClouds:
    def test_sky_clear(self):
        r = parsed("METAR KORD 141852Z 00000KT 10SM SKC 15/08 A3010")
        assert any("clear" in c.lower() for c in r["clouds"])

    def test_clr(self):
        r = parsed("METAR KORD 141852Z 27012KT 10SM CLR 20/10 A2985")
        assert any("clear" in c.lower() for c in r["clouds"])

    def test_few_clouds_with_altitude(self):
        r = parsed("METAR KJFK 141851Z 18016KT 10SM FEW060 22/13 A2993")
        assert any("few" in c.lower() and "6,000" in c for c in r["clouds"])

    def test_scattered_clouds(self):
        r = parsed("METAR KJFK 141851Z 18016KT 10SM SCT040 22/13 A2993")
        assert any("scattered" in c.lower() and "4,000" in c for c in r["clouds"])

    def test_broken_clouds(self):
        r = parsed("METAR KHIO 141853Z 19014KT 10SM BKN026 09/04 A3006")
        assert any("broken" in c.lower() and "2,600" in c for c in r["clouds"])

    def test_overcast(self):
        r = parsed("METAR KSFO 141856Z 26011KT 10SM OVC029 14/07 A3022")
        assert any("overcast" in c.lower() and "2,900" in c for c in r["clouds"])

    def test_multiple_cloud_layers(self):
        r = parsed("METAR KHIO 141853Z 19014KT 10SM FEW060 BKN250 22/13 A2993")
        assert len(r["clouds"]) == 2

    def test_cumulonimbus_flagged(self):
        r = parsed("METAR KORD 141852Z 27015KT 5SM SCT030CB BKN060 20/15 A2985")
        assert any("cumulonimbus" in c.lower() for c in r["clouds"])

    def test_vertical_visibility(self):
        r = parsed("METAR KORD 141852Z 04005KT 1/8SM FZFG VV002 M02/M03 A3005")
        assert any("obscured" in c.lower() for c in r["clouds"])


# ── Present weather ────────────────────────────────────────────────────────────

class TestPresentWeather:
    def test_light_rain(self):
        r = parsed("METAR KJFK 141851Z 18016KT 5SM -RA BKN060 20/15 A2985")
        assert any("light" in w and "rain" in w for w in r["weather"])

    def test_heavy_rain(self):
        r = parsed("METAR KJFK 141851Z 18016KT 3SM +RA BKN030 18/16 A2970")
        assert any("heavy" in w and "rain" in w for w in r["weather"])

    def test_thunderstorm_with_rain(self):
        r = parsed("METAR KORD 141852Z VRB03KT 1/4SM +TSRA FG OVC005 08/07 A2990")
        assert any("thunderstorm" in w and "rain" in w for w in r["weather"])

    def test_standalone_thunderstorm(self):
        r = parsed("METAR KORD 141852Z 27012KT 5SM -RA TS SCT030 BKN060 20/15 A2985")
        assert any("thunderstorm" in w for w in r["weather"])

    def test_snow(self):
        r = parsed("METAR KORD 141852Z 35010KT 2SM -SN OVC015 M02/M05 A3020")
        assert any("snow" in w for w in r["weather"])

    def test_freezing_fog(self):
        r = parsed("METAR KORD 141852Z 04005KT 1/8SM FZFG VV002 M02/M03 A3005")
        assert any("freezing" in w and "fog" in w for w in r["weather"])

    def test_freezing_rain(self):
        r = parsed("METAR KORD 141852Z 05008KT 1SM FZRA OVC010 M01/M03 A3010")
        assert any("freezing" in w and "rain" in w for w in r["weather"])

    def test_fog(self):
        r = parsed("METAR KORD 141852Z VRB03KT 1/4SM FG OVC005 08/07 A2990")
        assert any("fog" in w for w in r["weather"])

    def test_mist(self):
        r = parsed("METAR KJFK 141851Z 18008KT 5SM BR FEW010 22/20 A2990")
        assert any("mist" in w for w in r["weather"])

    def test_vicinity_shower(self):
        r = parsed("METAR KLAX 141850Z 27010KT 10SM VCSH FEW025 SCT060 18/10 A3005")
        assert any("vicinity" in w for w in r["weather"])

    def test_no_weather_when_clear(self):
        r = parsed("METAR KHIO 141853Z 19014KT 10SM CLR 09/04 A3006")
        assert r["weather"] == []


# ── Temperature & dew point ────────────────────────────────────────────────────

class TestTemperature:
    def test_positive_temperature(self):
        r = parsed("METAR KJFK 141851Z 18016KT 10SM CLR 22/13 A2993")
        assert "72°F" in r["temperature"]   # 22 C → 72 F
        assert "22°C" in r["temperature"]

    def test_positive_dewpoint(self):
        r = parsed("METAR KJFK 141851Z 18016KT 10SM CLR 22/13 A2993")
        assert "55°F" in r["dewpoint"]      # 13 C → 55 F
        assert "13°C" in r["dewpoint"]

    def test_negative_temperature(self):
        r = parsed("METAR KORD 141852Z 04005KT 1/8SM FZFG VV002 M02/M03 A3005")
        assert "28°F" in r["temperature"]   # -2 C → 28 F
        assert "-2°C" in r["temperature"]

    def test_negative_dewpoint(self):
        r = parsed("METAR KORD 141852Z 04005KT 1/8SM FZFG VV002 M02/M03 A3005")
        assert "27°F" in r["dewpoint"]      # -3 C → 27 F
        assert "-3°C" in r["dewpoint"]

    def test_zero_temperature(self):
        r = parsed("METAR KORD 141852Z 04005KT 10SM CLR 00/M02 A3005")
        assert "32°F" in r["temperature"]   # 0 C → 32 F


# ── Altimeter ──────────────────────────────────────────────────────────────────

class TestAltimeter:
    def test_inches_hg(self):
        r = parsed("METAR KHIO 141853Z 19014KT 10SM CLR 09/04 A3006")
        assert r["altimeter"] == "30.06 inHg"

    def test_qnh_hpa(self):
        r = parsed("METAR EGLL 141850Z 27010KT 9999 BKN020 12/05 Q1015")
        assert r["altimeter"] == "1015 hPa"


# ── RMK termination ────────────────────────────────────────────────────────────

class TestRemarks:
    def test_rmk_fields_not_parsed(self):
        # Anything after RMK should be ignored — T-group would confuse temp parsing
        r = parsed("METAR KHIO 141853Z 19014KT 10SM CLR 09/04 A3006 RMK AO2 SLP180 T00940044")
        assert r["temperature"] == "48°F (9°C)"   # from 09/04, not T-group


# ── Summary sentence ───────────────────────────────────────────────────────────

class TestSummary:
    def test_summary_contains_temperature(self):
        r = parsed("METAR KJFK 141851Z 18016KT 10SM FEW060 22/13 A2993")
        assert "72°F" in r["summary"]

    def test_summary_contains_wind(self):
        r = parsed("METAR KJFK 141851Z 18016KT 10SM FEW060 22/13 A2993")
        assert "wind" in r["summary"].lower()

    def test_summary_contains_sky_condition(self):
        r = parsed("METAR KJFK 141851Z 18016KT 10SM FEW060 22/13 A2993")
        assert "clear" in r["summary"].lower() or "cloud" in r["summary"].lower()

    def test_summary_mentions_weather_phenomena(self):
        r = parsed("METAR KORD 141852Z VRB03KT 1/4SM +TSRA FG OVC005 08/07 A2990")
        assert "thunderstorm" in r["summary"].lower()

    def test_calm_wind_in_summary(self):
        r = parsed("METAR KORD 141852Z 00000KT 10SM SKC 15/08 A3010")
        assert "calm" in r["summary"].lower()
