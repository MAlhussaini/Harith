from flask import Flask, request, render_template_string, make_response, jsonify, redirect, url_for
import json
import os

app = Flask(__name__)

SCHEDULE_FILE = "current_schedule.json"

# خطة افتراضية مع meta.days_valid
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


@app.after_request
def add_cors_headers(response):
    # لتسهيل الاتصال من Harith Push
    response.headers.setdefault("Access-Control-Allow-Origin", "*")
    response.headers.setdefault("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
    return response


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


@app.route("/")
def root():
    # تحويل مباشر للـ dashboard
    return redirect(url_for("dashboard"))


# =============== API للجوال (Harith Push) ===============

@app.route("/api/schedule", methods=["GET"])
def api_schedule():
    """يرجع آخر خطة مخزّنة كـ JSON (يستخدمه Harith Push)."""
    return jsonify(load_schedule())


# =============== تحميل ملف JSON يدوي ===============

HTML_DOWNLOAD_PAGE = r"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>حارث - تحميل الخطة (JSON)</title>
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
    textarea {
      width: 100%;
      min-height: 260px;
      border-radius: 8px;
      border: 1px solid #ccc;
      padding: 8px;
      font-family: monospace;
      font-size: 13px;
      box-sizing: border-box;
      direction: ltr;
      text-align: left;
    }
    button {
      padding: 10px 16px;
      border-radius: 8px;
      border: none;
      font-size: 16px;
      cursor: pointer;
      margin-top: 8px;
      width: 100%;
      background: #00897b;
      color: #fff;
    }
    .info { font-size: 14px; }
    .error { color: #e53935; font-size: 14px; margin-top: 8px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>حارث - تحميل / تعديل الخطة كـ JSON خام</h1>
    <p class="info">
      هذه الصفحة اختيارية. يفضّل استخدام <b>الـ Dashboard</b> للتحكم البصري،
      لكن يمكنك هنا تعديل JSON مباشرة أو تحميله كملف.
    </p>
    <p class="info">
      للعودة للـ Dashboard: <a href="/dashboard">/dashboard</a>
    </p>
  </div>

  <div class="card">
    <h2>الخطة الحالية (JSON)</h2>
    <form method="POST" action="/download">
      <textarea name="schedule_json">{{ schedule_json }}</textarea>
      <button type="submit">⬇ تحميل ملف JSON</button>
    </form>
    {% if error %}
      <div class="error">خطأ في JSON: {{ error }}</div>
    {% endif %}
  </div>
</body>
</html>
"""

@app.route("/download", methods=["GET", "POST"])
def download():
    if request.method == "GET":
        pretty = json.dumps(load_schedule(), ensure_ascii=False, indent=2)
        return render_template_string(HTML_DOWNLOAD_PAGE, schedule_json=pretty, error=None)

    text = request.form.get("schedule_json", "").strip()
    if not text:
        obj = load_schedule()
    else:
        try:
            obj = json.loads(text)
        except Exception as e:
            return render_template_string(
                HTML_DOWNLOAD_PAGE,
                schedule_json=text,
                error=str(e)
            )

    save_schedule(obj)
    pretty = json.dumps(obj, ensure_ascii=False, indent=2)
    resp = make_response(pretty)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Content-Disposition"] = 'attachment; filename="harith_schedule.json"'
    return resp


# =============== Dashboard للتحكم بعدد التايمرات والإعدادات ===============

HTML_DASHBOARD = r"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>حارث - Dashboard التايمرات والإعدادات</title>
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
    label {
      font-size: 14px;
      display: block;
      margin-bottom: 4px;
    }
    input[type="text"],
    input[type="number"],
    input[type="time"] {
      width: 100%;
      box-sizing: border-box;
      margin: 2px 0 8px;
      padding: 6px;
      border-radius: 8px;
      border: 1px solid #ccc;
      font-size: 13px;
      direction: ltr;
      text-align: left;
    }
    input[type="checkbox"] {
      transform: scale(1.1);
      margin-left: 4px;
    }
    .programs-container {
      margin-top: 8px;
    }
    .program-card {
      border-radius: 10px;
      border: 1px solid #e0e0e0;
      padding: 10px;
      margin-bottom: 10px;
      background: #fafafa;
    }
    .program-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 6px;
    }
    .program-title {
      font-weight: bold;
      font-size: 15px;
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
    .program-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 6px;
      font-size: 13px;
    }
    .program-grid > div {
      display: flex;
      flex-direction: column;
    }
    .program-actions {
      margin-top: 6px;
      text-align: left;
    }
    button {
      padding: 10px 16px;
      border-radius: 8px;
      border: none;
      font-size: 14px;
      cursor: pointer;
      margin-top: 8px;
      background: #00897b;
      color: #fff;
    }
    button.small {
      padding: 6px 10px;
      font-size: 12px;
      margin-top: 0;
      margin-right: 4px;
    }
    button.danger {
      background: #c62828;
    }
    .top-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .top-actions button {
      flex: 1 1 120px;
    }
    .info {
      font-size: 14px;
    }
    .status {
      margin-top: 8px;
      font-size: 14px;
    }
    .status.error { color: #e53935; }
    .status.success { color: #00897b; }
    .small-muted {
      font-size: 12px;
      color: #777;
      margin-top: 4px;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>حارث - Dashboard التايمرات والإعدادات</h1>
    <p class="info">
      من هنا تقدر تضيف/تحذف برامج الري (التايمرات) وتتحكم في:
    </p>
    <ul class="info">
      <li>اسم كل برنامج</li>
      <li>وقت بداية الري</li>
      <li>نمط الأيام في الأسبوع (مثال: 1111100 يعني من الأحد للخميس)</li>
      <li>مدد الري لكل زون بالثواني (مثال: 600,300,0)</li>
    </ul>
    <p class="small-muted">
      هذا الـ Dashboard مخصص لك (مالك النظام). المزارع يرى نسخة مبسطة عبر Harith Push.
    </p>
  </div>

  <div class="card">
    <h2>الإعدادات العامة</h2>
    <label for="days-valid">عدد الأيام التي تعتبر فيها الخطة “فعّالة” قبل التحول للوضع الثابت:</label>
    <input id="days-valid" type="number" min="1" max="365" />
    <p class="small-muted">
      هذا الحقل يُستخدم في رسالة Harith Push للمزارع
      (مثال: “سيعمل الري بكفاءة لمدة X يوم ثم سينتقل للوضع الثابت”).
    </p>
  </div>

  <div class="card">
    <h2>برامج الري (التايمرات)</h2>
    <div class="top-actions">
      <button type="button" id="add-program-btn">➕ إضافة برنامج جديد</button>
      <button type="button" id="save-btn">💾 حفظ الخطة</button>
      <button type="button" onclick="window.location.href='/download'">⬇ تحميل JSON خام (اختياري)</button>
    </div>
    {% if status_msg %}
      <div class="status {{ 'error' if status_error else 'success' }}">{{ status_msg }}</div>
    {% endif %}
    <div class="programs-container" id="programs-container"></div>
    <p class="small-muted">
      ملاحظات:
      <br>• “التايمر” هنا يعني برنامج ري واحد يمكن أن يخدم عدة زونات.
      <br>• “durations” هي مدد الري لكل زون بالثواني، مفصولة بفواصل (مثال: <code>600,300,0</code>).
    </p>
  </div>

  <form id="schedule-form" method="POST" action="/dashboard" style="display:none;">
    <input type="hidden" name="schedule_json" id="schedule-json-input" />
  </form>

  <script>
    const initialSchedule = {{ schedule|tojson }};
    let programs = Array.isArray(initialSchedule.programs) ? initialSchedule.programs.slice() : [];
    let meta = initialSchedule.meta || {};

    function getNextPid() {
      let maxPid = -1;
      for (const p of programs) {
        const pid = typeof p.pid === "number" ? p.pid : -1;
        if (pid > maxPid) maxPid = pid;
      }
      return maxPid + 1;
    }

    function renderPrograms() {
      const container = document.getElementById("programs-container");
      if (!programs.length) {
        container.innerHTML = "<p class='info'>لا توجد برامج حالياً. اضغط “إضافة برنامج جديد”.</p>";
        return;
      }

      let html = "";
      programs.forEach((p, idx) => {
        const pid = (typeof p.pid === "number") ? p.pid : idx;
        const name = p.name || ("برنامج #" + pid);
        const start = p.start || "06:00";
        const days = (p.days || "").toString() || "1111100";
        const enabled = !!p.en;
        const durList = Array.isArray(p.dur) ? p.dur : [];
        const durStr = durList.join(",");

        html += `
          <div class="program-card" data-pid="${pid}">
            <div class="program-header">
              <div class="program-title">
                ${name}
                <span class="badge ${enabled ? "" : "off"}">
                  ${enabled ? "مفعّل" : "موقوف"}
                </span>
              </div>
              <div>
                <label style="font-size:12px;">
                  <input type="checkbox" class="field-en" ${enabled ? "checked" : ""} />
                  مفعّل
                </label>
              </div>
            </div>
            <div class="program-grid">
              <div>
                <label>اسم البرنامج:</label>
                <input type="text" class="field-name" value="${name.replace(/"/g, "&quot;")}" />
              </div>
              <div>
                <label>وقت بداية الري (HH:MM):</label>
                <input type="time" class="field-start" value="${start}" />
              </div>
              <div>
                <label>نمط الأيام (0/1 بطول 7، مثال: 1111100):</label>
                <input type="text" class="field-days" value="${days}" />
              </div>
              <div>
                <label>مدد الري بالثواني لكل زون (مثال: 600,300,0):</label>
                <input type="text" class="field-dur" value="${durStr}" />
              </div>
            </div>
            <div class="program-actions">
              <button type="button" class="small danger" onclick="deleteProgram(${pid})">🗑 حذف هذا البرنامج</button>
            </div>
          </div>
        `;
      });

      container.innerHTML = html;
    }

    function deleteProgram(pid) {
      programs = programs.filter(p => {
        const ppid = (typeof p.pid === "number") ? p.pid : -1;
        return ppid !== pid;
      });
      renderPrograms();
    }

    function addProgram() {
      const pid = getNextPid();
      programs.push({
        pid: pid,
        en: 1,
        name: "برنامج جديد #" + pid,
        start: "06:00",
        days: "1111100",
        dur: [600]
      });
      renderPrograms();
    }

    function loadMetaToUI() {
      const dv = document.getElementById("days-valid");
      let days = 15;
      if (meta && typeof meta.days_valid === "number") {
        days = meta.days_valid;
      }
      dv.value = days;
    }

    function saveSchedule() {
      const container = document.getElementById("programs-container");
      const cards = container.querySelectorAll(".program-card");
      const newPrograms = [];

      cards.forEach((card, idx) => {
        const pidAttr = card.getAttribute("data-pid");
        const pid = parseInt(pidAttr, 10);
        const name = card.querySelector(".field-name").value.trim() || ("برنامج #" + pid);
        const start = card.querySelector(".field-start").value.trim() || "06:00";
        const days = card.querySelector(".field-days").value.trim() || "1111100";
        const en = card.querySelector(".field-en").checked ? 1 : 0;
        const durStr = card.querySelector(".field-dur").value.trim();

        let durs = [];
        if (durStr) {
          durs = durStr.split(",").map(s => {
            const v = parseInt(s.trim(), 10);
            return isNaN(v) ? 0 : v;
          });
        }

        newPrograms.push({
          pid: pid,
          en: en,
          name: name,
          start: start,
          days: days,
          dur: durs
        });
      });

      const dvInput = document.getElementById("days-valid");
      let daysValid = parseInt(dvInput.value, 10);
      if (isNaN(daysValid) || daysValid <= 0) {
        daysValid = 15;
      }

      const newSchedule = {
        programs: newPrograms,
        meta: {
          days_valid: daysValid
        }
      };

      const hiddenInput = document.getElementById("schedule-json-input");
      hiddenInput.value = JSON.stringify(newSchedule);
      document.getElementById("schedule-form").submit();
    }

    document.getElementById("add-program-btn").addEventListener("click", addProgram);
    document.getElementById("save-btn").addEventListener("click", saveSchedule);

    loadMetaToUI();
    renderPrograms();
  </script>
</body>
</html>
"""

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
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

    return render_template_string(
        HTML_DASHBOARD,
        schedule=schedule,
        status_msg=status_msg,
        status_error=status_error
    )


if __name__ == "__main__":
    # شغّل هذا في البيت / المكتب
    # مثال:
    #   python harith_server.py
    app.run(host="0.0.0.0", port=8000, debug=False)
