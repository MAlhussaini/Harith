from flask import (
    Flask,
    request,
    render_template,
    make_response,
    jsonify,
    redirect,
    url_for,
)

import json
import os
import hashlib
import requests
from datetime import datetime

app = Flask(__name__)

# ================= إعدادات حارث =================

SCHEDULE_FILE = "current_schedule.json"

DEFAULT_SCHEDULE = {
    "programs": [
        {
            "pid": 0,
            "en": 1,
            "name": "North Field",
            "start": "06:00",
            "days": "1101100",
            "dur": [600, 0, 0]
        },
        {
            "pid": 1,
            "en": 1,
            "name": "South Field",
            "start": "18:00",
            "days": "1010101",
            "dur": [300, 300, 0]
        }
    ],
    "meta": {
        "days_valid": 15
    }
}

# ================= إعدادات OpenSprinkler Proxy =================

OS_BASE_URL = os.environ.get("OS_BASE_URL", "http://192.168.1.50")
OS_PASSWORD = os.environ.get("OS_PASSWORD", "opendoor")
REQUEST_TIMEOUT = 5
LAST_SCHEDULE_FILE = "last_schedule.json"


@app.after_request
def add_cors_headers(response):
    # لتسهيل الاتصال من صفحة المزارع وغيره
    response.headers.setdefault("Access-Control-Allow-Origin", "*")
    response.headers.setdefault("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
    return response


# ================= دوال مساعدة لحارث =================

def load_schedule():
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_SCHEDULE


def save_schedule(obj):
    try:
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ================= دوال مساعدة لـ OpenSprinkler Proxy =================

def get_md5_pw():
    return hashlib.md5(OS_PASSWORD.encode("utf-8")).hexdigest()


def os_url(path: str) -> str:
    return OS_BASE_URL.rstrip("/") + path


def proxy_get(path: str):
    try:
        r = requests.get(os_url(path), params=request.args, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        return jsonify({"error": f"فشل الاتصال بـ OpenSprinkler: {e}"}), 502
    resp = make_response(r.content, r.status_code)
    for k, v in r.headers.items():
        if k.lower() in ("content-type", "cache-control"):
            resp.headers[k] = v
    return resp


def proxy_post_json(path: str, json_body: dict, extra_params: dict = None) -> requests.Response:
    params = dict(request.args) if request else {}
    if extra_params:
        params.update(extra_params)
    params.pop("pw", None)
    r = requests.post(os_url(path), params=params, json=json_body, timeout=REQUEST_TIMEOUT)
    return r


def save_last_schedule(obj: dict):
    try:
        with open(LAST_SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_last_schedule():
    if not os.path.exists(LAST_SCHEDULE_FILE):
        return None
    try:
        with open(LAST_SCHEDULE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_last_updated_str():
    if not os.path.exists(LAST_SCHEDULE_FILE):
        return None
    try:
        ts = os.path.getmtime(LAST_SCHEDULE_FILE)
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def summarize_schedule(data: dict):
    if not isinstance(data, dict):
        return {"programs_count": 0, "programs": []}
    programs = data.get("programs")
    info = []
    if isinstance(programs, list):
        for p in programs:
            if not isinstance(p, dict):
                continue
            dur = p.get("dur")
            info.append({
                "pid": p.get("pid"),
                "name": p.get("name"),
                "en": p.get("en"),
                "start": p.get("start"),
                "days": p.get("days"),
                "dur_len": len(dur) if isinstance(dur, (list, tuple)) else 0
            })
    return {"programs_count": len(info), "programs": info}


# ================= الصفحات =================

@app.route("/")
def index():
    return render_template("index.html")


# -------- حارث: API و Dashboard --------

@app.route("/api/schedule", methods=["GET"])
def api_schedule():
    return jsonify(load_schedule())


@app.route("/harith/dashboard", methods=["GET", "POST"])
def harith_dashboard():
    status_msg = None
    status_error = False
    schedule = load_schedule()

    if request.method == "POST":
        text = request.form.get("schedule_json", "").strip()
        if not text:
            status_msg = "لم يتم استلام بيانات الخطة من الواجهة."
            status_error = True
        else:
            try:
                obj = json.loads(text)
                save_schedule(obj)
                schedule = obj
                status_msg = "تم حفظ الخطة بنجاح."
                status_error = False
            except Exception as e:
                status_msg = f"خطأ في JSON المُرسل من الواجهة: {e}"
                status_error = True

    return render_template(
        "harith_dashboard.html",
        schedule=schedule,
        status_msg=status_msg,
        status_error=status_error,
    )


# -------- صفحة المزارع (Farmer) --------

@app.route("/farmer")
def farmer_page():
    return render_template("farmer.html")

@app.route("/report")
def irrigation_report():
    return render_template("report.html")


# -------- OpenSprinkler Proxy APIs --------

@app.route("/co", methods=["OPTIONS"])
def co_options():
    return ("", 204)

@app.route("/co", methods=["POST"])
def co_post():
    if not request.is_json:
        return jsonify({"error": "الطلب يجب أن يكون JSON."}), 400

    body = request.get_json(silent=True)
    if body is None:
        return jsonify({"error": "تعذر قراءة JSON."}), 400

    # 1) نحفظ الخطة في السيرفر دائماً (نجاح أساسي)
    save_last_schedule(body)

    # 2) نحاول إرسالها إلى جهاز OpenSprinkler (إن وجد)
    os_info = {
        "forwarded": False,
        "status_code": None,
        "response": None,
        "error": None,
    }

    try:
        r = proxy_post_json("/co", body, extra_params={"pw": get_md5_pw()})
        os_info["status_code"] = r.status_code
        try:
            os_info["response"] = r.json()
        except Exception:
            os_info["response"] = r.text

        # نعتبره ناجح إذا رد بأي كود < 400
        if r.status_code < 400:
            os_info["forwarded"] = True
        else:
            os_info["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        # فقط تحذير، ما نرجعها كـ error للمزارع
        os_info["error"] = str(e)

    # نرجع دائماً ok للمزارع، مع معلومات إضافية عن حالة جهاز الري
    return jsonify({
        "ok": True,
        "stored_locally": True,
        "os": os_info,
    })

@app.route("/js", methods=["GET"])
def api_js():
    return proxy_get("/js")


@app.route("/jc", methods=["GET"])
def api_jc():
    return proxy_get("/jc")


@app.route("/ja", methods=["GET"])
def api_ja():
    return proxy_get("/ja")


# -------- OpenSprinkler Dashboard Data & Page --------

@app.route("/os/dashboard_data", methods=["GET"])
def os_dashboard_data():
    last = load_last_schedule()
    last_summary = summarize_schedule(last) if last else {"programs_count": 0, "programs": []}
    last_updated = get_last_updated_str()

    ja_data = None
    ja_error = None
    try:
        r_ja = requests.get(os_url("/ja"), params={"pw": get_md5_pw()}, timeout=REQUEST_TIMEOUT)
        if r_ja.ok:
            try:
                ja_json = r_ja.json()
                ja_data = json.dumps(ja_json, ensure_ascii=False, indent=2)
            except Exception:
                ja_data = r_ja.text
        else:
            ja_error = f"HTTP {r_ja.status_code}"
    except Exception as e:
        ja_error = str(e)

    return jsonify({
        "last_updated": last_updated,
        "last_summary": last_summary,
        "ja_data": ja_data,
        "ja_error": ja_error
    })


@app.route("/os/dashboard", methods=["GET"])
def os_dashboard():
    return render_template("os_dashboard.html")


# -------- اختبار --------

@app.route("/api/test")
def api_test():
    return jsonify({"ok": True, "message": "Harith unified server running."})


if __name__ == "__main__":
    # مثال تشغيل:
    #   OS_BASE_URL="http://192.168.1.50" OS_PASSWORD="opendoor" python harith_server.py
    app.run(host="0.0.0.0", port=8000, debug=True)
