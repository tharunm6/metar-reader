# METAR Reader

A Flask web application that translates raw aviation weather reports (METARs) into plain English.

Type in any ICAO airport code and get a friendly, readable summary — temperature, wind, visibility, sky conditions, and more — instead of the cryptic shorthand pilots use.

**Example output for KHIO:**
> Mostly cloudy. 48°F (9°C). Winds 16 mph from the S (190°), gusting to 23 mph. Visibility 10+ miles (excellent).

## What is a METAR?

A METAR (Meteorological Aerodrome Report) is a standardised weather observation issued by airports around the world. They look like this:

```
METAR KJFK 141851Z 18016KT 10SM FEW060 BKN250 22/13 A2993 RMK AO2
```

This app decodes every field into something a non-pilot can understand.

## Features

- Live data fetched directly from [aviationweather.gov](https://aviationweather.gov)
- Decodes wind direction (degrees → compass), speed (knots → mph), and gusts
- Translates visibility, cloud layers, and sky conditions
- Handles present weather: rain, snow, thunderstorms, freezing conditions, fog, and more
- Converts temperature from Celsius to Fahrenheit
- Shows the raw METAR alongside the decoded result

## Installation

**Requirements:** Python 3.9+

```bash
# 1. Clone the repository
git clone https://github.com/your-username/metar-reader.git
cd metar-reader

# 2. Create and activate a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## Usage

Enter a 3- or 4-letter airport code and press **Get Weather**.

| Code format | Example | Notes |
|-------------|---------|-------|
| ICAO (4-letter) | `KJFK`, `KSFO`, `EGLL` | Recommended — most reliable |
| IATA (3-letter) | `LAX`, `ORD` | Works for many major airports |

US airports typically use a `K` prefix followed by the 3-letter IATA code (e.g. `KHIO` for Hillsboro, OR).

## Testing

The project has 78 tests split across two files, covering both the decoding logic and the Flask routes.

```bash
pytest
```

| File | Tests | What it covers |
|------|-------|----------------|
| `tests/test_parser.py` | 49 | METAR decoding: wind, visibility, clouds, weather phenomena, temperature, altimeter, RMK termination, summary sentence |
| `tests/test_app.py` | 29 | Flask routes: GET/POST, input validation, rendered HTML output, error handling, `sky_class`/`sky_icon` helpers |

Route tests use `unittest.mock.patch` to replace the live API call with mock METAR strings — no network access required. The suite runs in under a second.

## Project Structure

```
metar-reader/
├── app.py              # Flask application and template helpers
├── metar_parser.py     # METAR decoding logic (no third-party dependencies)
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Jinja2 template
├── static/
│   └── style.css       # Stylesheet
└── tests/
    ├── test_parser.py  # Unit tests for metar_parser.py
    └── test_app.py     # Integration tests for Flask routes
```

## Data Source

Weather data is provided by the [Aviation Weather Center](https://aviationweather.gov) (NOAA), a US government service. Data is fetched in real time on each request.
