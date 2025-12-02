# main.py
import os, json, traceback, datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

app = FastAPI(title="VedAstro Wrapper")

# CORS - change to your site for production
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN] if FRONTEND_ORIGIN != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# optional Google Sheet
GSHEET_ID = os.environ.get("GSHEET_ID")  # spreadsheet id
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")  # full JSON string

# Try import vedastro (may fail if not installed)
try:
    from vedastro import GeoLocation, Time, Calculate
    VEDASTRO_AVAILABLE = True
except Exception as e:
    VEDASTRO_AVAILABLE = False
    _vedastro_import_error = str(e)

# gspread helper (optional)
def write_to_sheet(result):
    if not GOOGLE_SERVICE_ACCOUNT_JSON or not GSHEET_ID:
        return False
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        creds_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(GSHEET_ID)
        try:
            ws = sh.worksheet("PanchangCache")
        except Exception:
            ws = sh.add_worksheet("PanchangCache", 200, 20)
            header = ["date","city","tithi","nakshatra","yoga","karan","rahu_kaal","gulika_kaal","abhijit","raw_json","updated_at"]
            ws.insert_row(header, index=1)
        row = [
            result.get("date"),
            result.get("city"),
            result.get("tithi"),
            result.get("nakshatra"),
            result.get("yoga"),
            result.get("karan"),
            result.get("rahu_kaal"),
            result.get("gulika_kaal"),
            result.get("abhijit"),
            json.dumps(result.get("raw", {})),
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]
        ws.append_row(row)
        return True
    except Exception as e:
        print("write_to_sheet error:", e)
        return False

# helper to try multiple function names on Calculate
def safe_call(name, *args, **kwargs):
    if not VEDASTRO_AVAILABLE:
        raise RuntimeError("VedAstro not available: " + _vedastro_import_error)
    fn = getattr(Calculate, name, None)
    if callable(fn):
        return fn(*args, **kwargs)
    # try alternatives
    for alt in (name.lower(), name.upper(), name.capitalize(), "All"+name, "Get"+name):
        fn = getattr(Calculate, alt, None)
        if callable(fn):
            return fn(*args, **kwargs)
    return None

@app.get("/")
def root():
    return {"status":"ok", "vedastro_available": VEDASTRO_AVAILABLE}

@app.get("/panchang")
def get_panchang(
    date: str = Query(None, description="YYYY-MM-DD or ISO"),
    lat: float = Query(26.9124),
    lon: float = Query(75.7873),
    tz: str = Query("Asia/Kolkata"),
    city: Optional[str] = Query("Jaipur")
):
    """
    Query example:
    GET /panchang?date=2025-12-02&lat=26.9124&lon=75.7873
    """
    try:
        if not date:
            date = datetime.date.today().isoformat()

        result = {
            "date": date,
            "city": city,
            "latitude": lat,
            "longitude": lon,
            "tithi": None,
            "nakshatra": None,
            "yoga": None,
            "karan": None,
            "rahu_kaal": None,
            "gulika_kaal": None,
            "abhijit": None,
            "raw": {}
        }

        if not VEDASTRO_AVAILABLE:
            # return a helpful error but still allow frontend to work in graceful mode
            result["raw"]["error"] = "vedastro not installed on server: " + _vedastro_import_error
            return result

        # Create geo/time objects: vedastro may expect different arg order — try common patterns
        # Many demos: GeoLocation("Name", longitude, latitude) or GeoLocation("Name", lat, lon)
        try:
            geol = GeoLocation(city, float(lon), float(lat))
        except Exception:
            geol = GeoLocation(city, float(lat), float(lon))

        # Time object: try ISO first, else construct a string "00:00 DD/MM/YYYY +05:30"
        iso_dt = date
        try:
            t = Time(iso_dt, geol)
        except Exception:
            # fallback: midnight with timezone offset if provided
            time_str = f"00:00 {date} +05:30"
            t = Time(time_str, geol)

        # attempt tithi, nakshatra, yoga, karan using several possible function names
        try:
            tithi_obj = safe_call("TithiAtTime", t)
            if tithi_obj is None:
                tithi_obj = safe_call("AllTithiData", t)
            result["tithi"] = getattr(tithi_obj, "name", str(tithi_obj)) if tithi_obj else None
            result["raw"]["tithi_obj"] = str(tithi_obj)
        except Exception as e:
            result["raw"]["tithi_error"] = str(e)

        try:
            nak_obj = safe_call("NakshatraAtTime", t) or safe_call("AllNakshatraData", t)
            result["nakshatra"] = getattr(nak_obj, "name", str(nak_obj)) if nak_obj else None
            result["raw"]["nakshatra_obj"] = str(nak_obj)
        except Exception as e:
            result["raw"]["nakshatra_error"] = str(e)

        try:
            yoga_obj = safe_call("YogaAtTime", t) or safe_call("AllYogaData", t)
            result["yoga"] = getattr(yoga_obj, "name", str(yoga_obj)) if yoga_obj else None
            result["raw"]["yoga_obj"] = str(yoga_obj)
        except Exception as e:
            result["raw"]["yoga_error"] = str(e)

        try:
            karan_obj = safe_call("KaranAtTime", t) or safe_call("AllKaranData", t)
            result["karan"] = getattr(karan_obj, "name", str(karan_obj)) if karan_obj else None
            result["raw"]["karan_obj"] = str(karan_obj)
        except Exception as e:
            result["raw"]["karan_error"] = str(e)

        # try to get rahu/gulika/abhijit — vedastro demos commonly provide helpers; try a few names
        try:
            rahu = safe_call("RahuKaalAtDate", t) or safe_call("GetRahuKaal", t) or safe_call("RahuKaal")
            result["rahu_kaal"] = str(rahu) if rahu else None
            result["raw"]["rahu_obj"] = str(rahu)
        except Exception as e:
            result["raw"]["rahu_error"] = str(e)

        try:
            gulika = safe_call("GulikaAtDate", t) or safe_call("GetGulika", t) or safe_call("Gulika")
            result["gulika_kaal"] = str(gulika) if gulika else None
            result["raw"]["gulika_obj"] = str(gulika)
        except Exception as e:
            result["raw"]["gulika_error"] = str(e)

        try:
            abh = safe_call("AbhijitAtDate", t) or safe_call("GetAbhijit", t)
            result["abhijit"] = str(abh) if abh else None
            result["raw"]["abhijit_obj"] = str(abh)
        except Exception as e:
            result["raw"]["abhijit_error"] = str(e)

        # Write to Google Sheet if configured (best-effort)
        try:
            wrote = write_to_sheet(result)
            result["raw"]["sheet_written"] = wrote
        except Exception as e:
            result["raw"]["sheet_error"] = str(e)

        return result

    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}\n{tb}")

