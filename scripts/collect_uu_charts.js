/* Run as an Edge DevTools Snippet on your normally logged-in UU item page. */
(function UUChartCollector() {
  "use strict";
  const VERSION = "uu-browser-charts-1.1";
  const LEGACY_SOURCE_SHA256 = "64186f5cdcffcdb7695c05639a578591916fc3fd23eb9954b9922243f9d5bf5e";
  const ENDPOINT = "https://pc-api.youpin898.com/api/youpin/price/trend/data";
  const LIMIT = 2 * 1024 * 1024;
  const KEYS = ["filterTemplateTypeNames", "templateId", "orderType", "day", "templateTypeName", "customizeDay"];
  const objectKeys = (v, keys) => v && !Array.isArray(v) && typeof v === "object" && Object.keys(v).every(k => keys.includes(k));
  function integer(v) {
    if (!((typeof v === "number" && Number.isSafeInteger(v)) || (typeof v === "string" && /^\d+$/.test(v)))) throw Error("invalid_integer");
    const n = Number(v);
    if (!Number.isSafeInteger(n)) throw Error("invalid_integer");
    return n;
  }
  function body(v) {
    if (!objectKeys(v, KEYS) || KEYS.some(k => !(k in v)) || v.customizeDay !== false || v.templateTypeName !== "" || !Array.isArray(v.filterTemplateTypeNames) || v.filterTemplateTypeNames.length) throw Error("unsupported_filter");
    const day = integer(v.day), template = integer(v.templateId), order = integer(v.orderType);
    if (day < 1 || day > 366 || template < 1 || ![1, 11].includes(order)) throw Error("unsupported_context");
    return {filterTemplateTypeNames: [], templateId: String(template), orderType: String(order), day: String(day), templateTypeName: "", customizeDay: false};
  }
  function tasks(seed, halfDay) {
    seed = body(seed);
    halfDay = integer(halfDay);
    if (halfDay <= 90 || halfDay > 366) throw Error("half_year_not_confirmed");
    return [["7d", 7, 1], ["7d", 7, 11], ["15d", 15, 11], ["30d", 30, 1], ["30d", 30, 11], ["90d", 90, 1], ["half_year", halfDay, 1]].map(([window, day, order]) => ({id: `${window}_${order}`, window, request_body: {...seed, day: String(day), orderType: String(order)}, status: "pending", attempts: 0}));
  }
  class ChartFailure extends Error {
    constructor(stage, reason, applicationCode) {
      super(reason); this.stage = stage; this.reason = reason;
      if (Number.isSafeInteger(applicationCode)) this.application_code = applicationCode;
    }
  }
  function diagnostic(error, stage) {
    const result = error instanceof ChartFailure ? {stage: error.stage, reason: error.reason} : {stage, reason: `${stage}_failed`};
    if (error instanceof ChartFailure && error.application_code !== undefined) result.application_code = error.application_code;
    return result;
  }
  function responseText(text, requestBody) {
    if (new TextEncoder().encode(text).length > LIMIT) throw new ChartFailure("response_read", "response_too_large");
    if (/eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}/.test(text)) throw new ChartFailure("schema", "credential_like_response");
    let p;
    try { p = JSON.parse(text); } catch (_) { throw new ChartFailure("json", "invalid_json"); }
    const b = body(requestBody);
    if (!objectKeys(p, ["code", "msg", "timestamp", "data"])) throw new ChartFailure("schema", "response_schema_error");
    if (p.code !== 0) throw new ChartFailure("application", "application_error", typeof p.code === "number" ? p.code : undefined);
    if (integer(p.timestamp) < 1e12 || integer(p.timestamp) >= 1e13 || !objectKeys(p.data, ["tradeDataList", "tradePriceList", "blockNum"]) || !Array.isArray(p.data.tradeDataList)) throw new ChartFailure("schema", "response_schema_error");
    if (!p.data.tradeDataList.length) throw new ChartFailure("schema", "empty_series");
    for (const point of p.data.tradeDataList) {
      if (!objectKeys(point, ["time", "price", "localDate", "proportion", "sourceType"]) || integer(point.time) < 1e12 || integer(point.time) >= 1e13) throw Error("invalid_point");
      if (point.price !== null) {
        if (!["number", "string"].includes(typeof point.price) || String(point.price).trim() === "" || !Number.isFinite(Number(point.price)) || Number(point.price) < 0) throw Error("invalid_value");
        if (b.orderType === "11" && !Number.isSafeInteger(Number(point.price))) throw Error("fractional_quantity");
      }
    }
    return p;
  }
  function migrateLegacy(candidate, halfDay) {
    if (candidate.format !== "uu-chart-batch-1.0" || candidate.collector_version !== "uu-browser-charts-1.0" || !Array.isArray(candidate.tasks) || candidate.tasks.length !== 8 || candidate.half_year_day !== Number(halfDay)) throw Error("invalid_legacy_batch");
    const oldIds = new Set(["7d_1", "7d_11", "15d_1", "15d_11", "90d_1", "90d_11", "half_year_1", "half_year_11"]);
    for (const task of candidate.tasks) {
      const b = body(task.request_body);
      if (!oldIds.delete(task.id) || b.templateId !== candidate.template_id || task.window !== task.id.slice(0, task.id.lastIndexOf("_")) || Number(b.day) !== ({"7d": 7, "15d": 15, "90d": 90, "half_year": Number(halfDay)})[task.window] || String(b.orderType) !== task.id.slice(task.id.lastIndexOf("_") + 1)) throw Error("invalid_legacy_task");
      if (task.status === "success") responseText(task.response_text, b);
    }
    const planned = tasks(candidate.tasks[0].request_body, halfDay);
    for (let i = 0; i < planned.length; i++) {
      const old = candidate.tasks.find(t => t.id === planned[i].id);
      if (old) planned[i] = old;
    }
    const excluded = candidate.tasks.filter(t => !planned.some(n => n.id === t.id)).map(t => ({id: t.id, status: t.status, attempts: t.attempts}));
    return {...candidate, format: "uu-chart-batch-1.1", collector_version: VERSION, tasks: planned, parent_batch: {run_id: candidate.run_id, collector_version: candidate.collector_version, excluded_unsupported_tasks: excluded}};
  }
  // Offline tests import only these pure helpers. No browser or network is started.
  if (typeof module !== "undefined" && module.exports && typeof window === "undefined") {
    module.exports = {VERSION, ENDPOINT, body, tasks, responseText, diagnostic, migrateLegacy};
    return;
  }
  if (location.origin !== "https://www.youpin898.com") throw Error("Please run on the normal https://www.youpin898.com page.");
  if (document.getElementById("uu-chart-collector")) return;
  const source = `(${UUChartCollector.toString()})();\n`;
  const STOP_KEY = "cs_youoweme_uu_chart_stop_v1";
  const nativeFetch = window.fetch;
  const proto = XMLHttpRequest.prototype;
  const originals = {open: proto.open, send: proto.send, setRequestHeader: proto.setRequestHeader};
  const xhrState = new WeakMap();
  let seed = null, pack = null, running = false, ended = false, controller = null, loaded = null;
  let blocked = true, storageOK = true;
  try { blocked = Boolean(localStorage.getItem(STOP_KEY)); } catch (_) { storageOK = false; }
  const panel = document.createElement("section");
  panel.id = "uu-chart-collector";
  panel.style.cssText = "position:fixed;right:16px;top:70px;z-index:2147483647;width:340px;background:white;color:#222;padding:16px;border:2px solid #1266cc;border-radius:8px;font:14px/1.6 sans-serif;box-shadow:0 4px 20px #888";
  const heading = document.createElement("strong"); heading.textContent = "UU 历史价格与在售数量采集";
  const status = document.createElement("p");
  const label = document.createElement("input"); label.placeholder = "商品完整名称、磨损、普通/特殊版本"; label.style.width = "95%";
  const start = document.createElement("button"); start.textContent = "确认当前窗口为半年，开始本轮采集"; start.disabled = true;
  const recover = document.createElement("button"); recover.textContent = "已人工确认访问恢复"; recover.disabled = true;
  const upload = document.createElement("input"); upload.type = "file"; upload.accept = ".json"; upload.title = "可选：载入此前中断批次，只继续未尝试任务";
  const download = document.createElement("button"); download.textContent = "下载已保存结果"; download.disabled = true;
  const stop = document.createElement("button"); stop.textContent = "停止并下载";
  for (const element of [heading, status, label, start, recover, upload, download, stop]) { panel.append(element, document.createElement("br")); }
  document.body.append(panel);
  const say = text => { status.textContent = text; };
  say(storageOK ? "请在原网页选择【半年】图表。等待它正常返回，再确认开始；不复制请求头。" : "浏览器本地存储不可用，无法持久保存访问停止状态，禁止采集。");
  function saveFile() {
    if (!pack) return;
    pack.updated_at = new Date().toISOString();
    const url = URL.createObjectURL(new Blob([JSON.stringify(pack, null, 2)], {type: "application/json"}));
    const a = document.createElement("a"); a.href = url; a.download = `${pack.run_id}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
  function detach() {
    if (window.fetch === wrappedFetch) window.fetch = nativeFetch;
    if (proto.open === wrappedOpen) proto.open = originals.open;
    if (proto.send === wrappedSend) proto.send = originals.send;
    if (proto.setRequestHeader === wrappedHeader) proto.setRequestHeader = originals.setRequestHeader;
    seed = null;
  }
  function finish(reason, accessStop = false) {
    if (ended) return;
    ended = true; running = false; start.disabled = true; recover.disabled = true;
    if (controller) controller.abort();
    if (accessStop) { try { localStorage.setItem(STOP_KEY, JSON.stringify({reason, at: new Date().toISOString()})); } catch (_) {} }
    if (pack) { pack.status = reason; download.disabled = false; }
    detach(); say(`${reason}。已停止；结果包含成功、失败和待采任务。`); saveFile();
  }
  const matches = url => { try { return new URL(url, location.href).href === ENDPOINT; } catch (_) { return false; } };
  async function captured(request, requestBody, response, text) {
    if (ended || running) return;
    if (response.status !== 200) {
      if ([401, 403, 429].includes(response.status)) finish(`http_${response.status}`, true);
      return;
    }
    try {
      const b = body(requestBody); responseText(text, b);
      if (Number(b.day) <= 90) { say(`已看到模板 ${b.templateId} 的 ${b.day} 天请求。请在网页切换【半年】以确定实际参数。`); return; }
      if (b.orderType !== "1") { say("请选择成交价格的半年图表作为正常请求依据。"); return; }
      seed = {request, body: b, text, received_at: new Date().toISOString()};
      recover.disabled = !blocked || !storageOK;
      start.disabled = blocked || !storageOK;
      say(`已捕获模板 ${b.templateId}，day=${b.day}。请确认网页选中成交价格的半年，并填写准确商品规格。${blocked ? "上次访问曾停止，正常成功响应后仍需人工确认恢复。" : "准备采集7组：价格7/30/90/半年，数量7/15/30天。"}`);
    } catch (_) { finish("application_or_schema_error", true); }
  }
  function wrappedFetch(input, init) {
    let request = null;
    try { const candidate = new Request(input instanceof Request ? input.clone() : input, init); if (candidate.method === "POST" && matches(candidate.url)) request = candidate; } catch (_) {}
    const result = nativeFetch.apply(this, arguments);
    if (request) {
      Promise.all([request.clone().text(), result.then(async r => ({status: r.status, text: r.status === 200 ? await r.clone().text() : ""}))])
        .then(([b, r]) => captured(request, JSON.parse(b), r, r.text)).catch(() => { if (!running && !ended) say("正常页面请求未能读取；未发送额外请求。请检查页面状态。"); });
    }
    return result;
  }
  function wrappedOpen(method, url) {
    xhrState.set(this, {enabled: String(method).toUpperCase() === "POST" && matches(url), headers: {}});
    return originals.open.apply(this, arguments);
  }
  function wrappedHeader(name, value) {
    const state = xhrState.get(this); if (state && state.enabled) state.headers[name] = value;
    return originals.setRequestHeader.apply(this, arguments);
  }
  function wrappedSend(value) {
    const state = xhrState.get(this);
    if (state && state.enabled && !ended && !running) {
      try {
        const b = JSON.parse(value);
        const request = new Request(ENDPOINT, {method: "POST", headers: state.headers, body: value, credentials: this.withCredentials ? "include" : "same-origin"});
        this.addEventListener("load", () => {
          let text = "";
          try { text = this.responseType === "json" ? JSON.stringify(this.response) : this.responseText; } catch (_) {}
          captured(request, b, {status: this.status}, text);
        }, {once: true});
      } catch (_) {}
    }
    return originals.send.apply(this, arguments);
  }
  window.fetch = wrappedFetch; proto.open = wrappedOpen; proto.send = wrappedSend; proto.setRequestHeader = wrappedHeader;
  recover.onclick = () => {
    if (!seed || !storageOK || running || ended) return;
    localStorage.removeItem(STOP_KEY); blocked = false; recover.disabled = true; start.disabled = false;
    say("人工恢复确认已记录。请确认半年与商品规格后开始新一轮。");
  };
  upload.onchange = async () => {
    if (running || ended || !upload.files[0]) return;
    try {
      if (upload.files[0].size > 20 * LIMIT) throw Error();
      const candidate = JSON.parse(await upload.files[0].text());
      if (!objectKeys(candidate, ["format", "collector_version", "collector_source", "run_id", "created_at", "updated_at", "template_id", "item_label", "half_year_day", "identity_verified", "status", "tasks", "parent_batch"]) || !Array.isArray(candidate.tasks)) throw Error();
      if (candidate.format === "uu-chart-batch-1.0" && candidate.collector_version === "uu-browser-charts-1.0") {
        const normalized = candidate.collector_source.replace(/\r\n/g, "\n");
        const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(normalized))), b => b.toString(16).padStart(2, "0")).join("");
        if (hash !== LEGACY_SOURCE_SHA256) throw Error();
        loaded = migrateLegacy(candidate, candidate.half_year_day);
        loaded.collector_source = source; loaded.run_id = `uu_charts_${new Date().toISOString().replace(/[:.]/g, "-")}_${candidate.template_id}`; loaded.created_at = new Date().toISOString();
      } else {
        if (candidate.format !== "uu-chart-batch-1.1" || candidate.collector_version !== VERSION || candidate.collector_source.replace(/\r\n/g, "\n") !== source.replace(/\r\n/g, "\n")) throw Error();
        loaded = candidate;
      }
      label.value = candidate.item_label; say("已载入并使用正确的7组窗口。成功任务保留；旧版不支持的请求排除并记入来源。请切换同商品半年价格，再人工确认开始。");
    } catch (_) { loaded = null; say("载入失败；请使用本工具下载的批次文件。没有发送请求。"); }
  };
  download.onclick = saveFile;
  stop.onclick = () => finish("user_interrupted");
  start.onclick = async () => {
    if (!seed || blocked || !storageOK || ended || running || !label.value.trim()) { say("请填写商品规格，并在正常成功的半年图表响应后开始。"); return; }
    const capturedSeed = seed;
    let planned;
    try {
      planned = tasks(capturedSeed.body, capturedSeed.body.day);
      if (loaded) {
        if (loaded.template_id !== capturedSeed.body.templateId || loaded.half_year_day !== Number(capturedSeed.body.day) || loaded.tasks.length !== planned.length) throw Error();
        for (const task of planned) {
          const old = loaded.tasks.find(r => r.id === task.id);
          if (!objectKeys(old, ["id", "window", "request_body", "status", "attempts", "origin", "started_at", "received_at", "http_status", "response_text", "error", "diagnostic"]) || old.window !== task.window || JSON.stringify(body(old.request_body)) !== JSON.stringify(task.request_body) || !["pending", "success", "failed", "interrupted_unknown"].includes(old.status) || ![0, 1].includes(old.attempts) || (old.status === "pending") !== (old.attempts === 0)) throw Error();
          if (old.status === "success") responseText(old.response_text, task.request_body);
        }
        planned = loaded.tasks;
      }
    } catch (_) { say("批次与当前模板/窗口或已保存任务不一致，未开始。"); return; }
    pack = loaded || {format: "uu-chart-batch-1.1", collector_version: VERSION, collector_source: source, run_id: `uu_charts_${new Date().toISOString().replace(/[:.]/g, "-")}_${capturedSeed.body.templateId}`, created_at: new Date().toISOString(), template_id: capturedSeed.body.templateId, item_label: label.value.trim(), half_year_day: Number(capturedSeed.body.day), identity_verified: false, status: "running", tasks: planned};
    pack.status = "running";
    if (!loaded) {
      const first = pack.tasks.find(t => t.window === "half_year" && t.request_body.orderType === capturedSeed.body.orderType);
      Object.assign(first, {status: "success", attempts: 1, origin: "user_triggered_page_request", started_at: capturedSeed.received_at, received_at: capturedSeed.received_at, http_status: 200, response_text: capturedSeed.text});
    }
    running = true; start.disabled = true; recover.disabled = true; upload.disabled = true; label.disabled = true; download.disabled = false;
    const deadline = Date.now() + 180000;
    try {
      for (const task of pack.tasks) {
        if (ended) break;
        if (task.status !== "pending") continue;
        await new Promise(resolve => setTimeout(resolve, 5000));
        if (ended) break;
        if (Date.now() >= deadline) { finish("deadline_reached"); break; }
        Object.assign(task, {status: "interrupted_unknown", attempts: 1, origin: "explicit_user_batch", started_at: new Date().toISOString()});
        controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), Math.min(30000, deadline - Date.now()));
        let r, text, stage = "request";
        try {
          r = await nativeFetch.call(window, new Request(capturedSeed.request.clone(), {method: "POST", body: JSON.stringify(task.request_body), redirect: "error", cache: "no-store", signal: controller.signal}));
          task.http_status = r.status;
          if (!r.ok || r.status !== 200) throw new ChartFailure("http", `http_${r.status}`);
          stage = "response_read";
          const reader = r.body.getReader(), chunks = []; let length = 0;
          while (true) {
            const next = await reader.read(); if (next.done) break;
            length += next.value.byteLength;
            if (length > LIMIT) { await reader.cancel(); throw new ChartFailure("response_read", "response_too_large"); }
            chunks.push(next.value);
          }
          const bytes = new Uint8Array(length); let offset = 0;
          for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
          stage = "utf8_decode";
          text = new TextDecoder("utf-8", {fatal: true}).decode(bytes);
          stage = "schema";
          responseText(text, task.request_body);
        } catch (error) {
          clearTimeout(timer);
          if (ended) break;
          task.status = "failed"; task.diagnostic = diagnostic(error, stage); task.error = task.diagnostic.reason;
          finish(task.error, true); break;
        } finally { clearTimeout(timer); controller = null; }
        if (ended) break;
        Object.assign(task, {status: "success", received_at: new Date().toISOString(), response_text: text});
        say(`已保存 ${pack.tasks.filter(t => t.status === "success").length}/${pack.tasks.length} 组。串行采集，无自动重试。`);
      }
      if (!ended) finish(pack.tasks.every(t => t.status === "success") ? "completed" : "partial_no_automatic_retry");
    } catch (_) { finish("internal_error", true); }
  };
})();
