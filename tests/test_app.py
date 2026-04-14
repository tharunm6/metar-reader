"""
Integration tests for the Flask routes in app.py.

The real HTTP call to aviationweather.gov is replaced with
unittest.mock.patch so every test is deterministic and offline.
The Flask test client simulates GET and POST requests against the
running app without starting a real server.
"""

import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
import app as flask_app


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def client():
    """Return a Flask test client with testing mode on."""
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c


def mock_urlopen(metar_string: str):
    """
    Return a context-manager mock that mimics urllib.request.urlopen,
    yielding a response whose .read() returns the given METAR string.
    """
    mock_resp = MagicMock()
    mock_resp.read.return_value = metar_string.encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return patch("app.urllib.request.urlopen", return_value=mock_resp)


# ── Sample METAR strings ───────────────────────────────────────────────────────

METAR_CLEAR      = "METAR KHIO 141853Z 19014KT 10SM CLR 09/04 A3006 RMK AO2"
METAR_OVERCAST   = "METAR KSFO 141856Z 26011KT 10SM OVC029 14/07 A3022 RMK AO2"
METAR_THUNDERSTORM = "METAR KORD 141852Z VRB03KT 1/4SM +TSRA FG OVC005 08/07 A2990 RMK AO2"
METAR_SNOW       = "METAR KORD 141852Z 35010KT 2SM -SN OVC015 M02/M05 A3020 RMK AO2"
METAR_FREEZING   = "METAR KORD 141852Z 04005KT 1/8SM FZFG VV002 M02/M03 A3005 RMK AO2"


# ── GET request ────────────────────────────────────────────────────────────────

class TestGetRequest:
    def test_homepage_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_homepage_contains_form(self, client):
        resp = client.get("/")
        assert b"airport_code" in resp.data

    def test_homepage_has_no_weather_card(self, client):
        resp = client.get("/")
        assert b"weather-card" not in resp.data

    def test_homepage_shows_landing_hint(self, client):
        resp = client.get("/")
        assert b"landing-hint" in resp.data


# ── Input validation ───────────────────────────────────────────────────────────

class TestInputValidation:
    def test_empty_code_shows_error(self, client):
        resp = client.post("/", data={"airport_code": ""})
        assert b"Please enter" in resp.data

    def test_two_letter_code_rejected(self, client):
        resp = client.post("/", data={"airport_code": "KH"})
        assert b"3" in resp.data and b"4" in resp.data   # mentions 3-4 letters

    def test_five_letter_code_rejected(self, client):
        resp = client.post("/", data={"airport_code": "KHIOXX"})
        assert b"alert-error" in resp.data

    def test_code_with_digits_rejected(self, client):
        resp = client.post("/", data={"airport_code": "KH1O"})
        assert b"alert-error" in resp.data

    def test_code_is_uppercased(self, client):
        with mock_urlopen(METAR_CLEAR):
            resp = client.post("/", data={"airport_code": "khio"})
        assert b"KHIO" in resp.data


# ── Successful weather fetch ───────────────────────────────────────────────────

class TestWeatherFetch:
    def test_station_displayed(self, client):
        with mock_urlopen(METAR_CLEAR):
            resp = client.post("/", data={"airport_code": "KHIO"})
        assert b"KHIO" in resp.data

    def test_decoded_temperature_shown(self, client):
        with mock_urlopen(METAR_CLEAR):
            resp = client.post("/", data={"airport_code": "KHIO"})
        assert b"48" in resp.data    # 9 C → 48 F

    def test_decoded_wind_shown(self, client):
        with mock_urlopen(METAR_CLEAR):
            resp = client.post("/", data={"airport_code": "KHIO"})
        assert b"mph" in resp.data

    def test_raw_metar_in_page(self, client):
        with mock_urlopen(METAR_CLEAR):
            resp = client.post("/", data={"airport_code": "KHIO"})
        assert b"19014KT" in resp.data   # raw token visible in the raw section

    def test_overcast_sky_badge(self, client):
        with mock_urlopen(METAR_OVERCAST):
            resp = client.post("/", data={"airport_code": "KSFO"})
        assert b"sky-overcast" in resp.data

    def test_thunderstorm_condition_shown(self, client):
        with mock_urlopen(METAR_THUNDERSTORM):
            resp = client.post("/", data={"airport_code": "KORD"})
        assert b"thunderstorm" in resp.data.lower()

    def test_snow_condition_shown(self, client):
        with mock_urlopen(METAR_SNOW):
            resp = client.post("/", data={"airport_code": "KORD"})
        assert b"snow" in resp.data.lower()

    def test_freezing_fog_shown(self, client):
        with mock_urlopen(METAR_FREEZING):
            resp = client.post("/", data={"airport_code": "KORD"})
        assert b"freezing" in resp.data.lower()

    def test_airport_code_repopulates_input(self, client):
        with mock_urlopen(METAR_CLEAR):
            resp = client.post("/", data={"airport_code": "KHIO"})
        assert b'value="KHIO"' in resp.data


# ── Empty / error API responses ────────────────────────────────────────────────

class TestApiErrors:
    def test_empty_response_shows_error(self, client):
        with mock_urlopen(""):
            resp = client.post("/", data={"airport_code": "ZZZZ"})
        assert b"alert-error" in resp.data
        assert b"ZZZZ" in resp.data

    def test_network_error_shows_error(self, client):
        import urllib.error
        with patch("app.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("connection refused")):
            resp = client.post("/", data={"airport_code": "KHIO"})
        assert b"alert-error" in resp.data
        assert b"weather service" in resp.data.lower()

    def test_unexpected_exception_shows_error(self, client):
        with patch("app.urllib.request.urlopen",
                   side_effect=Exception("something broke")):
            resp = client.post("/", data={"airport_code": "KHIO"})
        assert b"alert-error" in resp.data


# ── Template helpers ───────────────────────────────────────────────────────────

class TestTemplateHelpers:
    """Test sky_class() and sky_icon() directly (they are plain functions)."""

    def test_empty_clouds_is_clear(self):
        assert flask_app.sky_class([]) == "sky-clear"
        assert flask_app.sky_icon([]) == "☀️"

    def test_clear_skies(self):
        assert flask_app.sky_class(["clear skies"]) == "sky-clear"

    def test_few_clouds(self):
        assert flask_app.sky_class(["a few clouds at 3,000 ft"]) == "sky-few"
        assert flask_app.sky_icon(["a few clouds at 3,000 ft"]) == "🌤"

    def test_scattered_clouds(self):
        assert flask_app.sky_class(["scattered clouds at 4,000 ft"]) == "sky-scattered"
        assert flask_app.sky_icon(["scattered clouds at 4,000 ft"]) == "⛅"

    def test_broken_clouds(self):
        assert flask_app.sky_class(["broken clouds at 2,600 ft"]) == "sky-broken"
        assert flask_app.sky_icon(["broken clouds at 2,600 ft"]) == "🌥"

    def test_overcast(self):
        assert flask_app.sky_class(["overcast at 2,900 ft"]) == "sky-overcast"
        assert flask_app.sky_icon(["overcast at 2,900 ft"]) == "☁️"

    def test_sky_obscured(self):
        assert flask_app.sky_class(["sky obscured"]) == "sky-overcast"
        assert flask_app.sky_icon(["sky obscured"]) == "☁️"

    def test_only_first_layer_used(self):
        # A few clouds at the base with overcast higher up → "few" wins
        clouds = ["a few clouds at 3,000 ft", "overcast at 25,000 ft"]
        assert flask_app.sky_class(clouds) == "sky-few"
