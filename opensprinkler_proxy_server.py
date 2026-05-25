from flask import Flask, request, render_template_string, jsonify, Response
import os
import json
import hashlib
import requests
from datetime import datetime

app = Flask(__name__)

OS_BASE_URL = os.environ.get("OS_BASE_URL", "http://192.168.1.50")
OS_PASSWORD = os.environ.get("OS_PASSWORD", "opendoor")
REQUEST_TIMEOUT = 5
LAST_SCHEDULE_FILE = "last_schedule.json"


@app.after_request
def add_cors(response):
    # يسمح لصفحة Harith Push تتصل بالـ /co من أي شبكة داخلية
    response.headers.setdefault("Access-Control-Allow-Origin", "*")
    response.headers.setdefault("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
    return response


@app.route("/co", methods=["OPTIONS"])
def co_options():
    # للـ CORS preflight
    return ("", 204)


def get_md5_pw():
    return hashlib.md5(OS_PASSWORD.encode("utf-8")).hexdigest()


def os_url(path: str) -> str:
    return OS_BASE_URL.rstrip("/") + path


def proxy_get(path: str) -> Response:
    try:
        r = requests.get(os_url(path), params=request.args, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        return Response(json.dumps({"error": f"فشل الاتصال بـ OpenSprinkler: {e}"}),
                        status=502, mimetype="application/json")
    resp = Response(r.content, status=r.status_code)
    for k, v in r.headers.items():
        if k.lower() in ("content-type", "cache-control"):
            resp.headers[k] = v
    return resp


@app.route("/js", methods=["GET"])
def api_js():
    return proxy_get("/js")


@app.route("/jc", methods=["GET"])
def api_jc():
    return proxy_get("/jc")


@app.route("/ja", methods=["GET"])
def api_ja():
    return proxy_get("/ja")


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
        # تاريخ/وقت آخر تعديل للملف حسب توقيت جهاز السيرفر
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


@app.route("/co", methods=["POST"])
def co_post():
    """
    API بالنسبة للجوال (/co مثل OpenSprinkler):
    - يستقبل JSON (الخطة) من Harith Push
    - يحفظها في last_schedule.json
    - يرسلها لـ OpenSprinkler الحقيقي مع pw=MD5
    """
    if not request.is_json:
        return jsonify({"error": "الطلب يجب أن يكون JSON."}), 400

    body = request.get_json(silent=True)
    if body is None:
        return jsonify({"error": "تعذر قراءة JSON."}), 400

    save_last_schedule(body)

    try:
        r = proxy_post_json("/co", body, extra_params={"pw": get_md5_pw()})
    except Exception as e:
        return jsonify({"error": f"فشل الاتصال بـ OpenSprinkler: {e}"}), 502

    try:
        os_resp = r.json()
    except Exception:
        os_resp = {"raw": r.text}

    return jsonify({
        "proxied": True,
        "status_code": r.status_code,
        "os_response": os_resp
    }), r.status_code


# ========== API إضافي للـ Dashboard (تغذية تلقائية) ==========

@app.route("/dashboard_data", methods=["GET"])
def dashboard_data():
    """
    يرجع بيانات الـ Dashboard كـ JSON:
    - ملخص آخر خطة
    - وقت آخر تحديث
    - حالة /ja
    يستخدمه JavaScript في صفحة /dashboard للتحديث التلقائي.
    """
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


# ========== Dashboard مع تحديث تلقائي ==========
DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Dashboard - OpenSprinkler Proxy</title>
  <style>
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      padding: 16px;
      background: #f5f5f5;
      color: #222;
    }
    .card {
      background: #fff;
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 16px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    h1, h2 {
      margin-top: 0;
      font-size: 20px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 8px;
      font-size: 13px;
    }
    th, td {
      border: 1px solid #ddd;
      padding: 6px;
      text-align: center;
    }
    th {
      background: #eeeeee;
    }
    pre {
      white-space: pre-wrap;
      word-wrap: break-word;
      background: #fafafa;
      padding: 10px;
      border-radius: 8px;
      font-family: monospace;
      font-size: 12px;
      max-height: 260px;
      overflow-y: auto;
      direction: ltr;
      text-align: left;
    }
    .info {
      font-size: 14px;
    }
    .error {
      color: #e53935;
      font-size: 14px;
    }
    .muted {
      font-size: 12px;
      color: #777;
      margin-top: 4px;
    }
    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 11px;
      margin-right: 4px;
      background: #e0f2f1;
      color: #00695c;
    }
    .badge.off {
      background: #ffebee;
      color: #c62828;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>Dashboard - OpenSprinkler Proxy</h1>
    <p class="info">
      هذه الواجهة لمراجعة آخر خطة استقبلها السيرفر من الجوال،
      وكذلك حالة OpenSprinkler من /ja.
      يتم التحديث تلقائيًا كل 10 ثوانٍ تقريبًا.
    </p>
  </div>

  <div class="card">
    <h2>1. ملخص آخر خطة (last_schedule.json)</h2>
    <p class="info" id="last-updated-text">
      آخر تحديث للخطة: — 
    </p>
    <p class="info">
      عدد البرامج: <b id="programs-count">0</b>
    </p>
    <table>
      <thead>
        <tr>
          <th>pid</th>
          <th>الاسم</th>
          <th>مفعّل؟</th>
          <th>وقت البدء</th>
          <th>الأيام</th>
          <th>عدد مدد الري</th>
        </tr>
      </thead>
      <tbody id="programs-table-body">
        <tr><td colspan="6">لا توجد بيانات بعد.</td></tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>2. حالة OpenSprinkler (/ja)</h2>
    <div id="ja-error" class="error" style="display:none;"></div>
    <pre id="ja-data"></pre>
    <div class="muted">
      ملاحظة: الوقت داخل بيانات /ja يعتمد على إعدادات التوقيت في جهاز OpenSprinkler نفسه.
    </div>
  </div>

  <script>
    function renderDashboard(data) {
      const lastUpdatedEl = document.getElementById("last-updated-text");
      const countEl = document.getElementById("programs-count");
      const tbody = document.getElementById("programs-table-body");
      const jaErrorEl = document.getElementById("ja-error");
      const jaDataEl = document.getElementById("ja-data");

      const lastUpdated = data.last_updated || "لم يتم استلام أي خطة بعد.";
      lastUpdatedEl.innerHTML = "آخر تحديث للخطة: <b>" + lastUpdated + "</b>";

      const summary = data.last_summary || { programs_count: 0, programs: [] };
      const programs = Array.isArray(summary.programs) ? summary.programs : [];
      countEl.textContent = summary.programs_count || programs.length || 0;

      if (!programs.length) {
        tbody.innerHTML = '<tr><td colspan="6">لا توجد برامج في الخطة الحالية.</td></tr>';
      } else {
        let rows = "";
        programs.forEach(p => {
          const pid = (p.pid !== undefined && p.pid !== null) ? p.pid : "";
          const name = p.name || "-";
          const en = p.en ? "نعم" : "لا";
          const start = p.start || "-";
          const days = p.days || "-";
          const durLen = p.dur_len || 0;

          rows += `
            <tr>
              <td>${pid}</td>
              <td>${name}</td>
              <td>${en}</td>
              <td>${start}</td>
              <td>${days}</td>
              <td>${durLen}</td>
            </tr>
          `;
        });
        tbody.innerHTML = rows;
      }

      const jaError = data.ja_error;
      const jaData = data.ja_data;

      if (jaError) {
        jaErrorEl.style.display = "block";
        jaErrorEl.textContent = "تعذر قراءة /ja: " + jaError;
      } else {
        jaErrorEl.style.display = "none";
      }

      if (jaData) {
        jaDataEl.textContent = jaData;
      } else {
        jaDataEl.textContent = "لا توجد بيانات من /ja.";
      }
    }

    function fetchDashboardData() {
      fetch("/dashboard_data")
        .then(res => res.json())
        .then(data => {
          renderDashboard(data);
        })
        .catch(err => {
          console.log("Error fetching dashboard_data:", err);
        });
    }

    // تحميل أولي ثم تحديث كل 10 ثوانٍ
    fetchDashboardData();
    setInterval(fetchDashboardData, 10000);
  </script>
</body>
</html>
"""

@app.route("/dashboard", methods=["GET"])
def dashboard():
    # الصفحة نفسها ثابتة والبيانات تجي من /dashboard_data (AJAX)
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/test", methods=["GET"])
def api_test():
    return jsonify({"ok": True, "message": "OpenSprinkler proxy server is running."})


if __name__ == "__main__":
    # مثال تشغيل:
    # OS_BASE_URL="http://192.168.1.50" OS_PASSWORD="opendoor" python opensprinkler_proxy_server.py
    app.run(host="0.0.0.0", port=8000, debug=False)
