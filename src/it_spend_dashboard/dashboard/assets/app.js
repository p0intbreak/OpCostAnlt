(function () {
  const payload = window.dashboardPayload || {};
  const detailRows = payload.detail_rows || [];
  const state = {
    filters: {
      year: "",
      month: "",
      status_group: "",
      l1_category_id: "",
      l2_category_id: "",
      l3_category_id: "",
      vendor_id: "",
      organization_id: "",
      classification_confidence: "",
    },
    search: "",
    sortKey: "amount",
    sortDirection: "desc",
    page: 1,
    pageSize: 10,
    breadcrumb: [],
  };

  const byId = (id) => document.getElementById(id);
  const statusLabels = {
    paid: "Оплачено",
    approved_not_paid: "Согласовано, не оплачено",
    in_approval: "На согласовании",
    rejected: "Отклонено",
    other: "Прочее",
  };

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
    bindControls();
    renderActiveFilters();
    renderBreadcrumb();
    renderDetailTable();
  }

  function renderKpis() {
    const root = byId("kpi-grid");
    if (!root) return;
    root.innerHTML = "";
    (payload.kpis || []).forEach((kpi) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "kpi-card";
      card.innerHTML = `<div class="kpi-label">${esc(kpi.label)}</div><div class="kpi-value">${esc(String(kpi.value))}</div>`;
      card.addEventListener("click", () => applyKpiFilter(kpi.id));
      root.appendChild(card);
    });
  }

  function renderYearComparison() {
    const rows = payload.yearly_comparison || [];
    Plotly.newPlot(
      "year-comparison-chart",
      [{
        x: rows.map((row) => String(row.year)),
        y: rows.map((row) => row.total_amount),
        type: "bar",
        customdata: rows.map((row) => [String(row.year)]),
        hovertemplate: "Год %{x}<br>Сумма %{y:.2f}<extra></extra>",
      }],
      baseLayout("Сумма расходов по годам"),
      { responsive: true }
    );
    bindPlotClick("year-comparison-chart", (point) => setFilter("year", point.customdata[0]));
  }

  function renderMonthlyTrends() {
    const rows = payload.monthly_trends || [];
    const years = [...new Set(rows.map((row) => row.year))];
    const traces = years.map((year) => {
      const scoped = rows.filter((row) => row.year === year);
      return {
        x: scoped.map((row) => row.year_month),
        y: scoped.map((row) => row.total_amount),
        mode: "lines+markers",
        name: String(year),
        customdata: scoped.map((row) => [String(row.year), String(row.month)]),
        hovertemplate: "%{x}<br>Сумма %{y:.2f}<extra></extra>",
      };
    });
    Plotly.newPlot("monthly-trends-chart", traces, baseLayout("Динамика по месяцам"), { responsive: true });
    bindPlotClick("monthly-trends-chart", (point) => {
      setFilter("year", point.customdata[0], false);
      setFilter("month", point.customdata[1], true);
    });
  }

  function renderCategoriesTree() {
    const flattened = flattenTree(payload.categories_tree || []);
    Plotly.newPlot(
      "categories-tree-chart",
      [{
        type: "treemap",
        labels: flattened.labels,
        ids: flattened.ids,
        parents: flattened.parents,
        values: flattened.values,
        branchvalues: "total",
        hovertemplate: "%{label}<br>Сумма %{value:.2f}<extra></extra>",
      }],
      { margin: { l: 0, r: 0, t: 8, b: 0 }, paper_bgcolor: "transparent" },
      { responsive: true }
    );
    bindPlotClick("categories-tree-chart", (point) => applyCategoryPath(point.id || ""));
  }

  function renderStatusBreakdown() {
    const rows = payload.status_breakdown || [];
    const traces = rows.map((row) => ({
      x: ["Статусы"],
      y: [row.total_amount],
      name: row.status_label,
      type: "bar",
      customdata: [[row.status_id]],
      hovertemplate: `${row.status_label}<br>Сумма %{y:.2f}<extra></extra>`,
    }));
    Plotly.newPlot(
      "status-breakdown-chart",
      traces,
      { ...baseLayout("Статусная структура"), barmode: "stack", margin: { l: 36, r: 16, t: 36, b: 36 } },
      { responsive: true }
    );
    bindPlotClick("status-breakdown-chart", (point) => setFilter("status_group", point.customdata[0]));
  }

  function renderEntityBar(containerId, rows, prefix) {
    const topRows = rows.slice(0, 10);
    Plotly.newPlot(
      containerId,
      [{
        x: topRows.map((row) => row.total_amount),
        y: topRows.map((row) => row.label),
        type: "bar",
        orientation: "h",
        customdata: topRows.map((row) => [row.id]),
        hovertemplate: "%{y}<br>Сумма %{x:.2f}<extra></extra>",
      }],
      { ...baseLayout(""), margin: { l: 160, r: 16, t: 8, b: 32 } },
      { responsive: true }
    );
    bindPlotClick(containerId, (point) => {
      if (prefix === "vendor") setFilter("vendor_id", point.customdata[0]);
      if (prefix === "organization") setFilter("organization_id", point.customdata[0]);
    });
  }

  function renderDepartments() {
    const rows = aggregateBy(detailRows, "department_name");
    Plotly.newPlot(
      "departments-chart",
      [{
        x: rows.map((row) => row.total_amount),
        y: rows.map((row) => row.label),
        type: "bar",
        orientation: "h",
        hovertemplate: "%{y}<br>Сумма %{x:.2f}<extra></extra>",
      }],
      { ...baseLayout("Подразделения"), margin: { l: 160, r: 16, t: 36, b: 32 } },
      { responsive: true }
    );
  }

  function renderInsights() {
    const root = byId("insights-grid");
    if (!root) return;
    root.innerHTML = "";
    (payload.insights || []).forEach((insight) => {
      const card = document.createElement("article");
      card.className = `insight-card ${insight.severity}`;
      card.innerHTML = `<h3 class="insight-title">${esc(insight.title)}</h3><div class="insight-metric">${esc(insight.metric)}</div><div class="insight-text">${esc(insight.explanation)}</div>`;
      card.addEventListener("click", () => applyInsightFilters(insight.supporting_filters || {}));
      root.appendChild(card);
    });
  }

  function bindControls() {
    bindSelect("detail-year-filter", "year");
    bindSelect("detail-month-filter", "month");
    bindSelect("detail-status-filter", "status_group");
    bindSelect("detail-confidence-filter", "classification_confidence");
    bindSelect("detail-l1-filter", "l1_category_id");
    bindSelect("detail-l2-filter", "l2_category_id");
    bindSelect("detail-l3-filter", "l3_category_id");
    bindSelect("detail-vendor-filter", "vendor_id");
    bindSelect("detail-organization-filter", "organization_id");

    byId("detail-search")?.addEventListener("input", (event) => {
      state.search = String(event.target.value || "").toLowerCase();
      state.page = 1;
      renderDetailTable();
    });
    byId("detail-reset")?.addEventListener("click", resetAllFilters);
    byId("detail-export")?.addEventListener("click", exportCurrentSelectionToCsv);
    document.querySelectorAll("[data-sort-key]").forEach((header) => {
      header.addEventListener("click", () => toggleSort(header.dataset.sortKey));
    });
  }

  function bindSelect(id, field) {
    byId(id)?.addEventListener("change", (event) => setFilter(field, event.target.value));
  }

  function setFilter(field, value, rerender = true) {
    state.filters[field] = String(value || "");
    if (field === "l1_category_id" && !value) {
      state.filters.l2_category_id = "";
      state.filters.l3_category_id = "";
      state.breadcrumb = [];
    }
    if (field === "l2_category_id" && !value) {
      state.filters.l3_category_id = "";
      state.breadcrumb = state.breadcrumb.slice(0, 1);
    }
    state.page = 1;
    syncSelectValues();
    if (rerender) rerenderAll();
  }

  function rerenderAll() {
    renderActiveFilters();
    renderBreadcrumb();
    renderDetailTable();
  }

  function applyCategoryPath(path) {
    if (!path) return;
    const parts = String(path).split("|");
    const breadcrumb = [];
    state.filters.l1_category_id = "";
    state.filters.l2_category_id = "";
    state.filters.l3_category_id = "";
    parts.forEach((part) => {
      const [level, id, label] = part.split(":");
      if (level === "l1") state.filters.l1_category_id = id;
      if (level === "l2") state.filters.l2_category_id = id;
      if (level === "l3") state.filters.l3_category_id = id;
      breadcrumb.push({ level, id, label });
    });
    state.breadcrumb = breadcrumb;
    state.page = 1;
    syncSelectValues();
    rerenderAll();
  }

  function applyKpiFilter(kpiId) {
    if (kpiId === "paid_amount") setFilter("status_group", "paid");
    else if (kpiId === "unpaid_amount") setFilter("status_group", "approved_not_paid");
    else if (kpiId === "review_share") setFilter("classification_confidence", "unclassified");
    else resetAllFilters();
  }

  function applyInsightFilters(filters) {
    if (filters.status_group) setFilter("status_group", filters.status_group, false);
    if (filters.vendor_name) setFilter("vendor_id", slug(filters.vendor_name), false);
    if (filters.organization_name) setFilter("organization_id", slug(filters.organization_name), false);
    if (filters.l1_category) setFilter("l1_category_id", slug(filters.l1_category), false);
    if (filters.year && Array.isArray(filters.year) && filters.year.length) setFilter("year", String(filters.year[filters.year.length - 1]), false);
    state.page = 1;
    syncSelectValues();
    rerenderAll();
  }

  function syncSelectValues() {
    const mapping = {
      "detail-year-filter": state.filters.year,
      "detail-month-filter": state.filters.month,
      "detail-status-filter": state.filters.status_group,
      "detail-confidence-filter": state.filters.classification_confidence,
      "detail-l1-filter": state.filters.l1_category_id,
      "detail-l2-filter": state.filters.l2_category_id,
      "detail-l3-filter": state.filters.l3_category_id,
      "detail-vendor-filter": state.filters.vendor_id,
      "detail-organization-filter": state.filters.organization_id,
    };
    Object.entries(mapping).forEach(([id, value]) => {
      const node = byId(id);
      if (node) node.value = value;
    });
  }

  function renderActiveFilters() {
    const root = byId("active-filters");
    if (!root) return;
    const chips = [];
    Object.entries(activeFilterLabels()).forEach(([field, label]) => {
      chips.push(`<span class="filter-chip">${esc(label)}<button type="button" data-remove-filter="${field}">×</button></span>`);
    });
    root.innerHTML = chips.length ? chips.join("") : '<span class="section-caption">Активных фильтров нет</span>';
    root.querySelectorAll("[data-remove-filter]").forEach((button) => {
      button.addEventListener("click", () => removeFilter(button.dataset.removeFilter));
    });
  }

  function activeFilterLabels() {
    const labels = {};
    if (state.filters.year) labels.year = `Год: ${state.filters.year}`;
    if (state.filters.month) labels.month = `Месяц: ${String(state.filters.month).padStart(2, "0")}`;
    if (state.filters.status_group) labels.status_group = `Статус: ${statusLabel(state.filters.status_group)}`;
    if (state.filters.l1_category_id) labels.l1_category_id = `L1: ${findLabel(payload.filters?.categories_l1, state.filters.l1_category_id)}`;
    if (state.filters.l2_category_id) labels.l2_category_id = `L2: ${findLabel(payload.filters?.categories_l2, state.filters.l2_category_id)}`;
    if (state.filters.l3_category_id) labels.l3_category_id = `L3: ${findLabel(payload.filters?.categories_l3, state.filters.l3_category_id)}`;
    if (state.filters.vendor_id) labels.vendor_id = `Поставщик: ${findLabel(payload.filters?.vendors, state.filters.vendor_id)}`;
    if (state.filters.organization_id) labels.organization_id = `Организация: ${findLabel(payload.filters?.organizations, state.filters.organization_id)}`;
    if (state.filters.classification_confidence) labels.classification_confidence = `Качество: ${state.filters.classification_confidence}`;
    if (state.search) labels.search = `Поиск: ${state.search}`;
    return labels;
  }

  function renderBreadcrumb() {
    const root = byId("category-breadcrumb");
    if (!root) return;
    if (!state.breadcrumb.length) {
      root.innerHTML = '<span class="section-caption">Путь drill-down пока не выбран</span>';
      return;
    }
    root.innerHTML = state.breadcrumb.map((item, index) => {
      const prefix = state.breadcrumb.slice(0, index + 1).map((part) => `${part.level}:${part.id}:${part.label}`).join("|");
      return `<span class="breadcrumb-chip">${esc(item.label)}<button type="button" data-breadcrumb="${escAttr(prefix)}">×</button></span>`;
    }).join("");
    root.querySelectorAll("[data-breadcrumb]").forEach((button) => {
      button.addEventListener("click", () => applyCategoryPath(button.dataset.breadcrumb));
    });
  }

  function renderDetailTable() {
    const rows = getFilteredRows();
    const totalPages = Math.max(1, Math.ceil(rows.length / state.pageSize));
    if (state.page > totalPages) state.page = totalPages;
    const pagedRows = rows.slice((state.page - 1) * state.pageSize, state.page * state.pageSize);
    const body = byId("detail-table-body");
    const summary = byId("detail-table-summary");
    if (!body || !summary) return;
    summary.textContent = `Показано ${pagedRows.length} из ${rows.length} строк`;
    if (!pagedRows.length) {
      body.innerHTML = '<tr><td colspan="10" class="empty-state">Нет строк под выбранные фильтры</td></tr>';
    } else {
      body.innerHTML = pagedRows.map((row) => `
        <tr>
          <td>${esc(row.period_date)}</td>
          <td>${esc(row.vendor_label)}</td>
          <td>${esc(row.organization_label)}</td>
          <td>${esc(row.article_name)}</td>
          <td><span class="badge">${esc(statusLabel(row.status_group))}</span></td>
          <td>${esc(row.l1_category_label)}</td>
          <td>${esc(row.l2_category_label)}</td>
          <td>${esc(row.l3_category_label)}</td>
          <td>${esc(row.classification_confidence)}</td>
          <td>${formatAmount(row.amount)}</td>
        </tr>
      `).join("");
    }
    renderPagination(rows.length, totalPages);
  }

  function renderPagination(totalRows, totalPages) {
    const markup = `
      <button type="button" data-page-action="prev" ${state.page <= 1 ? "disabled" : ""}>Назад</button>
      <span class="pagination-info">Страница ${state.page} из ${totalPages}, строк: ${totalRows}</span>
      <button type="button" data-page-action="next" ${state.page >= totalPages ? "disabled" : ""}>Вперед</button>
    `;
    ["detail-pagination-top", "detail-pagination-bottom"].forEach((id) => {
      const node = byId(id);
      if (!node) return;
      node.innerHTML = markup;
      node.querySelectorAll("[data-page-action]").forEach((button) => {
        button.addEventListener("click", () => {
          if (button.dataset.pageAction === "prev" && state.page > 1) state.page -= 1;
          if (button.dataset.pageAction === "next" && state.page < totalPages) state.page += 1;
          renderDetailTable();
        });
      });
    });
  }

  function getFilteredRows() {
    const filtered = detailRows.filter((row) => {
      if (state.filters.year && String(row.year) !== state.filters.year) return false;
      if (state.filters.month && String(row.month) !== state.filters.month) return false;
      if (state.filters.status_group && row.status_group !== state.filters.status_group) return false;
      if (state.filters.l1_category_id && row.l1_category_id !== state.filters.l1_category_id) return false;
      if (state.filters.l2_category_id && row.l2_category_id !== state.filters.l2_category_id) return false;
      if (state.filters.l3_category_id && row.l3_category_id !== state.filters.l3_category_id) return false;
      if (state.filters.vendor_id && row.vendor_id !== state.filters.vendor_id) return false;
      if (state.filters.organization_id && row.organization_id !== state.filters.organization_id) return false;
      if (state.filters.classification_confidence && row.classification_confidence !== state.filters.classification_confidence) return false;
      if (state.search) {
        const haystack = [
          row.vendor_label,
          row.organization_label,
          row.article_name,
          row.project_name,
          row.department_name,
          row.l1_category_label,
          row.l2_category_label,
          row.l3_category_label,
        ].join(" ").toLowerCase();
        if (!haystack.includes(state.search)) return false;
      }
      return true;
    });
    return filtered.sort((left, right) => compareRows(left, right));
  }

  function compareRows(left, right) {
    const key = state.sortKey;
    const direction = state.sortDirection === "asc" ? 1 : -1;
    const a = left[key];
    const b = right[key];
    if (typeof a === "number" && typeof b === "number") return (a - b) * direction;
    return String(a).localeCompare(String(b), "ru") * direction;
  }

  function removeFilter(field) {
    if (field === "search") {
      state.search = "";
      const node = byId("detail-search");
      if (node) node.value = "";
    } else {
      setFilter(field, "", false);
    }
    if (field === "l1_category_id") {
      state.filters.l2_category_id = "";
      state.filters.l3_category_id = "";
      state.breadcrumb = [];
    }
    if (field === "l2_category_id") {
      state.filters.l3_category_id = "";
      state.breadcrumb = state.breadcrumb.slice(0, 1);
    }
    syncSelectValues();
    rerenderAll();
  }

  function resetAllFilters() {
    Object.keys(state.filters).forEach((field) => { state.filters[field] = ""; });
    state.search = "";
    state.page = 1;
    state.breadcrumb = [];
    const search = byId("detail-search");
    if (search) search.value = "";
    syncSelectValues();
    rerenderAll();
  }

  function toggleSort(key) {
    if (state.sortKey === key) {
      state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
    } else {
      state.sortKey = key;
      state.sortDirection = key === "amount" ? "desc" : "asc";
    }
    renderDetailTable();
  }

  function exportCurrentSelectionToCsv() {
    const rows = getFilteredRows();
    const columns = ["period_date", "vendor_label", "organization_label", "article_name", "status_group", "l1_category_label", "l2_category_label", "l3_category_label", "classification_confidence", "amount"];
    const csv = [columns.join(",")].concat(
      rows.map((row) => columns.map((column) => csvCell(row[column])).join(","))
    ).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "dashboard_selection.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  function flattenTree(nodes) {
    const out = { labels: [], ids: [], parents: [], values: [] };
    nodes.forEach((node) => walkTree(node, "", out, []));
    return out;
  }

  function walkTree(node, parentId, out, path) {
    const current = `${node.level}:${node.id}:${node.label}`;
    const fullPath = path.concat(current);
    out.labels.push(node.label);
    out.ids.push(fullPath.join("|"));
    out.parents.push(parentId);
    out.values.push(node.total_amount);
    (node.children || []).forEach((child) => walkTree(child, fullPath.join("|"), out, fullPath));
  }

  function aggregateBy(rows, field) {
    const grouped = {};
    rows.forEach((row) => {
      const label = String(row[field] || "unknown");
      if (!grouped[label]) grouped[label] = { label, total_amount: 0 };
      grouped[label].total_amount += Number(row.amount || 0);
    });
    return Object.values(grouped).sort((a, b) => b.total_amount - a.total_amount).slice(0, 10);
  }

  function findLabel(options, id) {
    return (options || []).find((item) => item.id === id)?.label || id;
  }

  function bindPlotClick(containerId, callback) {
    const node = byId(containerId);
    if (!node || !node.on) return;
    node.on("plotly_click", (event) => {
      if (event.points && event.points[0]) callback(event.points[0]);
    });
  }

  function baseLayout(title) {
    return {
      margin: { l: 36, r: 16, t: 36, b: 36 },
      title: title ? { text: title, font: { size: 16 } } : undefined,
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      xaxis: { color: "#5f6b7a", gridcolor: "rgba(95,107,122,0.18)" },
      yaxis: { color: "#5f6b7a", gridcolor: "rgba(95,107,122,0.18)" },
      legend: { orientation: "h" },
    };
  }

  function statusLabel(value) {
    return statusLabels[value] || value;
  }

  function slug(value) {
    return String(value || "").trim().toLowerCase().replace(/[^0-9a-z]+/g, "_").replace(/^_+|_+$/g, "") || "unknown";
  }

  function csvCell(value) {
    return `"${String(value == null ? "" : value).replace(/"/g, '""')}"`;
  }

  function formatAmount(value) {
    return new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value || 0));
  }

  function esc(value) {
    return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function escAttr(value) {
    return esc(value).replace(/"/g, "&quot;");
  }
})();
