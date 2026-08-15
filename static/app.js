/* 每日打卡 前端逻辑 */
"use strict";

// ---------- 工具 ----------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(node.dataset, v);
    else if (v !== undefined && v !== null) node.setAttribute(k, v);
  }
  for (const c of children) {
    if (c === null || c === undefined) continue;
    node.append(c.nodeType ? c : document.createTextNode(c));
  }
  return node;
}

async function api(path, options = {}) {
  const opts = { headers: {}, ...options };
  if (opts.body && typeof opts.body !== "string") {
    opts.body = JSON.stringify(opts.body);
    opts.headers["Content-Type"] = "application/json";
  }
  const res = await fetch(path, opts);
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    state.user = null;
    showLogin();
    throw new Error("请先登录");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const msg = (data && data.detail) || `请求失败（${res.status}）`;
    if (typeof data === "string") throw new Error(data);
    throw new Error(msg);
  }
  return data;
}

let toastTimer = null;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 2600);
}

const WEEK_CN = ["日", "一", "二", "三", "四", "五", "六"];
const fmtDate = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parseFmt = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };

const state = {
  user: null,
  view: "today",
  todayDate: fmtDate(new Date()),
  habits: [],
  todayData: null,
  calYear: null,
  calMonth: null,
  monthStats: null,
  bp: { days: 90, records: [], avgSys: null, avgDia: null, count: 0 },
  metrics: { records: [], latest: {}, editingId: null },
  analysis: { days: 30, list: [], current: null, loading: false },
  editingBpId: null,
  editingHabitId: null,
  authMode: "login",
};

// ---------- 初始化 ----------
async function init() {
  bindNav();
  window.addEventListener("hashchange", onHashChange);
  try {
    state.user = await api("/api/auth/me");
    if (!location.hash) location.hash = "#today";
    onHashChange();
  } catch (e) {
    showLogin();
  }
}

function bindNav() {
  $$(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      location.hash = "#" + btn.dataset.view;
    });
  });
}

function onHashChange() {
  const view = (location.hash || "#today").replace("#", "");
  const valid = ["today", "calendar", "bp", "analysis", "habits", "settings"];
  state.view = valid.includes(view) ? view : "today";
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === state.view));
  $("#nav").classList.remove("hidden");
  renderView();
}

function renderView() {
  const titleMap = {
    today: "每日打卡",
    calendar: "日历与统计",
    bp: "健康记录",
    analysis: "AI 分析",
    habits: "习惯管理",
    settings: "我的",
  };
  $("#page-title").textContent = titleMap[state.view];
  $("#header-sub").textContent = state.user ? `${state.user.username} · ${todayTitle()}` : "";
  const main = $("#main");
  main.innerHTML = "";
  const loaders = {
    today: loadToday,
    calendar: loadCalendar,
    bp: loadBp,
    analysis: loadAnalysis,
    habits: loadHabits,
    settings: loadSettings,
  };
  main.appendChild(el("div", { class: "loading" }, "加载中…"));
  loaders[state.view]().catch((e) => {
    main.innerHTML = "";
    main.appendChild(el("div", { class: "empty-tip" }, e.message));
  });
}

function todayTitle() {
  const d = new Date();
  return `${d.getMonth() + 1}月${d.getDate()}日 周${WEEK_CN[d.getDay()]}`;
}

// ---------- 登录 / 注册 ----------
function showLogin() {
  $("#nav").classList.add("hidden");
  const main = $("#main");
  $("#page-title").textContent = "每日打卡";
  $("#header-sub").textContent = "";
  main.innerHTML = "";

  const wrap = el("div", { class: "auth-wrap" });
  wrap.appendChild(el("div", { class: "auth-logo" },
    el("div", { class: "logo-circle" }, "✓"),
    el("h1", {}, "每日打卡"),
    el("p", {}, "记录锻炼、吃药、血压，养成好习惯")
  ));

  const tabs = el("div", { class: "auth-tabs" },
    el("button", { class: "auth-tab active", dataset: { mode: "login" } }, "登录"),
    el("button", { class: "auth-tab", dataset: { mode: "register" } }, "注册")
  );
  const form = el("div");
  wrap.append(tabs, form);

  function renderForm() {
    const isRegister = state.authMode === "register";
    form.innerHTML = "";
    $$(".auth-tab", tabs).forEach((t) => t.classList.toggle("active", t.dataset.mode === state.authMode));
    const f = el("div");
    f.appendChild(el("label", { class: "field" }, el("span", {}, "用户名"),
      el("input", { type: "text", id: "auth-username", placeholder: "你的昵称", autocomplete: "username" })));
    f.appendChild(el("label", { class: "field" }, el("span", {}, "密码"),
      el("input", { type: "password", id: "auth-password", placeholder: "至少 6 位", autocomplete: isRegister ? "new-password" : "current-password" })));
    if (isRegister) {
      f.appendChild(el("label", { class: "field" }, el("span", {}, "邀请码"),
        el("input", { type: "text", id: "auth-invite", placeholder: "找管理员获取邀请码" })));
    }
    const btn = el("button", { class: "btn block", id: "auth-submit" }, isRegister ? "注册并开始" : "登录");
    f.appendChild(btn);
    form.appendChild(f);
    if (!isRegister) {
      form.appendChild(el("p", { class: "hint", style: "margin-top:10px" }, "首次使用：直接注册的第一个账号即为管理员"));
    }
    btn.addEventListener("click", submitAuth);
  }

  tabs.addEventListener("click", (e) => {
    const tab = e.target.closest(".auth-tab");
    if (!tab) return;
    state.authMode = tab.dataset.mode;
    renderForm();
  });

  main.appendChild(wrap);
  renderForm();
}

async function submitAuth() {
  const username = $("#auth-username").value.trim();
  const password = $("#auth-password").value;
  const inviteCode = $("#auth-invite") ? $("#auth-invite").value.trim() : undefined;
  if (!username || !password) return toast("请填写用户名和密码");
  try {
    if (state.authMode === "register") {
      await api("/api/auth/register", { method: "POST", body: { username, password, invite_code: inviteCode || null } });
    }
    await api("/api/auth/login", { method: "POST", body: { username, password } });
    state.user = await api("/api/auth/me");
    location.hash = "#today";
    onHashChange();
  } catch (e) {
    toast(e.message);
  }
}

// ---------- 今日打卡 ----------
async function loadToday() {
  const data = await api(`/api/today?date=${state.todayDate}`);
  state.todayData = data;
  const main = $("#main");
  main.innerHTML = "";

  const d = parseFmt(state.todayDate);
  const today = parseFmt(fmtDate(new Date()));
  const nav = el("div", { class: "date-nav" },
    el("button", { class: "date-prev" }, "‹"),
    el("div", { class: "date-label" }, `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 周${WEEK_CN[d.getDay()]}`),
    el("button", { class: "date-next" }, "›")
  );
  if (state.todayDate === fmtDate(new Date())) {
    nav.appendChild(el("button", { class: "btn small secondary", id: "back-today", style: "margin-left:auto" }, "今天"));
    $(".date-label", nav).style.marginLeft = "auto";
  }
  main.appendChild(nav);

  const card = el("div", { class: "card" });
  const habits = data.habits;
  if (habits.length === 0) {
    card.appendChild(el("div", { class: "empty-tip" },
      "还没有习惯，去「习惯」页添加吧"));
  } else {
    habits.forEach((h) => {
      const row = el("div", { class: "habit-row" + (h.checkin && h.checkin.done ? " done" : "") });
      row.appendChild(el("span", { class: "habit-dot", style: `background:${h.color}` }));
      const info = el("div", { class: "habit-info" },
        el("div", { class: "habit-name" }, h.name,
          h.reminder_enabled && h.reminder_time ? el("span", { class: "badge" }, `⏰ ${h.reminder_time}`) : null),
        el("div", { class: "habit-meta" },
          h.value_label ? `单位：${h.value_label}` : "无单位",
          h.checkin && h.checkin.value ? ` · 已记：${h.checkin.value}` : "")
      );
      const check = el("button", { class: "habit-check", title: "完成" }, "✓");
      const expand = el("button", { class: "habit-expand" }, "▾");
      row.append(info, check, expand);

      const detail = el("div", { class: "habit-detail" },
        el("label", { class: "field" },
          el("span", {}, h.value_label ? `数值（${h.value_label}）` : "数值（可选）"),
          el("input", { type: "text", class: "h-value", value: (h.checkin && h.checkin.value) || "", placeholder: h.value_label || "如 30" })),
        el("label", { class: "field" },
          el("span", {}, "备注（可选）"),
          el("input", { type: "text", class: "h-note", value: (h.checkin && h.checkin.note) || "", placeholder: "如：晨跑 5 公里" })),
        el("button", { class: "btn small block", dataset: { save: h.id } }, "保存")
      );
      row.appendChild(detail);

      check.addEventListener("click", async () => {
        const cur = h.checkin || { done: false, value: "", note: "" };
        await api(`/api/checkins/${h.id}?date=${state.todayDate}`, {
          method: "PUT",
          body: { done: !cur.done, value: cur.value || null, note: cur.note || null },
        });
        await loadToday();
      });
      expand.addEventListener("click", () => row.classList.toggle("open"));
      $$(".h-value, .h-note", detail).forEach((input) => input.addEventListener("change", () => {
        const cur = h.checkin || { done: false };
        h.checkin = { ...cur, value: $(".h-value", detail).value.trim(), note: $(".h-note", detail).value.trim() };
      }));
      $$("[data-save]", detail).forEach((b) => b.addEventListener("click", async () => {
        const cur = h.checkin || { done: false };
        await api(`/api/checkins/${h.id}?date=${state.todayDate}`, {
          method: "PUT",
          body: {
            done: cur.done,
            value: $(".h-value", detail).value.trim() || null,
            note: $(".h-note", detail).value.trim() || null,
          },
        });
        toast("已保存");
        await loadToday();
      }));
      card.appendChild(row);
    });
  }
  main.appendChild(card);

  $(".date-prev", main).addEventListener("click", () => { state.todayDate = fmtDate(addDays(d, -1)); loadToday(); });
  const nextBtn = $(".date-next", main);
  nextBtn.addEventListener("click", () => { state.todayDate = fmtDate(addDays(d, 1)); loadToday(); });
  if (state.todayDate >= fmtDate(new Date())) nextBtn.disabled = true;
  const backToday = $("#back-today", main);
  if (backToday) backToday.addEventListener("click", () => { state.todayDate = fmtDate(new Date()); loadToday(); });
}

// ---------- 日历与统计 ----------
async function loadCalendar() {
  const now = new Date();
  if (state.calYear === null) { state.calYear = now.getFullYear(); state.calMonth = now.getMonth() + 1; }
  const data = await api(`/api/stats/month?year=${state.calYear}&month=${state.calMonth}`);
  state.monthStats = data;
  const main = $("#main");
  main.innerHTML = "";

  const header = el("div", { class: "cal-header" },
    el("button", { class: "cal-prev" }, "‹"),
    el("div", { class: "cal-title" }, `${data.year}年${data.month}月`),
    el("button", { class: "cal-next" }, "›")
  );
  main.appendChild(header);

  const card = el("div", { class: "card" });
  const weekRow = el("div", { class: "cal-week" });
  WEEK_CN.forEach((w) => weekRow.appendChild(el("span", {}, w)));
  card.appendChild(weekRow);

  const first = new Date(data.year, data.month - 1, 1);
  const daysInMonth = new Date(data.year, data.month, 0).getDate();
  const totalHabits = data.habits.length;
  const grid = el("div", { class: "cal-grid" });
  const offset = first.getDay();
  const todayStr = fmtDate(new Date());

  for (let i = 0; i < offset; i++) grid.appendChild(el("div", { class: "cal-day other" }));
  for (let day = 1; day <= daysInMonth; day++) {
    const dateStr = `${data.year}-${String(data.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    let done = 0;
    data.habits.forEach((h) => { if (h.days[dateStr]) done++; });
    let cls = "cal-day none";
    if (totalHabits > 0) {
      if (done === totalHabits) cls = "cal-day full";
      else if (done > 0) cls = "cal-day partial";
    }
    if (dateStr === todayStr) cls += " today";
    if (dateStr > todayStr) cls += " dim";
    const cell = el("div", { class: cls, dataset: { date: dateStr } }, String(day));
    if (dateStr <= todayStr) {
      cell.addEventListener("click", () => {
        state.todayDate = dateStr;
        location.hash = "#today";
      });
    }
    grid.appendChild(cell);
  }
  card.appendChild(grid);
  main.appendChild(card);

  if (totalHabits === 0) {
    main.appendChild(el("div", { class: "card" }, el("div", { class: "empty-tip" }, "还没有习惯")));
  } else {
    const statCard = el("div", { class: "card" });
    statCard.appendChild(el("div", { class: "card-title" }, "本月统计"));
    data.habits.forEach((h) => {
      const pct = Math.round(h.rate * 100);
      const row = el("div", { class: "stat-row" },
        el("span", { class: "habit-dot", style: `background:${h.color}` }),
        el("div", { class: "stat-info" },
          el("div", { class: "stat-name" }, h.name),
          el("div", { class: "stat-meta" },
            `完成 ${h.done_count}/${h.elapsed_days} 天 · 达成率 ${pct}% · 连续 ${h.streak} 天`),
          el("div", { class: "progress" }, el("div", { style: `width:${pct}%` }))
        )
      );
      statCard.appendChild(row);
    });
    main.appendChild(statCard);
  }

  $(".cal-prev", main).addEventListener("click", () => {
    state.calMonth -= 1;
    if (state.calMonth === 0) { state.calMonth = 12; state.calYear -= 1; }
    loadCalendar();
  });
  $(".cal-next", main).addEventListener("click", () => {
    state.calMonth += 1;
    if (state.calMonth === 13) { state.calMonth = 1; state.calYear += 1; }
    loadCalendar();
  });
}

// ---------- 血压 ----------
async function loadBp() {
  const [data, mdata] = await Promise.all([
    api(`/api/bp?days=${state.bp.days}`),
    api(`/api/metrics?days=${state.bp.days}`),
  ]);
  state.bp.records = data.records;
  state.bp.avgSys = data.avg_systolic;
  state.bp.avgDia = data.avg_diastolic;
  state.bp.count = data.count;
  state.metrics.records = mdata.records;
  state.metrics.latest = mdata.latest;
  state.editingBpId = null;
  state.metrics.editingId = null;
  renderBp();
}

function bpCategory(sys, dia) {
  if (sys >= 140 || dia >= 90) return { tag: "hypertension", label: "偏高" };
  if (sys >= 120 || dia >= 80) return { tag: "high-normal", label: "正常高值" };
  return { tag: "normal", label: "正常" };
}

function renderBp() {
  const main = $("#main");
  main.innerHTML = "";

  // 录入/编辑表单
  const formCard = el("div", { class: "card" });
  const formTitle = el("div", { class: "card-title" }, state.editingBpId ? "编辑血压记录" : "记录血压");
  formCard.appendChild(formTitle);
  const editing = state.editingBpId
    ? state.bp.records.find((r) => r.id === state.editingBpId)
    : null;
  const now = new Date();
  const defDate = editing ? editing.date : fmtDate(now);
  const defTime = editing ? editing.time : `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;

  const grid = el("div", { class: "bp-form-grid" });
  grid.append(
    el("label", { class: "field" }, el("span", {}, "日期"), el("input", { type: "date", id: "bp-date", value: defDate })),
    el("label", { class: "field" }, el("span", {}, "时间"), el("input", { type: "time", id: "bp-time", value: defTime })),
    el("label", { class: "field" }, el("span", {}, "收缩压（高压）"), el("input", { type: "number", id: "bp-sys", value: editing ? editing.systolic : "", placeholder: "如 120", min: 50, max: 300 })),
    el("label", { class: "field" }, el("span", {}, "舒张压（低压）"), el("input", { type: "number", id: "bp-dia", value: editing ? editing.diastolic : "", placeholder: "如 80", min: 30, max: 200 })),
    el("label", { class: "field" }, el("span", {}, "脉搏（可选）"), el("input", { type: "number", id: "bp-pulse", value: editing && editing.pulse ? editing.pulse : "", placeholder: "如 72", min: 20, max: 250 })),
    el("label", { class: "field full" }, el("span", {}, "备注（可选）"), el("input", { type: "text", id: "bp-note", value: editing ? (editing.note || "") : "", placeholder: "如：晨起空腹测量" }))
  );
  const saveBtn = el("button", { class: "btn block", id: "bp-save" }, editing ? "更新记录" : "保存记录");
  grid.appendChild(saveBtn);
  if (editing) {
    const cancelBtn = el("button", { class: "btn secondary block", id: "bp-cancel", style: "margin-top:8px" }, "取消编辑");
    grid.appendChild(cancelBtn);
  }
  formCard.appendChild(grid);
  main.appendChild(formCard);

  // 趋势图
  const chartCard = el("div", { class: "card" });
  chartCard.appendChild(el("div", { class: "card-title" }, "血压趋势"));
  const tabs = el("div", { class: "range-tabs" });
  [30, 90, 180].forEach((d) => {
    const b = el("button", { class: d === state.bp.days ? "active" : "", dataset: { days: d } }, `${d}天`);
    tabs.appendChild(b);
  });
  chartCard.appendChild(tabs);
  chartCard.appendChild(el("div", { class: "bp-chart" }));
  const chartBox = $(".bp-chart", chartCard);
  chartBox.innerHTML = renderBpChartSvg(state.bp.records, state.bp.days);
  chartCard.appendChild(el("div", { class: "bp-legend" },
    el("span", {}, el("i", { style: "background:#e5484d" }), "收缩压"),
    el("span", {}, el("i", { style: "background:#3b82f6" }), "舒张压"),
    el("span", {}, "虚线为 140/90 参考线")
  ));
  const avg = el("div", { class: "bp-avg" },
    el("div", { class: "avg-item" }, el("div", { class: "num" }, state.bp.avgSys ?? "—"), el("div", { class: "label" }, `平均收缩压（${state.bp.days}天）`)),
    el("div", { class: "avg-item" }, el("div", { class: "num" }, state.bp.avgDia ?? "—"), el("div", { class: "label" }, `平均舒张压（${state.bp.days}天）`)),
    el("div", { class: "avg-item" }, el("div", { class: "num" }, state.bp.count), el("div", { class: "label" }, "记录次数"))
  );
  chartCard.appendChild(avg);
  main.appendChild(chartCard);

  // 记录列表
  const listCard = el("div", { class: "card" });
  listCard.appendChild(el("div", { class: "card-title" }, `最近记录（${state.bp.days}天，共 ${state.bp.count} 条）`));
  if (state.bp.records.length === 0) {
    listCard.appendChild(el("div", { class: "empty-tip" }, "还没有血压记录，先在上面记一条吧"));
  } else {
    [...state.bp.records].reverse().forEach((r) => {
      const cat = bpCategory(r.systolic, r.diastolic);
      const item = el("div", { class: "bp-item" },
        el("div", { class: "bp-values" },
          el("div", { class: "nums" },
            `${r.systolic}/${r.diastolic}`,
            r.pulse ? el("small", {}, `  ♥${r.pulse}`) : null,
            el("span", { class: `bp-tag ${cat.tag}`, style: "margin-left:6px" }, cat.label)
          ),
          el("div", { class: "when" }, `${r.date} ${r.time}${r.note ? " · " + r.note : ""}`)
        ),
        el("div", { class: "bp-actions" },
          el("button", { class: "btn small secondary", dataset: { edit: r.id } }, "改"),
          el("button", { class: "btn small danger", dataset: { del: r.id } }, "删")
        )
      );
      listCard.appendChild(item);
    });
  }
  main.appendChild(listCard);

  // ---- 体重/指标 ----
  const metricCard = el("div", { class: "card" });
  metricCard.appendChild(el("div", { class: "card-title" }, state.metrics.editingId ? "编辑指标" : "体重 / 指标"));
  const mEdit = state.metrics.editingId
    ? state.metrics.records.find((r) => r.id === state.metrics.editingId)
    : null;
  const mgrid = el("div", { class: "bp-form-grid" });
  mgrid.append(
    el("label", { class: "field" }, el("span", {}, "名称"), el("input", { type: "text", id: "m-name", list: "metric-names", value: mEdit ? mEdit.name : "", placeholder: "体重 / 体脂率 / 血糖" })),
    el("label", { class: "field" }, el("span", {}, "数值"), el("input", { type: "number", id: "m-value", step: "0.1", value: mEdit ? mEdit.value : "", placeholder: "如 65.5", min: 0, max: 1000 })),
    el("label", { class: "field" }, el("span", {}, "单位"), el("input", { type: "text", id: "m-unit", value: mEdit ? (mEdit.unit || "") : "", placeholder: "kg / % / mmol/L" })),
    el("label", { class: "field" }, el("span", {}, "日期"), el("input", { type: "date", id: "m-date", value: mEdit ? mEdit.date : fmtDate(new Date()) })),
    el("label", { class: "field full" }, el("span", {}, "备注（可选）"), el("input", { type: "text", id: "m-note", value: mEdit ? (mEdit.note || "") : "", placeholder: "如：晨起空腹" }))
  );
  const mSave = el("button", { class: "btn block", id: "m-save" }, mEdit ? "更新指标" : "保存指标");
  mgrid.appendChild(mSave);
  if (mEdit) mgrid.appendChild(el("button", { class: "btn secondary block", id: "m-cancel", style: "margin-top:8px" }, "取消编辑"));
  metricCard.appendChild(mgrid);
  metricCard.appendChild(el("datalist", { id: "metric-names" },
    el("option", { value: "体重" }), el("option", { value: "体脂率" }), el("option", { value: "血糖" }), el("option", { value: "腰围" })));
  const mList = el("div");
  metricCard.appendChild(mList);
  if (state.metrics.records.length === 0) {
    mList.appendChild(el("div", { class: "empty-tip" }, "还没有指标记录，先记一条体重吧"));
  } else {
    [...state.metrics.records].reverse().forEach((r) => {
      mList.appendChild(el("div", { class: "bp-item" },
        el("div", { class: "bp-values" },
          el("div", { class: "nums" }, `${r.name} ${r.value}${r.unit ? " " + r.unit : ""}`),
          el("div", { class: "when" }, `${r.date}${r.note ? " · " + r.note : ""}`)),
        el("div", { class: "bp-actions" },
          el("button", { class: "btn small secondary", dataset: { medit: r.id } }, "改"),
          el("button", { class: "btn small danger", dataset: { mdel: r.id } }, "删"))));
    });
  }
  main.appendChild(metricCard);

  mSave.addEventListener("click", saveMetric);
  const mCancel = $("#m-cancel", main);
  if (mCancel) mCancel.addEventListener("click", () => { state.metrics.editingId = null; renderBp(); });
  $$("[data-medit]", mList).forEach((b) => b.addEventListener("click", () => {
    state.metrics.editingId = Number(b.dataset.medit);
    renderBp();
  }));
  $$("[data-mdel]", mList).forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("删除这条指标记录？")) return;
    await api(`/api/metrics/${b.dataset.mdel}`, { method: "DELETE" });
    toast("已删除");
    await loadBp();
  }));

  // 事件
  tabs.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    state.bp.days = Number(b.dataset.days);
    loadBp();
  });
  saveBtn.addEventListener("click", saveBp);
  const cancel = $("#bp-cancel", main);
  if (cancel) cancel.addEventListener("click", () => { state.editingBpId = null; renderBp(); });
  $$("[data-edit]", listCard).forEach((b) => b.addEventListener("click", () => {
    state.editingBpId = Number(b.dataset.edit);
    renderBp();
  }));
  $$("[data-del]", listCard).forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("删除这条血压记录？")) return;
    await api(`/api/bp/${b.dataset.del}`, { method: "DELETE" });
    toast("已删除");
    await loadBp();
  }));
}

async function saveBp() {
  const body = {
    date: $("#bp-date").value,
    time: $("#bp-time").value,
    systolic: Number($("#bp-sys").value),
    diastolic: Number($("#bp-dia").value),
    pulse: $("#bp-pulse").value ? Number($("#bp-pulse").value) : null,
    note: $("#bp-note").value.trim() || null,
  };
  if (!body.date || !body.systolic || !body.diastolic) return toast("请填写日期和血压值");
  try {
    if (state.editingBpId) {
      await api(`/api/bp/${state.editingBpId}`, { method: "PATCH", body });
      toast("已更新");
    } else {
      await api("/api/bp", { method: "POST", body });
      toast("已记录");
    }
    await loadBp();
  } catch (e) {
    toast(e.message);
  }
}

async function saveMetric() {
  const body = {
    name: $("#m-name").value.trim(),
    value: Number($("#m-value").value),
    unit: $("#m-unit").value.trim() || null,
    date: $("#m-date").value,
    note: $("#m-note").value.trim() || null,
  };
  if (!body.name || body.value === undefined || body.value === "" || Number.isNaN(body.value)) return toast("请填写名称和数值");
  try {
    if (state.metrics.editingId) {
      await api(`/api/metrics/${state.metrics.editingId}`, { method: "PATCH", body });
      toast("已更新");
    } else {
      await api("/api/metrics", { method: "POST", body });
      toast("已记录");
    }
    await loadBp();
  } catch (e) {
    toast(e.message);
  }
}

// ---------- AI 分析 ----------
function mdToHtml(text) {
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const lines = esc(text).split("\n");
  let html = "", inList = false;
  const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^###\s+/.test(line)) { closeList(); html += `<h4>${line.replace(/^###\s+/, "")}</h4>`; }
    else if (/^##\s+/.test(line)) { closeList(); html += `<h3>${line.replace(/^##\s+/, "")}</h3>`; }
    else if (/^[-*]\s+/.test(line)) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${line.replace(/^[-*]\s+/, "")}</li>`; }
    else if (line.trim() === "") { closeList(); }
    else { closeList(); html += `<p>${line}</p>`; }
  }
  closeList();
  return html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

async function loadAnalysis() {
  const list = await api("/api/analysis");
  state.analysis.list = list;
  renderAnalysis();
}

function renderAnalysis() {
  const main = $("#main");
  main.innerHTML = "";
  const card = el("div", { class: "card" });
  card.appendChild(el("div", { class: "card-title" }, "AI 健康分析"));
  card.appendChild(el("p", { class: "stat-meta", style: "margin-bottom:10px" },
    "基于你最近的打卡、血压和体重数据，由大模型生成个性化建议（仅供参考，不替代医生诊断）。"));
  const tabs = el("div", { class: "range-tabs" });
  [7, 30, 90].forEach((d) => tabs.appendChild(el("button", {
    class: d === state.analysis.days ? "active" : "", dataset: { adays: d },
  }, `近${d}天`)));
  card.appendChild(tabs);
  const genBtn = el("button", { class: "btn block", id: "gen-analysis" },
    state.analysis.loading ? "分析中，请稍候…" : "生成我的健康分析");
  if (state.analysis.loading) genBtn.disabled = true;
  card.appendChild(genBtn);
  main.appendChild(card);

  if (state.analysis.current) {
    const cur = state.analysis.current;
    const curCard = el("div", { class: "card" });
    curCard.appendChild(el("div", { class: "card-title" },
      `分析结果（${cur.period_start} ~ ${cur.period_end}）`,
      el("button", { class: "btn small secondary", id: "del-current", style: "margin-left:auto" }, "删除")));
    const contentBox = el("div", { class: "analysis-content" });
    contentBox.innerHTML = mdToHtml(cur.content);
    curCard.appendChild(contentBox);
    main.appendChild(curCard);
    $("#del-current", curCard).addEventListener("click", async () => {
      if (!confirm("删除这条分析记录？")) return;
      await api(`/api/analysis/${cur.id}`, { method: "DELETE" });
      state.analysis.current = null;
      await loadAnalysis();
    });
  } else if (!state.analysis.loading && state.analysis.list.length === 0) {
    main.appendChild(el("div", { class: "card" }, el("div", { class: "empty-tip" }, "还没有分析记录，点上面按钮生成一份吧")));
  }

  if (state.analysis.list.length > 0) {
    const hist = el("div", { class: "card" });
    hist.appendChild(el("div", { class: "card-title" }, "历史分析"));
    state.analysis.list.forEach((a) => {
      const row = el("div", { class: "bp-item" },
        el("div", { class: "bp-values" },
          el("div", { class: "when" }, `${a.period_start} ~ ${a.period_end} · ${a.created_at}`)),
        el("div", { class: "bp-actions" },
          el("button", { class: "btn small secondary", dataset: { aview: a.id } }, "查看"),
          el("button", { class: "btn small danger", dataset: { adel: a.id } }, "删")));
      hist.appendChild(row);
    });
    main.appendChild(hist);
    $$("[data-aview]", hist).forEach((b) => b.addEventListener("click", async () => {
      state.analysis.current = await api(`/api/analysis/${b.dataset.aview}`);
      renderAnalysis();
    }));
    $$("[data-adel]", hist).forEach((b) => b.addEventListener("click", async () => {
      if (!confirm("删除这条分析记录？")) return;
      await api(`/api/analysis/${b.dataset.adel}`, { method: "DELETE" });
      await loadAnalysis();
    }));
  }

  tabs.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    state.analysis.days = Number(b.dataset.adays);
    renderAnalysis();
  });
  genBtn.addEventListener("click", async () => {
    state.analysis.loading = true;
    renderAnalysis();
    try {
      const result = await api(`/api/analysis?days=${state.analysis.days}`, { method: "POST" });
      state.analysis.current = result;
      state.analysis.loading = false;
      state.analysis.list = await api("/api/analysis");
      renderAnalysis();
      toast("分析完成");
    } catch (e) {
      state.analysis.loading = false;
      renderAnalysis();
      toast(e.message);
    }
  });
}

// 血压趋势 SVG 图
function renderBpChartSvg(records, days) {
  if (records.length < 2) {
    return el("div", { class: "empty-tip" }, "至少记录 2 次后显示趋势图").outerHTML;
  }
  const W = 800, H = 360, PL = 46, PR = 14, PT = 24, PB = 40;
  const plotW = W - PL - PR, plotH = H - PT - PB;
  let minVal = Math.min(...records.map((r) => r.diastolic));
  let maxVal = Math.max(...records.map((r) => r.systolic));
  minVal = Math.min(minVal, 90);
  maxVal = Math.max(maxVal, 140);
  minVal = Math.max(50, Math.floor((minVal - 10) / 10) * 10);
  maxVal = Math.min(200, Math.ceil((maxVal + 10) / 10) * 10);

  const x = (i) => PL + (records.length === 1 ? plotW / 2 : (i / (records.length - 1)) * plotW);
  const y = (v) => PT + plotH - ((v - minVal) / (maxVal - minVal)) * plotH;

  const parts = [];
  // 网格线
  for (let v = minVal; v <= maxVal; v += 20) {
    const yy = y(v);
    parts.push(`<line x1="${PL}" y1="${yy}" x2="${W - PR}" y2="${yy}" stroke="#eef1f7" stroke-width="1"/>`);
    parts.push(`<text x="${PL - 6}" y="${yy + 4}" text-anchor="end" font-size="11" fill="#8a93a6">${v}</text>`);
  }
  // 参考线 140 / 90
  parts.push(`<line x1="${PL}" y1="${y(140)}" x2="${W - PR}" y2="${y(140)}" stroke="#e5484d" stroke-width="1.2" stroke-dasharray="6 4" opacity="0.6"/>`);
  parts.push(`<text x="${PL + 4}" y="${y(140) - 5}" font-size="11" fill="#e5484d">140</text>`);
  parts.push(`<line x1="${PL}" y1="${y(90)}" x2="${W - PR}" y2="${y(90)}" stroke="#e5484d" stroke-width="1.2" stroke-dasharray="6 4" opacity="0.6"/>`);
  parts.push(`<text x="${PL + 4}" y="${y(90) - 5}" font-size="11" fill="#e5484d">90</text>`);

  const sysPts = records.map((r, i) => `${x(i)},${y(r.systolic)}`).join(" ");
  const diaPts = records.map((r, i) => `${x(i)},${y(r.diastolic)}`).join(" ");
  parts.push(`<polyline points="${sysPts}" fill="none" stroke="#e5484d" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>`);
  parts.push(`<polyline points="${diaPts}" fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>`);

  // 数据点 + 日期标签
  const step = Math.max(1, Math.ceil(records.length / 8));
  records.forEach((r, i) => {
    parts.push(`<circle cx="${x(i)}" cy="${y(r.systolic)}" r="3" fill="#e5484d"/>`);
    parts.push(`<circle cx="${x(i)}" cy="${y(r.diastolic)}" r="3" fill="#3b82f6"/>`);
    if (i % step === 0 || i === records.length - 1) {
      const label = r.date.slice(5);
      parts.push(`<text x="${x(i)}" y="${H - 14}" text-anchor="middle" font-size="11" fill="#8a93a6">${label}</text>`);
    }
  });

  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="血压趋势图">${parts.join("")}</svg>`;
}

// ---------- 习惯管理 ----------
const COLOR_PRESETS = ["#4f8cff", "#22b573", "#ff6b6b", "#f5a623", "#9b59b6", "#1abc9c", "#e84393", "#636e72"];

async function loadHabits() {
  const habits = await api("/api/habits");
  state.habits = habits;
  const main = $("#main");
  main.innerHTML = "";

  const formCard = el("div", { class: "card" });
  const editing = state.editingHabitId ? habits.find((h) => h.id === state.editingHabitId) : null;
  formCard.appendChild(el("div", { class: "card-title" }, editing ? "编辑习惯" : "添加习惯"));
  const f = el("div");
  f.appendChild(el("label", { class: "field" }, el("span", {}, "名称"), el("input", { type: "text", id: "h-name", value: editing ? editing.name : "", placeholder: "如：锻炼 / 吃药 / 阅读" })));
  f.appendChild(el("label", { class: "field" }, el("span", {}, "数值单位（可选）"), el("input", { type: "text", id: "h-unit", value: editing ? (editing.value_label || "") : "", placeholder: "如：分钟 / 次 / 粒" })));
  const swRow = el("div", { class: "switch-row" },
    el("div", {}, el("div", { style: "font-weight:600" }, "定时提醒"), el("div", { style: "font-size:12px;color:var(--muted)" }, "到点且未完成时推送通知")),
    el("div", { class: "switch" + (editing && editing.reminder_enabled ? " on" : ""), id: "h-reminder-sw" })
  );
  f.appendChild(swRow);
  f.appendChild(el("label", { class: "field", style: "margin-top:8px" }, el("span", {}, "提醒时间"), el("input", { type: "time", id: "h-time", value: editing && editing.reminder_time ? editing.reminder_time : "20:00" })));
  const picker = el("div", { class: "color-picker" });
  const chosenColor = editing ? editing.color : COLOR_PRESETS[0];
  COLOR_PRESETS.forEach((c) => {
    picker.appendChild(el("div", {
      class: "swatch" + (c === chosenColor ? " active" : ""),
      style: `background:${c}`,
      dataset: { color: c },
    }));
  });
  f.appendChild(el("label", { class: "field" }, el("span", {}, "颜色"), picker));
  const saveBtn = el("button", { class: "btn block", id: "h-save" }, editing ? "保存修改" : "添加习惯");
  f.appendChild(saveBtn);
  if (editing) {
    f.appendChild(el("button", { class: "btn secondary block", id: "h-cancel", style: "margin-top:8px" }, "取消编辑"));
  }
  formCard.appendChild(f);
  main.appendChild(formCard);

  const listCard = el("div", { class: "card" });
  listCard.appendChild(el("div", { class: "card-title" }, `我的习惯（${habits.length}）`));
  if (habits.length === 0) {
    listCard.appendChild(el("div", { class: "empty-tip" }, "还没有习惯"));
  } else {
    habits.forEach((h) => {
      const row = el("div", { class: "habit-row" },
        el("span", { class: "habit-dot", style: `background:${h.color}` }),
        el("div", { class: "habit-info" },
          el("div", { class: "habit-name" }, h.name,
            h.reminder_enabled && h.reminder_time ? el("span", { class: "badge" }, `⏰ ${h.reminder_time}`) : null),
          el("div", { class: "habit-meta" }, h.value_label ? `单位：${h.value_label}` : "无单位")
        ),
        el("div", { class: "bp-actions" },
          el("button", { class: "btn small secondary", dataset: { edit: h.id } }, "改"),
          el("button", { class: "btn small danger", dataset: { del: h.id } }, "删")
        )
      );
      listCard.appendChild(row);
    });
  }
  main.appendChild(listCard);

  // 事件
  let selectedColor = chosenColor;
  $$(".swatch", picker).forEach((s) => s.addEventListener("click", () => {
    $$(".swatch", picker).forEach((x) => x.classList.remove("active"));
    s.classList.add("active");
    selectedColor = s.dataset.color;
  }));
  $("#h-reminder-sw", f).addEventListener("click", () => {
    const sw = $("#h-reminder-sw", f);
    sw.classList.toggle("on");
    const t = $("#h-time", f);
    t.disabled = !sw.classList.contains("on");
  });
  const remSw = $("#h-reminder-sw", f);
  $("#h-time", f).disabled = !remSw.classList.contains("on");

  saveBtn.addEventListener("click", async () => {
    const name = $("#h-name", f).value.trim();
    if (!name) return toast("请填写习惯名称");
    const body = {
      name,
      value_label: $("#h-unit", f).value.trim() || null,
      reminder_enabled: remSw.classList.contains("on"),
      reminder_time: remSw.classList.contains("on") ? $("#h-time", f).value : null,
      color: selectedColor,
    };
    try {
      if (state.editingHabitId) {
        await api(`/api/habits/${state.editingHabitId}`, { method: "PATCH", body });
        toast("已更新");
      } else {
        await api("/api/habits", { method: "POST", body });
        toast("已添加");
      }
      state.editingHabitId = null;
      await loadHabits();
    } catch (e) {
      toast(e.message);
    }
  });
  const cancel = $("#h-cancel", f);
  if (cancel) cancel.addEventListener("click", () => { state.editingHabitId = null; loadHabits(); });
  $$("[data-edit]", listCard).forEach((b) => b.addEventListener("click", () => {
    state.editingHabitId = Number(b.dataset.edit);
    loadHabits();
  }));
  $$("[data-del]", listCard).forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("删除这个习惯？历史打卡记录也会一并删除。")) return;
    await api(`/api/habits/${b.dataset.del}`, { method: "DELETE" });
    toast("已删除");
    await loadHabits();
  }));
}

// ---------- 我的 / 设置 ----------
async function loadSettings() {
  const main = $("#main");
  main.innerHTML = "";

  const userCard = el("div", { class: "card" });
  const avatar = el("div", { class: "user-avatar" }, state.user.username.slice(0, 1).toUpperCase());
  userCard.appendChild(el("div", { class: "user-card" },
    avatar,
    el("div", {},
      el("div", { class: "user-name" }, state.user.username),
      el("div", { class: "user-role" }, state.user.is_admin ? "管理员" : "成员")
    )
  ));
  main.appendChild(userCard);

  // 通知
  const notifCard = el("div", { class: "card" });
  notifCard.appendChild(el("div", { class: "card-title" }, "提醒通知"));
  const notifStatus = el("div", { class: "stat-meta", style: "margin-bottom:10px" }, "检测通知权限…");
  notifCard.appendChild(notifStatus);
  notifCard.appendChild(el("div", { class: "row" },
    el("button", { class: "btn", id: "push-on" }, "开启推送"),
    el("button", { class: "btn secondary", id: "push-off" }, "关闭推送")
  ));
  main.appendChild(notifCard);

  const logoutBtn = el("button", { class: "btn danger block", id: "logout" }, "退出登录");
  main.appendChild(el("div", { class: "card" }, logoutBtn));

  // 管理后台
  if (state.user.is_admin) {
    const adminCard = el("div", { class: "card" });
    adminCard.appendChild(el("div", { class: "card-title" }, "管理后台"));

    const memberTitle = el("div", { class: "stat-meta", style: "font-weight:700;color:var(--text);margin:6px 0" }, "成员管理");
    const memberList = el("div");
    adminCard.append(memberTitle, memberList);

    const inviteTitle = el("div", { class: "stat-meta", style: "font-weight:700;color:var(--text);margin:14px 0 6px" }, "邀请码");
    const inviteCreate = el("div", { class: "row", style: "margin-bottom:8px" },
      el("select", { id: "invite-expiry" },
        el("option", { value: "30" }, "30 天有效"),
        el("option", { value: "90" }, "90 天有效"),
        el("option", { value: "365" }, "365 天有效"),
        el("option", { value: "0" }, "长期有效")
      ),
      el("button", { class: "btn", id: "invite-create" }, "生成邀请码")
    );
    const inviteList = el("div");
    adminCard.append(inviteTitle, inviteCreate, inviteList);
    main.appendChild(adminCard);

    const loadMembers = async () => {
      const members = await api("/api/admin/members");
      memberList.innerHTML = "";
      members.forEach((m) => {
        const row = el("div", { class: "member-row" },
          el("div", { class: "user-avatar", style: "width:36px;height:36px;font-size:16px" }, m.username.slice(0, 1).toUpperCase()),
          el("div", { class: "member-info" },
            el("div", { class: "stat-name" }, m.username, m.is_admin ? el("span", { class: "badge" }, "管理员") : null),
            el("div", { class: "stat-meta" }, m.is_disabled ? "已停用" : "正常")
          ),
          m.is_admin ? null : el("button", {
            class: "btn small " + (m.is_disabled ? "secondary" : "danger"),
            dataset: { toggle: m.id, disabled: m.is_disabled },
          }, m.is_disabled ? "启用" : "停用")
        );
        memberList.appendChild(row);
      });
    };
    const loadInvites = async () => {
      const codes = await api("/api/admin/invite-codes");
      inviteList.innerHTML = "";
      if (codes.length === 0) {
        inviteList.appendChild(el("div", { class: "stat-meta" }, "还没有生成过邀请码"));
      } else {
        codes.forEach((c) => {
          inviteList.appendChild(el("div", { class: "invite-row" },
            el("code", {}, c.code),
            el("div", { class: "stat-meta", style: "flex:1" },
              c.used_by ? `已使用` : (c.expires_at ? `有效期至 ${c.expires_at}` : "长期有效"))
          ));
        });
      }
    };
    await Promise.all([loadMembers(), loadInvites()]);

    memberList.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-toggle]");
      if (!b) return;
      await api(`/api/admin/members/${b.dataset.toggle}`, {
        method: "PATCH",
        body: { is_disabled: b.dataset.disabled === "true" ? false : true },
      });
      await loadMembers();
    });
    $("#invite-create").addEventListener("click", async () => {
      const expiry = Number($("#invite-expiry").value);
      const res = await api("/api/admin/invite-codes", { method: "POST", body: { expires_days: expiry || null } });
      toast(`邀请码：${res.code}`);
      await loadInvites();
    });
  }

  // 通知状态
  const updateNotifStatus = async () => {
    try {
      if (!("serviceWorker" in navigator)) {
        notifStatus.textContent = "此浏览器不支持推送通知（需要 HTTPS）。";
        return;
      }
      const reg = await navigator.serviceWorker.getRegistration();
      const sub = reg ? await reg.pushManager.getSubscription() : null;
      const perm = Notification.permission;
      notifStatus.textContent = sub
        ? `已开启：可收到 ${sub.endpoint ? "设备推送" : ""}（浏览器通知权限：${perm}）`
        : `未开启推送（浏览器通知权限：${perm}）。开启后，设置了提醒时间的习惯会在到点未完成时提醒你。`;
    } catch (e) {
      notifStatus.textContent = "无法获取通知状态：" + e.message;
    }
  };
  updateNotifStatus();

  $("#push-on").addEventListener("click", async () => {
    try {
      await enablePush();
      toast("推送已开启");
      await updateNotifStatus();
    } catch (e) {
      toast(e.message);
    }
  });
  $("#push-off").addEventListener("click", async () => {
    try {
      await disablePush();
      toast("推送已关闭");
      await updateNotifStatus();
    } catch (e) {
      toast(e.message);
    }
  });
  logoutBtn.addEventListener("click", async () => {
    await api("/api/auth/logout", { method: "POST" });
    state.user = null;
    showLogin();
  });
}

// ---------- 推送 ----------
function urlBase64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const base64Url = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64Url);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

function bufToBase64Url(buf) {
  let binary = "";
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function enablePush() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    throw new Error("此浏览器不支持推送通知，需要 HTTPS 且使用较新的浏览器");
  }
  const reg = await navigator.serviceWorker.register("/sw.js");
  const perm = await Notification.requestPermission();
  if (perm !== "granted") throw new Error("未获得通知权限，请在浏览器设置中允许本站通知");
  const keyRes = await api("/api/push/vapid-public-key");
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(keyRes.public_key),
  });
  await api("/api/push/subscribe", {
    method: "POST",
    body: {
      endpoint: sub.endpoint,
      p256dh: bufToBase64Url(sub.getKey("p256dh")),
      auth: bufToBase64Url(sub.getKey("auth")),
    },
  });
}

async function disablePush() {
  if (!("serviceWorker" in navigator)) return;
  const reg = await navigator.serviceWorker.getRegistration();
  if (reg) {
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      await api(`/api/push/subscribe?endpoint=${encodeURIComponent(sub.endpoint)}`, { method: "DELETE" });
      await sub.unsubscribe();
    }
  }
}

document.addEventListener("DOMContentLoaded", init);
