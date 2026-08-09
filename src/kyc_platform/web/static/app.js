"use strict";

const state = {
  cases: [],
  currentCase: null,
  caseFilter: "open",
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Actor-ID": "workbench-analyst-01",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const payload = await response.json();
      message = typeof payload.detail === "string" ? payload.detail : message;
    } catch {
      // The status code remains the useful fallback.
    }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function toast(message, kind = "success") {
  const item = document.createElement("div");
  item.className = `toast ${kind === "error" ? "error" : ""}`;
  item.textContent = message;
  $("#toastRegion").append(item);
  window.setTimeout(() => item.remove(), 4200);
}

function formatDate(value, includeTime = false) {
  if (!value) return "—";
  const date = new Date(value);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(includeTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

function categoryLabel(category) {
  return { low: "低风险", medium: "中风险", high: "高风险", critical: "严重风险" }[category] || category;
}

function statusLabel(status) {
  return { open: "待复核", escalated: "已升级", closed: "已完成" }[status] || status;
}

function decisionLabel(decision) {
  return {
    false_positive: "已排除误报",
    confirmed_match: "已确认命中",
    escalate: "已升级调查",
  }[decision] || "查看证据";
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function showView(name) {
  $$(".view").forEach((view) => view.classList.toggle("is-visible", view.id === `view-${name}`));
  $$(".nav-item[data-view]").forEach((item) => {
    const active = item.dataset.view === name;
    item.classList.toggle("is-active", active);
    active ? item.setAttribute("aria-current", "page") : item.removeAttribute("aria-current");
  });
  const view = $(`#view-${name}`);
  $("#currentViewLabel").textContent = view?.dataset.title || "工作台";
  $("#sidebar").classList.remove("is-open");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function loadDashboard() {
  const summary = await api("/api/v1/dashboard");
  $("#customerCount").textContent = summary.customer_count;
  $("#pepCount").textContent = summary.pep_count;
  $("#activeCaseCount").textContent = summary.active_case_count;
  $("#openCaseCount").textContent = summary.open_case_count;
  $("#auditCount").textContent = summary.audit_event_count;
  $("#escalatedCaseCount").textContent = Math.max(0, summary.active_case_count - summary.open_case_count);
  $("#navCaseCount").textContent = summary.active_case_count;
  $("#pulseCustomers").textContent = `${summary.customer_count} 个主体`;
  $("#pulseCases").textContent = `${summary.active_case_count} 件待处理`;
  $("#pulsePolicy").textContent = `策略 ${summary.risk_policy_version}`;
  $("#pulseScreening").textContent = summary.sanctions_source;
  $("#modeLabel").textContent = summary.operating_mode === "offline" ? "离线演示模式" : "在线名单模式";
  $("#datasetLabel").textContent = `${summary.sanctions_source} · ${summary.sanctions_version}`;
}

function caseRowTemplate(item) {
  return `
    <article class="case-row" data-status="${escapeHtml(item.status)}">
      <div class="case-party">
        <strong>${escapeHtml(item.customer.legal_name)}</strong>
        <span>${escapeHtml(item.customer.record_id)} · ${escapeHtml(item.customer.registered_country || "国家未知")}</span>
      </div>
      <div class="case-match">
        <strong>${escapeHtml(item.matched_name)}</strong>
        <span>${escapeHtml(item.source)} · ${escapeHtml((item.evidence.programs || []).join(" / ") || "未标注项目")}</span>
      </div>
      <div class="case-score"><strong>${Math.round(item.score * 100)}%</strong><span>名称相似度</span></div>
      <button class="case-open-button" type="button" data-open-case="${escapeHtml(item.id)}">${item.status === "closed" ? decisionLabel(item.decision) : "开始判断"}</button>
    </article>`;
}

function renderCases(container, cases) {
  if (!cases.length) {
    container.innerHTML = `<div class="empty-state"><span>◇</span><strong>当前队列为空</strong><p>客户评估产生的名单匹配会自动进入这里。</p></div>`;
    return;
  }
  container.innerHTML = cases.map(caseRowTemplate).join("");
}

async function loadCases() {
  const query = state.caseFilter ? `?status=${encodeURIComponent(state.caseFilter)}` : "";
  state.cases = await api(`/api/v1/cases${query}`);
  renderCases($("#reviewCaseList"), state.cases);
  const openCases = await api("/api/v1/cases?status=open&limit=3");
  renderCases($("#overviewCases"), openCases);
}

function customerRowTemplate(customer) {
  const flags = [customer.is_pep ? '<span class="status-tag escalated">PEP</span>' : "", customer.entity_type === "individual" ? '<span class="tag">个人</span>' : '<span class="tag">机构</span>'].join(" ");
  return `
    <tr>
      <td><strong>${escapeHtml(customer.legal_name)}</strong><small>${escapeHtml(customer.record_id)}</small></td>
      <td class="mono-cell">${escapeHtml(customer.registered_country || "—")}</td>
      <td class="mono-cell">${escapeHtml(customer.registration_number || "—")}</td>
      <td class="mono-cell">${escapeHtml(customer.lei || "—")}</td>
      <td>${flags}</td>
      <td><button class="risk-button" type="button" data-assess-customer="${escapeHtml(customer.id)}">筛查并评分</button></td>
    </tr>`;
}

async function loadCustomers() {
  const params = new URLSearchParams({ limit: "200" });
  const query = $("#customerSearch").value.trim();
  const country = $("#countryFilter").value.trim();
  const pep = $("#pepFilter").value;
  if (query) params.set("query", query);
  if (country) params.set("country", country.toUpperCase());
  if (pep) params.set("is_pep", pep);
  const customers = await api(`/api/v1/customers?${params}`);
  $("#customerTableBody").innerHTML = customers.map(customerRowTemplate).join("");
  $("#customerEmpty").hidden = customers.length !== 0;
  $(".table-wrap").hidden = customers.length === 0;
}

async function assessCustomer(customerId, button) {
  button.disabled = true;
  const oldText = button.textContent;
  button.textContent = "正在评估…";
  try {
    const result = await api(`/api/v1/customers/${encodeURIComponent(customerId)}/assessment`, { method: "POST" });
    const assessment = result.assessment;
    toast(`评估完成：${categoryLabel(assessment.category)} ${assessment.score}分，新增 ${result.cases_created} 件复核案件`);
    await Promise.all([loadDashboard(), loadCases()]);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = oldText;
  }
}

function formPayload(form) {
  const raw = Object.fromEntries(new FormData(form).entries());
  const payload = {};
  Object.entries(raw).forEach(([key, value]) => {
    if (value !== "") payload[key] = value;
  });
  payload.is_pep = form.elements.is_pep.checked;
  if (payload.registered_country) payload.registered_country = payload.registered_country.toUpperCase();
  if (payload.aum_usd_millions) payload.aum_usd_millions = Number(payload.aum_usd_millions);
  payload.source = "business-workbench";
  return payload;
}

async function createCustomer(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submit = $("button[type='submit']", form);
  submit.disabled = true;
  try {
    const customer = await api("/api/v1/customers", {
      method: "POST",
      body: JSON.stringify(formPayload(form)),
    });
    const result = await api(`/api/v1/customers/${encodeURIComponent(customer.id)}/assessment`, { method: "POST" });
    $("#customerDialog").close();
    form.reset();
    toast(`客户已保存并完成初筛：${categoryLabel(result.assessment.category)} ${result.assessment.score}分`);
    await Promise.all([loadCustomers(), loadDashboard(), loadCases()]);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    submit.disabled = false;
  }
}

function renderQuickResult(result) {
  const container = $("#quickScreenResult");
  const assessment = result.assessment;
  const topMatch = result.screening.matches[0];
  container.classList.toggle("has-alert", Boolean(topMatch));
  container.innerHTML = `
    <div class="result-top"><div><strong>${categoryLabel(assessment.category)}</strong><p>策略 ${escapeHtml(assessment.policy_version)}</p></div><b>${assessment.score}</b></div>
    <p>${topMatch ? `名单候选：${escapeHtml(topMatch.matched_name)}，相似度 ${Math.round(topMatch.score * 100)}%` : "未发现达到人工复核阈值的名单候选。"}</p>
    <div class="factor-tags">${assessment.factors.map((factor) => `<span class="tag">${escapeHtml(factor.code)} +${escapeHtml(factor.contribution)}</span>`).join("")}</div>`;
  container.hidden = false;
}

async function quickScreen(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = $("button[type='submit']", form);
  const data = new FormData(form);
  const customer = {
    legal_name: data.get("legal_name"),
    source: "business-workbench-quick-check",
    is_pep: form.elements.is_pep.checked,
  };
  const country = String(data.get("country") || "").trim();
  if (country) customer.registered_country = country.toUpperCase();
  button.disabled = true;
  button.textContent = "筛查中…";
  try {
    const result = await api("/api/v1/risk-assessments", {
      method: "POST",
      body: JSON.stringify({ customer }),
    });
    renderQuickResult(result);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "立即筛查";
  }
}

function openCase(caseId) {
  const item = state.cases.find((candidate) => candidate.id === caseId);
  if (!item) {
    toast("案件数据已更新，请刷新后重试", "error");
    return;
  }
  state.currentCase = item;
  const programs = (item.evidence.programs || []).map((program) => `<span class="tag">${escapeHtml(program)}</span>`).join("");
  $("#caseEvidence").innerHTML = `
    <div><span>客户主体</span><strong>${escapeHtml(item.customer.legal_name)}</strong><div class="program-tags">${item.customer.is_pep ? '<span class="status-tag escalated">PEP</span>' : ""}</div></div>
    <div><span>名单候选</span><strong>${escapeHtml(item.matched_name)}</strong><div class="program-tags">${programs || '<span class="tag">未标注项目</span>'}</div></div>
    <div class="evidence-score"><span>相似度</span><strong>${Math.round(item.score * 100)}%</strong></div>`;
  const actions = $(".decision-actions", $("#caseDialog"));
  actions.hidden = item.status === "closed";
  const notes = item.evidence.review?.notes || "";
  $("textarea[name='notes']", $("#caseDecisionForm")).value = notes;
  $("#caseDialog").showModal();
}

async function decideCase(event) {
  event.preventDefault();
  if (!state.currentCase || !event.submitter?.value) return;
  const form = event.currentTarget;
  const decision = event.submitter.value;
  const notes = new FormData(form).get("notes");
  $$(".decision-actions button", form).forEach((button) => (button.disabled = true));
  try {
    await api(`/api/v1/cases/${encodeURIComponent(state.currentCase.id)}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, notes }),
    });
    $("#caseDialog").close();
    toast(`复核结论已记录：${decisionLabel(decision)}`);
    await Promise.all([loadDashboard(), loadCases()]);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    $$(".decision-actions button", form).forEach((button) => (button.disabled = false));
  }
}

const artifactLabels = {
  "kyc-compliance-report.xlsx": "Excel 报告",
  "kyc-compliance-summary.pdf": "PDF 摘要",
  "customers.csv": "客户明细",
  "duplicate-candidates.csv": "重复候选",
  "screening-results.jsonl": "筛查证据",
  "risk-assessments.jsonl": "风险证据",
};

function runCardTemplate(run) {
  const summary = run.summary || {};
  const artifacts = run.artifacts
    .filter((artifact) => artifactLabels[artifact.path])
    .map((artifact) => `<a href="/artifacts/${encodeURIComponent(run.run_id)}/${encodeURIComponent(artifact.path)}" target="_blank" rel="noreferrer">${artifactLabels[artifact.path]}</a>`)
    .join("");
  return `
    <article class="run-card">
      <div class="run-card-head"><div><strong>${run.offline ? "离线验证批次" : "在线名单批次"}</strong><code>${escapeHtml(run.run_id)}</code></div><time>${formatDate(run.completed_at, true)}</time></div>
      <div class="run-metrics">
        <div><span>处理记录</span><strong>${summary.record_count ?? run.record_count}</strong></div>
        <div><span>筛查复核</span><strong>${summary.screening_review_count ?? 0}</strong></div>
        <div><span>潜在命中</span><strong>${summary.potential_match_count ?? 0}</strong></div>
        <div><span>重复候选</span><strong>${summary.duplicate_candidate_count ?? 0}</strong></div>
      </div>
      <div class="artifact-links">${artifacts}</div>
    </article>`;
}

async function loadRuns() {
  const runs = await api("/api/v1/pipeline-runs?limit=20");
  const container = $("#runList");
  if (!runs.length) {
    container.innerHTML = '<div class="empty-state"><span>⇅</span><strong>还没有报告包</strong><p>运行第一个批次后，可在这里打开 Excel 和 PDF。</p></div>';
    return;
  }
  container.innerHTML = runs.map(runCardTemplate).join("");
}

async function loadBenchmarkInfo() {
  const info = await api("/api/v1/evaluations/benchmark/info");
  $("#benchmarkName").textContent = info.name;
  $("#benchmarkVersion").textContent = `v${info.version} · ${info.sha256.slice(0, 12)}`;
  $("#benchmarkCustomers").textContent = info.customer_count;
  $("#benchmarkScreeningLabels").textContent = `${info.screening_label_count} / ${info.screening_positive_count} 正例`;
  $("#benchmarkRiskLabels").textContent = info.risk_label_count;
  $("#benchmarkDuplicateLabels").textContent = info.duplicate_record_count;
}

const evaluationArtifactLabels = {
  "screening-records.csv": "逐条筛查结果",
  "threshold-sweep.csv": "阈值扫描",
  "risk-records.csv": "风险分类结果",
  "duplicate-errors.csv": "去重错误",
};

function renderEvaluation(result) {
  $("#evaluationEmpty").hidden = true;
  $("#evaluationResult").hidden = false;
  $("#evaluationF1").textContent = formatPercent(result.screening.alerts.f1);
  $("#evaluationPrecision").textContent = formatPercent(result.screening.alerts.precision);
  $("#evaluationRecall").textContent = formatPercent(result.screening.alerts.recall);
  $("#evaluationEntityRecall").textContent = formatPercent(result.screening.entity_recall_at_k);
  $("#evaluationRiskAccuracy").textContent = formatPercent(result.risk.accuracy);
  $("#evaluationDuplicateF1").textContent = formatPercent(result.duplicates.f1);
  $("#evaluationTimestamp").textContent = `${formatDate(result.evaluated_at, true)} · 阈值 ${result.review_threshold}`;
  $("#evaluationRunId").textContent = result.run_id.slice(0, 8);
  $("#evaluationFalsePositive").textContent = result.screening.alerts.false_positive;
  $("#evaluationFalseNegative").textContent = result.screening.alerts.false_negative;
  $("#duplicateFalsePositive").textContent = result.duplicates.false_positive;
  $("#duplicateFalseNegative").textContent = result.duplicates.false_negative;

  const bestF1 = Math.max(...result.threshold_sweep.map((metric) => metric.f1));
  $("#thresholdTableBody").innerHTML = result.threshold_sweep
    .map((metric) => `
      <tr class="${metric.f1 === bestF1 ? "threshold-best" : ""}">
        <td class="mono-cell">${metric.threshold.toFixed(2)}</td>
        <td>${formatPercent(metric.precision)}</td>
        <td>${formatPercent(metric.recall)}</td>
        <td><strong>${formatPercent(metric.f1)}</strong></td>
        <td>${metric.false_positive}</td>
        <td>${metric.false_negative}</td>
      </tr>`)
    .join("");
  $("#evaluationArtifacts").innerHTML = result.artifacts
    .map((artifact) => `<a href="/artifacts/evaluations/${encodeURIComponent(result.run_id)}/${encodeURIComponent(artifact.path)}" target="_blank" rel="noreferrer">${evaluationArtifactLabels[artifact.path] || escapeHtml(artifact.path)}</a>`)
    .join("");
}

async function loadEvaluations() {
  const runs = await api("/api/v1/evaluations/benchmark/runs?limit=1");
  if (runs.length) renderEvaluation(runs[0]);
}

async function runEvaluation() {
  const button = $("#runEvaluation");
  button.disabled = true;
  $("#evaluationProgress").hidden = false;
  try {
    const result = await api("/api/v1/evaluations/benchmark/runs", { method: "POST" });
    renderEvaluation(result);
    toast(`评估完成：筛查 F1 ${formatPercent(result.screening.alerts.f1)}`);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    button.disabled = false;
    $("#evaluationProgress").hidden = true;
  }
}

async function runPipeline(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submit = $("button[type='submit']", form);
  const values = Object.fromEntries(new FormData(form).entries());
  const payload = {
    record_count: Number(values.record_count),
    duplicate_rate: Number(values.duplicate_rate),
    sanctions_injection_rate: Number(values.sanctions_injection_rate),
    seed: Number(values.seed),
    offline: true,
  };
  submit.disabled = true;
  $("#pipelineProgress").hidden = false;
  try {
    const result = await api("/api/v1/pipeline-runs", { method: "POST", body: JSON.stringify(payload) });
    toast(`批次已完成：处理 ${result.summary.record_count} 条记录`);
    await loadRuns();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    submit.disabled = false;
    $("#pipelineProgress").hidden = true;
  }
}

function bindEvents() {
  $$(".nav-item[data-view]").forEach((item) => item.addEventListener("click", () => showView(item.dataset.view)));
  $$('[data-view-target]').forEach((item) => item.addEventListener("click", () => showView(item.dataset.viewTarget)));
  $$('[data-open-customer]').forEach((item) => item.addEventListener("click", () => $("#customerDialog").showModal()));
  $$('[data-action="refresh"]').forEach((item) => item.addEventListener("click", async () => {
    try {
      await Promise.all([loadDashboard(), loadCustomers(), loadCases(), loadRuns(), loadBenchmarkInfo(), loadEvaluations()]);
      toast("工作台数据已刷新");
    } catch (error) {
      toast(error.message, "error");
    }
  }));
  $$('[data-close-dialog]').forEach((item) => item.addEventListener("click", () => item.closest("dialog").close()));
  $("#menuButton").addEventListener("click", () => $("#sidebar").classList.toggle("is-open"));
  $("#customerForm").addEventListener("submit", createCustomer);
  $("#quickScreenForm").addEventListener("submit", quickScreen);
  $("#caseDecisionForm").addEventListener("submit", decideCase);
  $("#pipelineForm").addEventListener("submit", runPipeline);
  $("#customerFilterButton").addEventListener("click", () => loadCustomers().catch((error) => toast(error.message, "error")));
  $("#customerSearch").addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadCustomers().catch((error) => toast(error.message, "error"));
  });
  $("#refreshRuns").addEventListener("click", () => loadRuns().catch((error) => toast(error.message, "error")));
  $("#runEvaluation").addEventListener("click", runEvaluation);
  $$("[data-case-filter]").forEach((item) => item.addEventListener("click", async () => {
    state.caseFilter = item.dataset.caseFilter;
    $$("[data-case-filter]").forEach((chip) => chip.classList.toggle("is-active", chip === item));
    try {
      await loadCases();
    } catch (error) {
      toast(error.message, "error");
    }
  }));
  document.addEventListener("click", (event) => {
    const assess = event.target.closest("[data-assess-customer]");
    if (assess) assessCustomer(assess.dataset.assessCustomer, assess);
    const caseButton = event.target.closest("[data-open-case]");
    if (caseButton) openCase(caseButton.dataset.openCase);
  });
}

async function initialize() {
  bindEvents();
  $("#loadingCurtain").hidden = false;
  try {
    await Promise.all([loadDashboard(), loadCustomers(), loadCases(), loadRuns(), loadBenchmarkInfo(), loadEvaluations()]);
  } catch (error) {
    toast(`工作台初始化失败：${error.message}`, "error");
  } finally {
    $("#loadingCurtain").hidden = true;
  }
}

document.addEventListener("DOMContentLoaded", initialize);
