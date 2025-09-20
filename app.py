from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"

# шаги сетки (в THz)
STEP_12_5 = Decimal("0.0125")   # 12.5 GHz
STEP_6_25 = Decimal("0.00625")  # 6.25  GHz

app = FastAPI(title="C-band helper")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

# ---------- точные округления ----------
def q(x, nd=5) -> float:
    """Округление к nd знакам после запятой без артефактов float."""
    d = Decimal(str(x)).quantize(Decimal("1." + "0"*nd), rounding=ROUND_HALF_UP)
    return float(d)

def snap(value_thz: Decimal, step: Decimal) -> Decimal:
    """Привязка к ближайшей точке сетки (6.25 или 12.5 ГГц)."""
    k = (value_thz / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return k * step

def width_thz(slices: int) -> Decimal:
    # 1 THz = 1000 GHz
    return Decimal(slices * 12.5) / Decimal(1000)

# ---------- загрузка таблицы nm↔THz (если есть) ----------
# форматируем список пар (nm, thz)
_nm2thz: list[tuple[float, float]] = []

def try_load_mapping():
    """Читаем любую *.txt в data/, которая содержит 'wavelength' и пары 'xxxx.xx nm/yyyy.yy THz'."""
    global _nm2thz
    _nm2thz = []
    if not DATA_DIR.exists():
        return
    for p in sorted(DATA_DIR.glob("*.txt")):
        if "wavelength" not in p.name.lower():
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.search(r"(\d+(?:[.,]\d+)?)\s*nm\s*/\s*(\d+(?:[.,]\d+)?)\s*thz", line, flags=re.I)
            if m:
                nm = float(m.group(1).replace(",", "."))
                thz = float(m.group(2).replace(",", "."))
                _nm2thz.append((nm, thz))
    _nm2thz.sort(key=lambda t: t[0])

try_load_mapping()

def nm_to_thz(nm: float) -> float:
    """По возможности используем таблицу, иначе физическую формулу (c/λ)."""
    if _nm2thz:
        best = min(_nm2thz, key=lambda t: abs(t[0] - nm))
        thz = best[1]
    else:
        thz = 299_792.458 / nm
    return float(q(snap(Decimal(str(thz)), STEP_6_25), 5))

def thz_to_nm(thz: float) -> float:
    """Обратное преобразование: по таблице (ближайшее), иначе формула."""
    if _nm2thz:
        best = min(_nm2thz, key=lambda t: abs(t[1] - thz))
        nm = best[0]
    else:
        nm = 299_792.458 / thz
    return float(Decimal(str(nm)).quantize(Decimal("1.00000"), rounding=ROUND_HALF_UP))

# ---------- автодетект единиц в режиме А ----------
_unit_re = re.compile(r"(nm|thz)", re.I)

def parse_center_any(s: str) -> float:
    """
    Принимает строку с центром, понимает 'nm' / 'THz' / просто число.
    - если явно есть 'nm' → считаем как нм
    - если явно есть 'thz' → считаем как ТГц
    - иначе по величине: >= 1000 → нм; иначе → ТГц
    Возвращает частоту центра в ТГц, привязанную к сетке 6.25 ГГц.
    """
    raw = (s or "").strip()
    m = _unit_re.search(raw)
    unit_hint = m.group(1).lower() if m else None

    # вытащим первое число в строке
    m2 = re.search(r"([-+]?\d+(?:[.,]\d+)?)", raw)
    if not m2:
        raise ValueError("Не найдено числовое значение центра.")
    val = float(m2.group(1).replace(",", "."))

    if unit_hint == "nm" or (unit_hint is None and val >= 1000):
        return nm_to_thz(val)
    # иначе THz
    return float(q(snap(Decimal(str(val)), STEP_6_25), 5))

# ---------- модели ----------
class CalcByCenter(BaseModel):
    slices: int
    value: str  # строка, автоопределение единиц

class CalcByStart(BaseModel):
    slices: int
    start_thz: float

# ---------- маршруты ----------
@app.get("/healthz")
def health():
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def index():
    return (APP_DIR / "static" / "index.html").read_text(encoding="utf-8")

@app.post("/calc_center")
def calc_center(payload: CalcByCenter):
    slices = 6 if payload.slices != 7 else 7
    center_thz = parse_center_any(payload.value)

    half = width_thz(slices) / Decimal(2)
    start = snap(Decimal(str(center_thz)) - half, STEP_12_5)
    end   = snap(Decimal(str(center_thz)) + half, STEP_12_5)

    width_ghz = 12.5 * slices
    center_nm = thz_to_nm(center_thz)

    return JSONResponse({
        "slices": slices,
        "band":  [q(start,5), q(end,5)],
        "center_thz": q(center_thz,5),
        "center_nm": center_nm,
        "width_ghz": float(width_ghz)
    })

@app.post("/calc_from_start")
def calc_from_start(payload: CalcByStart):
    slices = 6 if payload.slices != 7 else 7
    w = width_thz(slices)
    start = snap(Decimal(str(payload.start_thz)), STEP_12_5)
    end   = snap(start + w, STEP_12_5)
    center = snap((start + end) / Decimal(2), STEP_6_25)

    width_ghz = 12.5 * slices
    center_nm = thz_to_nm(float(center))

    return JSONResponse({
        "slices": slices,
        "band":  [q(start,5), q(end,5)],
        "center_thz": q(center,5),
        "center_nm": center_nm,
        "width_ghz": float(width_ghz)
    })
