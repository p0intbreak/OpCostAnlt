(function () {
  const payload = window.dashboardPayload || {};
  const detailRows = payload.detail_rows || [];
  const detailIndex = payload.detail_row_index || {};
  const state = { activeIds: null, sortKey: "amount", sortDirection: "desc", search: "", status: "", confidence: "" };
  const byId = (id) => document.getElementById(id);

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    renderKpis();
    renderYearComparison();
    renderMonthlyTrends();
    renderCategoriesTree();
    renderStatusBreakdown();
    renderEntityBar("vendors-chart", payload.vendors || [], "vendor");
    renderEntityBar("organizations-chart", payload.organizations || [], "organization");
    renderDepartments();
    renderInsights();
    bindToolbar();
    renderDetailTable();
  }

  function renderKpis() {
    const root = byId("kpi-grid");
    if (!root) return;
    root.innerHTML = (payload.kpis || []).map((kpi) => `<div class="kpi-card"><div class="kpi-label">${esc(kpi.label)}</div><div class="kpi-value">${esc(String(kpi.value))}</div></div>`).join("");
  }

  function renderYearComparison() {
    const rows = payload.yearly_comparison || [];
    Plotly.newPlot("year-comparison-chart", [{ x: rows.map((r) => String(r.year)), y: rows.map((r) => r.total_amount), type: "bar", customdata: rows.map((r) => [r.year]), hovertemplate: "Год %{x}<br>Сумма %{y:.2f}<extra></extra>" }], layout("Сумма расходов"), { responsive: true });
    bindPlotClick("year-comparison-chart", (p) => activateSlice(`year:${p.customdata[0]}`));
  }

  function renderMonthlyTrends() {
    const rows = payload.monthly_trends || [];
    const years = [...new Set(rows.map((r) => r.year))];
    const traces = years.map((year) => ({ x: rows.filter((r) => r.year === year).map((r) => r.year_month), y: rows.filter((r) => r.year === year).map((r) => r.total_amount), mode: "lines+markers", name: String(year) }));
    Plotly.newPlot("monthly-trends-chart", traces, layout("Динамика расходов"), { responsive: true });
  }

  function renderCategoriesTree() {
    const tree = flatten(payload.categories_tree || []);
    Plotly.newPlot("categories-tree-chart", [{ type: "treemap", labels: tree.labels, ids: tree.ids, parents: tree.parents, values: tree.values, branchvalues: "total" }], { margin: { l: 0, r: 0, t: 8, b: 0 }, paper_bgcolor: "transparent" }, { responsive: true });
    bindPlotClick("categories-tree-chart", (p) => { if (p.id) activateSlice(p.id); });
  }

  function renderStatusBreakdown() {
    const rows = payload.status_breakdown || [];
    const traces = rows.map((row) => ({ x: ["Статусы"], y: [row.total_amount], name: row.status_label, type: "bar", customdata: [[row.status_id]], hovertemplate: `${row.status_label}<br>Сумма %{y:.2f}<extra></extra>` }));
    Plotly.newPlot("status-breakdown-chart", traces, { barmode: "stack", margin: { l: 36, r: 16, t: 8, b: 36 }, paper_bgcolor: "transparent", plot_bgcolor: "transparent" }, { responsive: true });
    bindPlotClick("status-breakdown-chart", (p) => activateSlice(`status:${p.customdata[0]}`));
  }

  function renderEntityBar(containerId, rows, prefix) {
    const topRows = rows.slice(0, 10);
    Plotly.newPlot(containerId, [{ x: topRows.map((r) => r.total_amount), y: topRows.map((r) => r.label), type: "bar", orientation: "h", customdata: topRows.map((r) => [r.id]), hovertemplate: "%{y}<br>Сумма %{x:.2f}<extra></extra>" }], { margin: { l: 160, r: 16, t: 8, b: 32 }, paper_bgcolor: "transparent", plot_bgcolor: "transparent" }, { responsive: true });
    bindPlotClick(containerId, (p) => activateSlice(`${prefix}:${p.customdata[0]}`));
  }

  function renderDepartments() {
    const grouped = {};
    detailRows.forEach((row) => {
      const key = row.department_name || "unknown";
      if (!grouped[key]) grouped[key] = { label: key, total_amount: 0 };
      grouped[key].total_amount += Number(row.amount || 0);
    });
    const rows = Object.values(grouped).sort((a, b) => b.total_amount - a.total_amount).slice(0, 10);
    Plotly.newPlot("departments-chart", [{ x: rows.map((r) => r.total_amount), y: rows.map((r) => r.label), type: "bar", orientation: "h", hovertemplate: "%{y}<br>Сумма %{x:.2f}<extra></extra>" }], { margin: { l: 160, r: 16, t: 8, b: 32 }, paper_bgcolor: "transparent", plot_bgcolor: "transparent" }, { responsive: true });
  }

  function renderInsights() {
    const root = byId("insights-grid");
    if (!root) return;
    root.innerHTML = (payload.insights || []).map((insight) => `<article class="insight-card ${insight.severity}" data-index="${payload.insights.indexOf(insight)}"><h3 class="insight-title">${esc(insight.title)}</h3><div class="insight-metric">${esc(insight.metric)}</div><div class="insight-text">${esc(insight.explanation)}</div></article>`).join("");
    root.querySelectorAll(".insight-card").forEach((card) => card.addEventListener("click", () => activateInsight(payload.insights[Number(card.dataset.index)].supporting_filters || {})));
  }

  function bindToolbar() {
    byId("detail-search")?.addEventListener("input", (e) => { state.search = e.target.value.toLowerCase(); renderDetailTable(); });
    byId("detail-status-filter")?.addEventListener("change", (e) => { state.status = e.target.value; renderDetailTable(); });
    byId("detail-confidence-filter")?.addEventListener("change", (e) => { state.confidence = e.target.value; renderDetailTable(); });
    byId("detail-reset")?.addEventListener("click", resetFilters);
    document.querySelectorAll("[data-sort-key]").forEach((header) => header.addEventListener("click", () => toggleSort(header.dataset.sortKey)));
  }

  function renderDetailTable() {
    const rows = visibleRows();
    const body = byId("detail-table-body");
    const summary = byId("detail-table-summary");
    if (!body || !summary) return;
    summary.textContent = `Показано ${rows.length} из ${detailRows.length} строк`;
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="10" class="empty-state">Нет строк под выбранные фильтры</td></tr>';
      return;
    }
    body.innerHTML = rows.map((row) => `<tr><td>${esc(row.period_date)}</td><td>${esc(row.vendor_label)}</td><td>${esc(row.organization_label)}</td><td>${esc(row.article_name)}</td><td><span class="badge">${esc(statusLabel(row.status_group))}</span></td><td>${esc(row.l1_category_label)}</td><td>${esc(row.l2_category_label)}</td><td>${esc(row.l3_category_label)}</td><td>${esc(row.classification_confidence)}</td><td>${formatAmount(row.amount)}</td></tr>`).join("");
  }

  function visibleRows() {
    let rows = detailRows.slice();
    if (state.activeIds?.length) {
      const allowed = new Set(state.activeIds);
      rows = rows.filter((row) => allowed.has(row.payment_id));
    }
    if (state.status) rows = rows.filter((row) => row.status_group === state.status);
    if (state.confidence) rows = rows.filter((row) => row.classification_confidence === state.confidence);
    if (state.search) rows = rows.filter((row) => [row.vendor_label, row.organization_label, row.article_name, row.project_name, row.department_name, row.l1_category_label, row.l2_category_label, row.l3_category_label].join(" ").toLowerCase().includes(state.search));
    rows.sort((a, b) => compare(a, b, state.sortKey, state.sortDirection));
    return rows;
  }

  function activateSlice(key) { state.activeIds = detailIndex[key] || []; renderDetailTable(); }
  function activateInsight(filters) {
    if (filters.payment_id) { state.activeIds = [filters.payment_id]; renderDetailTable(); return; }
    if (filters.vendor_name) return activateSlice(`vendor:${slug(filters.vendor_name)}`);
    if (filters.status_group) return activateSlice(`status:${filters.status_group}`);
    if (filters.organization_name) return activateSlice(`organization:${slug(filters.organization_name)}`);
    if (filters.l1_category) return activateSlice(`l1:${slug(filters.l1_category)}`);
  }
  function resetFilters() { state.activeIds = null; state.search = ""; state.status = ""; state.confidence = ""; if (byId("detail-search")) byId("detail-search").value = ""; if (byId("detail-status-filter")) byId("detail-status-filter").value = ""; if (byId("detail-confidence-filter")) byId("detail-confidence-filter").value = ""; renderDetailTable(); }
  function toggleSort(key) { state.sortDirection = state.sortKey === key && state.sortDirection === "asc" ? "desc" : "asc"; state.sortKey = key; if (key === "amount" && state.sortDirection !== "desc") state.sortDirection = "desc"; renderDetailTable(); }
  function bindPlotClick(id, cb) { const node = byId(id); if (node && node.on) node.on("plotly_click", (event) => event.points?.[0] && cb(event.points[0])); }
  function flatten(nodes) { const out = { labels: [], ids: [], parents: [], values: [] }; nodes.forEach((node) => walk(node, "", out)); return out; }
  function walk(node, parentId, out) { const id = `${node.level}:${node.id}`; out.labels.push(node.label); out.ids.push(id); out.parents.push(parentId); out.values.push(node.total_amount); (node.children || []).forEach((child) => walk(child, id, out)); }
  function layout(title) { return { margin: { l: 36, r: 16, t: 36, b: 36 }, title: { text: title, font: { size: 16 } }, paper_bgcolor: "transparent", plot_bgcolor: "transparent" }; }
  function compare(a, b, key, direction) { const sign = direction === "asc" ? 1 : -1; return ((typeof a[key] === "number" && typeof b[key] === "number") ? a[key] - b[key] : String(a[key]).localeCompare(String(b[key]), "ru")) * sign; }
  function formatAmount(value) { return new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value || 0)); }
  function statusLabel(value) { return ({ paid: "Оплачено", approved_not_paid: "Согласовано, не оплачено", in_approval: "На согласовании", rejected: "Отклонено", other: "Прочее" })[value] || value; }
  function slug(value) { return String(value || "").trim().toLowerCase().replace(/[^0-9a-z]+/g, "_").replace(/^_+|_+$/g, "") || "unknown"; }
  function esc(value) { return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }
})();
