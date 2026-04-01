(function () {
  const payload = window.dashboardPayload || {};
  const apiBaseUrl = window.dashboardApiBaseUrl || "/api/dashboard";
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
    pageSize: 25,
    breadcrumb: [],
    tableRows: [],
    totalRows: 0,
    totalPages: 1,
    vendorDrilldown: {
      selectedVendorId: "",
      selectedMonth: "",
    },
  };

  const byId = (id) => document.getElementById(id);
  const amountAxisTemplate = {
    color: "#5f6b7a",
    gridcolor: "rgba(95,107,122,0.18)",
    tickformat: ",.0f",
  };
  const statusLabels = {
    paid: "Оплачено",
    approved_not_paid: "Согласовано, не оплачено",
    in_approval: "На согласовании",
    rejected: "Отклонено",
    other: "Прочее",
  };
  const cyrillicToLatin = {
    а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e", ж: "zh", з: "z", и: "i",
    й: "i", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t",
    у: "u", ф: "f", х: "h", ц: "ts", ч: "ch", ш: "sh", щ: "sch", ъ: "", ы: "y", ь: "",
    э: "e", ю: "yu", я: "ya",
  };

  document.addEventListener("DOMContentLoaded", init);

  async function init() {
    renderStoryline();
    renderInsights();
    renderKpis();
    renderYearComparison();
    renderStatusBreakdown();
    renderCategoriesTree();
    renderCategoryRanking();
    renderMonthlyTrends();
    renderCategoryYoy();
    renderEntityBar("organizations-chart", payload.organizations || [], "organization");
    renderDepartments();
    bindControls();
    bindModalControls();
    renderActiveFilters();
    renderBreadcrumb();
    await loadVendorDrilldown();
    await loadDetailTable();
  }

  function renderStoryline() {
    const totalAmount = Number((payload.kpis || []).find((item) => item.id === "total_amount")?.value || 0);
    const topCategory = flattenL1Categories(payload.categories_tree || [])[0];
    const growthLeader = (payload.category_yoy || [])
      .filter((row) => Number(row.delta_amount || 0) > 0)
      .sort((a, b) => Number(b.delta_amount || 0) - Number(a.delta_amount || 0))[0];
    const stuckAmount = (payload.status_breakdown || [])
      .filter((row) => ["approved_not_paid", "in_approval"].includes(row.status_id))
      .reduce((sum, row) => sum + Number(row.total_amount || 0), 0);

    setText("story-main-title", topCategory ? topCategory.label : "Крупнейшая статья не найдена");
    setText("story-main-metric", topCategory ? formatAmountThousands(topCategory.total_amount) : "Нет данных");
    setText(
      "story-main-text",
      topCategory
        ? `${topCategory.label} формирует ${formatPercent(topCategory.total_amount / Math.max(totalAmount, 1))} общего бюджета. Это главный слой расходов, с которого стоит начинать анализ.`
        : "Недостаточно данных для определения крупнейшей категории."
    );

    setText("story-growth-title", growthLeader ? growthLeader.label : "Нет выраженного роста");
    setText("story-growth-metric", growthLeader ? formatSignedThousands(growthLeader.delta_amount) : "Нет данных");
    setText(
      "story-growth-text",
      growthLeader
        ? `В ${growthLeader.right_year} году категория выросла относительно ${growthLeader.left_year} года на ${formatPercent(growthLeader.delta_share)}. Это главный кандидат для проверки причин ускорения.`
        : "Годовое сравнение пока не показывает явного лидера роста."
    );

    setText("story-risk-title", "Неоплаченные и зависшие суммы");
    setText("story-risk-metric", formatAmountThousands(stuckAmount));
    setText("story-risk-text", "Суммы в статусах «Согласовано, не оплачено» и «На согласовании» образуют операционный риск и требуют управленческого контроля.");
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

  function renderKpis() {
    const root = byId("kpi-grid");
    if (!root) return;
    root.innerHTML = "";
    (payload.kpis || []).forEach((kpi) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "kpi-card";
      card.innerHTML = `<div class="kpi-label">${esc(kpi.label)}</div><div class="kpi-value">${esc(formatKpiValue(kpi))}</div>`;
      card.addEventListener("click", () => applyKpiFilter(kpi.id));
      root.appendChild(card);
    });
  }

  function renderYearComparison() {
    const rows = payload.yearly_comparison || [];
    Plotly.newPlot("year-comparison-chart", [{
      x: rows.map((row) => String(row.year)),
      y: rows.map((row) => toThousands(row.total_amount)),
      type: "bar",
      marker: { color: ["#a8c0ff", "#2e62ff"] },
      customdata: rows.map((row) => [String(row.year)]),
      text: rows.map((row) => formatAmountThousands(row.total_amount)),
      textposition: "outside",
      hovertemplate: "Год %{x}<br>Сумма %{y:,.2f} тыс. руб.<extra></extra>",
    }], baseLayout(""), { responsive: true });
    bindPlotClick("year-comparison-chart", (point) => setFilter("year", point.customdata[0]));
  }

  function renderStatusBreakdown() {
    const rows = payload.status_breakdown || [];
    const traces = rows.map((row) => ({
      x: ["Статусы"],
      y: [toThousands(row.total_amount)],
      name: row.status_label,
      type: "bar",
      customdata: [[row.status_id]],
      hovertemplate: `${row.status_label}<br>Сумма %{y:,.2f} тыс. руб.<extra></extra>`,
    }));
    Plotly.newPlot("status-breakdown-chart", traces, { ...baseLayout(""), barmode: "stack", margin: { l: 28, r: 12, t: 20, b: 24 } }, { responsive: true });
    bindPlotClick("status-breakdown-chart", (point) => setFilter("status_group", point.customdata[0]));
  }

  function renderCategoriesTree() {
    const flattened = flattenTree(payload.categories_tree || []);
    Plotly.newPlot("categories-tree-chart", [{
      type: "treemap",
      labels: flattened.labels,
      ids: flattened.ids,
      parents: flattened.parents,
      values: flattened.values.map((value) => toThousands(value)),
      branchvalues: "total",
      textinfo: "label+value",
      hovertemplate: "%{label}<br>Сумма %{value:,.2f} тыс. руб.<extra></extra>",
    }], { margin: { l: 0, r: 0, t: 4, b: 0 }, paper_bgcolor: "transparent" }, { responsive: true });
    bindPlotClick("categories-tree-chart", (point) => applyCategoryPath(point.id || ""));
  }

  function renderCategoryRanking() {
    const rows = flattenL1Categories(payload.categories_tree || []).slice(0, 8);
    Plotly.newPlot("category-ranking-chart", [{
      x: rows.map((row) => toThousands(row.total_amount)),
      y: rows.map((row) => row.label),
      type: "bar",
      orientation: "h",
      marker: { color: "#2e62ff" },
      customdata: rows.map((row) => [row.id]),
      text: rows.map((row) => formatAmountThousands(row.total_amount)),
      textposition: "outside",
      hovertemplate: "%{y}<br>Сумма %{x:,.2f} тыс. руб.<extra></extra>",
    }], { ...baseLayout(""), margin: { l: 160, r: 16, t: 8, b: 20 }, xaxis: amountAxisTemplate }, { responsive: true });
    bindPlotClick("category-ranking-chart", (point) => setFilter("l1_category_id", point.customdata[0]));
  }

  function renderMonthlyTrends() {
    const rows = payload.monthly_trends || [];
    const years = [...new Set(rows.map((row) => row.year))];
    const traces = years.map((year, index) => {
      const scoped = rows.filter((row) => row.year === year);
      return {
        x: scoped.map((row) => row.year_month),
        y: scoped.map((row) => toThousands(row.total_amount)),
        mode: "lines+markers",
        line: { width: 3, color: index === years.length - 1 ? "#2e62ff" : "#8bb8ff" },
        marker: { size: 6 },
        fill: index === years.length - 1 ? "tozeroy" : undefined,
        fillcolor: index === years.length - 1 ? "rgba(46, 98, 255, 0.12)" : undefined,
        name: String(year),
        customdata: scoped.map((row) => [String(row.year), String(row.month)]),
        hovertemplate: "%{x}<br>Сумма %{y:,.2f} тыс. руб.<extra></extra>",
      };
    });
    Plotly.newPlot("monthly-trends-chart", traces, { ...baseLayout(""), margin: { l: 34, r: 16, t: 16, b: 30 } }, { responsive: true });
    bindPlotClick("monthly-trends-chart", (point) => {
      setFilter("year", point.customdata[0], false);
      setFilter("month", point.customdata[1], true);
    });
  }

  function renderCategoryYoy() {
    const rows = (payload.category_yoy || []).slice(0, 8);
    Plotly.newPlot("category-yoy-chart", [{
      x: rows.map((row) => row.label),
      y: rows.map((row) => toThousands(row.delta_amount)),
      type: "bar",
      marker: { color: rows.map((row) => Number(row.delta_amount || 0) >= 0 ? "#16a34a" : "#f59e0b") },
      customdata: rows.map((row) => [row.id]),
      text: rows.map((row) => formatSignedThousands(row.delta_amount)),
      textposition: "outside",
      hovertemplate: "%{x}<br>Δ %{y:,.2f} тыс. руб.<extra></extra>",
    }], { ...baseLayout(""), margin: { l: 34, r: 12, t: 20, b: 90 }, xaxis: { tickangle: -24 } }, { responsive: true });
    bindPlotClick("category-yoy-chart", (point) => setFilter("l1_category_id", point.customdata[0]));
  }

  function renderEntityBar(containerId, rows, prefix) {
    const topRows = rows.slice(0, 10);
    Plotly.newPlot(containerId, [{
      x: topRows.map((row) => toThousands(row.total_amount)),
      y: topRows.map((row) => row.label),
      type: "bar",
      orientation: "h",
      marker: { color: prefix === "vendor" ? "#2e62ff" : "#18b5d8" },
      customdata: topRows.map((row) => [row.id]),
      hovertemplate: "%{y}<br>Сумма %{x:,.2f} тыс. руб.<extra></extra>",
    }], { ...baseLayout(""), margin: { l: 170, r: 16, t: 8, b: 24 }, xaxis: amountAxisTemplate }, { responsive: true });
    bindPlotClick(containerId, (point) => {
      if (prefix === "vendor") setFilter("vendor_id", point.customdata[0]);
      if (prefix === "organization") setFilter("organization_id", point.customdata[0]);
    });
  }

  function renderDepartments() {
    const rows = payload.departments || [];
    Plotly.newPlot("departments-chart", [{
      x: rows.slice(0, 10).map((row) => toThousands(row.total_amount)),
      y: rows.slice(0, 10).map((row) => row.label),
      type: "bar",
      orientation: "h",
      marker: { color: "#7aa8ff" },
      hovertemplate: "%{y}<br>Сумма %{x:,.2f} тыс. руб.<extra></extra>",
    }], { ...baseLayout(""), margin: { l: 170, r: 16, t: 8, b: 24 }, xaxis: amountAxisTemplate }, { responsive: true });
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
      loadDetailTable();
    });
    byId("detail-reset")?.addEventListener("click", () => resetAllFilters());
    byId("detail-export")?.addEventListener("click", exportCurrentSelectionToCsv);
    document.querySelectorAll("[data-sort-key]").forEach((header) => {
      header.addEventListener("click", () => toggleSort(header.dataset.sortKey));
    });
  }

  function bindModalControls() {
    byId("detail-modal-close")?.addEventListener("click", closeDetailModal);
    byId("detail-modal")?.addEventListener("click", (event) => {
      if (event.target?.id === "detail-modal") closeDetailModal();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeDetailModal();
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
    loadVendorDrilldown();
    loadDetailTable();
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
    resetAllFilters(false);
    if (filters.status_group) setFilter("status_group", filters.status_group, false);
    if (filters.vendor_name) setFilter("vendor_id", slug(filters.vendor_name), false);
    if (filters.organization_name) setFilter("organization_id", slug(filters.organization_name), false);
    if (filters.l1_category) setFilter("l1_category_id", slug(filters.l1_category), false);
    if (filters.year && Array.isArray(filters.year) && filters.year.length) setFilter("year", String(filters.year[filters.year.length - 1]), false);
    state.page = 1;
    syncSelectValues();
    rerenderAll();
    byId("detail-table-summary")?.scrollIntoView({ behavior: "smooth", block: "start" });
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

  async function loadDetailTable() {
    const params = buildQueryParams();
    const response = await fetch(`${apiBaseUrl}/details?${params.toString()}`);
    if (!response.ok) return;
    const payload = await response.json();
    state.tableRows = payload.rows || [];
    state.totalRows = Number(payload.total_rows || 0);
    state.totalPages = Number(payload.total_pages || 1);
    renderDetailTable();
  }

  async function loadVendorDrilldown() {
    const params = new URLSearchParams();
    if (state.filters.year) params.set("year", state.filters.year);
    if (state.filters.status_group) params.set("status_group", state.filters.status_group);
    if (state.filters.l1_category_id) params.set("l1_category_id", state.filters.l1_category_id);
    if (state.filters.l2_category_id) params.set("l2_category_id", state.filters.l2_category_id);
    if (state.filters.l3_category_id) params.set("l3_category_id", state.filters.l3_category_id);
    if (state.filters.organization_id) params.set("organization_id", state.filters.organization_id);
    if (state.filters.classification_confidence) params.set("classification_confidence", state.filters.classification_confidence);
    if (state.vendorDrilldown.selectedVendorId) params.set("selected_vendor_id", state.vendorDrilldown.selectedVendorId);
    if (state.vendorDrilldown.selectedMonth) params.set("selected_month", state.vendorDrilldown.selectedMonth);
    const response = await fetch(`${apiBaseUrl}/vendor-drilldown?${params.toString()}`);
    if (!response.ok) return;
    const drilldown = await response.json();
    state.vendorDrilldown.selectedVendorId = String(drilldown.selected_vendor_id || "");
    state.vendorDrilldown.selectedMonth = String(drilldown.selected_month || "");
    renderVendorDrilldown(drilldown);
  }

  function renderVendorDrilldown(drilldown) {
    const stateNode = byId("vendor-drilldown-state");
    if (stateNode) {
      if (drilldown.selected_vendor_label) {
        const monthLabel = drilldown.selected_month ? String(drilldown.selected_month).padStart(2, "0") : "все месяцы";
        stateNode.textContent = `Год: ${drilldown.selected_year || "—"} · Поставщик: ${drilldown.selected_vendor_label} · Месяц: ${monthLabel}`;
      } else {
        stateNode.textContent = "Нет данных для построения vendor drill-down в текущем срезе.";
      }
    }

    renderVendorAnnualChart(drilldown.top_vendors || [], drilldown.selected_vendor_id || "");
    renderVendorMonthlyChart(drilldown.vendor_monthly || [], drilldown.selected_month || "");
    renderVendorComponentsChart(drilldown.month_components || []);
  }

  function renderVendorAnnualChart(rows, selectedVendorId) {
    const colors = rows.map((row) => row.id === selectedVendorId ? "#2e62ff" : "#a8c0ff");
    Plotly.newPlot("vendors-top-chart", [{
      x: rows.map((row) => row.label),
      y: rows.map((row) => toThousands(row.total_amount)),
      type: "bar",
      marker: { color: colors },
      customdata: rows.map((row) => [row.id]),
      text: rows.map((row) => formatAmountThousands(row.total_amount)),
      textposition: "outside",
      hovertemplate: "%{x}<br>Сумма %{y:,.2f} тыс. руб.<extra></extra>",
    }], {
      ...baseLayout(""),
      margin: { l: 32, r: 16, t: 10, b: 110 },
      xaxis: { tickangle: -28, automargin: true, color: "#5f6b7a" },
      yaxis: amountAxisTemplate,
      showlegend: false,
    }, { responsive: true });
    bindPlotClick("vendors-top-chart", (point) => {
      state.vendorDrilldown.selectedVendorId = point.customdata[0];
      state.vendorDrilldown.selectedMonth = "";
      loadVendorDrilldown();
    });
  }

  function renderVendorMonthlyChart(rows, selectedMonth) {
    const colors = rows.map((row) => String(row.month) === String(selectedMonth) ? "#2e62ff" : "#8bb8ff");
    Plotly.newPlot("vendor-monthly-chart", [{
      x: rows.map((row) => row.year_month || String(row.month).padStart(2, "0")),
      y: rows.map((row) => toThousands(row.total_amount)),
      type: "bar",
      marker: { color: colors },
      customdata: rows.map((row) => [String(row.month)]),
      text: rows.map((row) => formatAmountThousands(row.total_amount)),
      textposition: "outside",
      hovertemplate: "%{x}<br>Сумма %{y:,.2f} тыс. руб.<extra></extra>",
    }], {
      ...baseLayout(""),
      margin: { l: 32, r: 16, t: 10, b: 48 },
      showlegend: false,
    }, { responsive: true });
    bindPlotClick("vendor-monthly-chart", (point) => {
      state.vendorDrilldown.selectedMonth = point.customdata[0];
      loadVendorDrilldown();
    });
  }

  function renderVendorComponentsChart(rows) {
    Plotly.newPlot("vendor-components-chart", [{
      x: rows.map((row) => toThousands(row.total_amount)),
      y: rows.map((row) => row.label),
      type: "bar",
      orientation: "h",
      marker: { color: "#18b5d8" },
      text: rows.map((row) => formatAmountThousands(row.total_amount)),
      textposition: "outside",
      hovertemplate: "%{y}<br>Сумма %{x:,.2f} тыс. руб.<extra></extra>",
    }], {
      ...baseLayout(""),
      margin: { l: 210, r: 16, t: 10, b: 24 },
      xaxis: amountAxisTemplate,
      showlegend: false,
    }, { responsive: true });
  }

  function renderDetailTable() {
    const body = byId("detail-table-body");
    const summary = byId("detail-table-summary");
    if (!body || !summary) return;
    summary.textContent = `Показано ${state.tableRows.length} из ${state.totalRows} строк`;
    if (!state.tableRows.length) {
      body.innerHTML = '<tr><td colspan="9" class="empty-state">Нет строк под выбранные фильтры</td></tr>';
    } else {
      body.innerHTML = state.tableRows.map((row) => `
        <tr data-detail-row-id="${escAttr(row.detail_row_id)}">
          <td>${esc(row.period_date)}</td>
          <td>${esc(row.vendor_label)}</td>
          <td>${esc(row.organization_label)}</td>
          <td>${esc(row.expense_subject || row.article_name)}${Number(row.source_line_count || 1) > 1 ? ` <span class="badge">источников: ${Number(row.source_line_count)}</span>` : ""}</td>
          <td>${esc(row.project_name)}</td>
          <td>${esc(row.classification_confidence)}</td>
          <td class="detail-reason-cell">${esc(row.classification_reason_human)}</td>
          <td class="detail-status-cell"><span class="badge">${esc(statusLabel(row.status_group))}</span></td>
          <td class="detail-amount-cell">${formatAmountThousands(row.amount)}</td>
        </tr>
      `).join("");
      body.querySelectorAll("[data-detail-row-id]").forEach((node) => {
        node.addEventListener("click", () => openDetailModal(node.dataset.detailRowId));
      });
    }
    renderPagination();
  }

  function renderPagination() {
    const markup = `
      <button type="button" data-page-action="prev" ${state.page <= 1 ? "disabled" : ""}>Назад</button>
      <span class="pagination-info">Страница ${state.page} из ${state.totalPages}, строк: ${state.totalRows}</span>
      <button type="button" data-page-action="next" ${state.page >= state.totalPages ? "disabled" : ""}>Вперед</button>
    `;
    ["detail-pagination-top", "detail-pagination-bottom"].forEach((id) => {
      const node = byId(id);
      if (!node) return;
      node.innerHTML = markup;
      node.querySelectorAll("[data-page-action]").forEach((button) => {
        button.addEventListener("click", () => {
          if (button.dataset.pageAction === "prev" && state.page > 1) state.page -= 1;
          if (button.dataset.pageAction === "next" && state.page < state.totalPages) state.page += 1;
          loadDetailTable();
        });
      });
    });
  }

  async function openDetailModal(detailRowId) {
    const response = await fetch(`${apiBaseUrl}/rows/${encodeURIComponent(detailRowId)}`);
    if (!response.ok) return;
    const details = await response.json();
    setText("detail-modal-title", `Позиция ${detailRowId}`);
    const summary = details.summary || {};
    setText(
      "detail-modal-summary",
      `${summary.period_date || ""} · ${summary.vendor_name || ""} · ${formatAmountThousands(summary.amount || 0)} · статус: ${statusLabel(summary.status_group || "")} · исходных строк: ${summary.source_line_count || 1}`
    );
    renderKeyValueGrid("detail-modal-pipeline", details.pipeline_attributes || {});
    renderLineCollection("detail-modal-raw", details.raw_lines || [], details.raw_attributes || {});
    renderTransformations("detail-modal-transformations", details.transformations || []);
    byId("detail-modal")?.classList.remove("hidden");
    byId("detail-modal")?.setAttribute("aria-hidden", "false");
  }

  function closeDetailModal() {
    byId("detail-modal")?.classList.add("hidden");
    byId("detail-modal")?.setAttribute("aria-hidden", "true");
  }

  function renderTransformations(containerId, transformations) {
    const node = byId(containerId);
    if (!node) return;
    if (!transformations.length) {
      node.innerHTML = '<div class="section-caption">Изменений по правилам очистки и нормализации не зафиксировано.</div>';
      return;
    }
    node.innerHTML = `<div class="transformation-list">${transformations.map((item) => `
      <div class="transformation-item">
        <div class="transformation-rule">
          <span class="badge">${esc(item.rule_label)}</span>
          <span class="transformation-field">${esc(item.field)}</span>
        </div>
        <div class="transformation-values">
          <div class="transformation-before"><strong>Было:</strong> ${esc(item.before || "∅")}</div>
          <div class="transformation-after"><strong>Стало:</strong> ${esc(item.after || "∅")}</div>
        </div>
      </div>
    `).join("")}</div>`;
  }

  function renderKeyValueGrid(containerId, values) {
    const node = byId(containerId);
    if (!node) return;
    const entries = Object.entries(values || {});
    if (!entries.length) {
      node.innerHTML = '<div class="section-caption">Нет данных для отображения.</div>';
      return;
    }
    node.innerHTML = entries.map(([key, value]) => `
      <div class="attr-item">
        <div class="attr-key">${esc(key)}</div>
        <div class="attr-value">${esc(value)}</div>
      </div>
    `).join("");
  }

  function renderLineCollection(containerId, lines, fallbackValues) {
    const node = byId(containerId);
    if (!node) return;
    if (Array.isArray(lines) && lines.length > 1) {
      node.innerHTML = lines.map((line, index) => `
        <div class="source-line-card">
          <div class="source-line-title">Исходная строка ${index + 1}</div>
          <div class="attr-grid attr-grid-raw">
            ${Object.entries(line || {}).map(([key, value]) => `
              <div class="attr-item">
                <div class="attr-key">${esc(key)}</div>
                <div class="attr-value">${esc(value)}</div>
              </div>
            `).join("")}
          </div>
        </div>
      `).join("");
      return;
    }
    renderKeyValueGrid(containerId, fallbackValues || (lines && lines[0]) || {});
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

  function resetAllFilters(rerender = true) {
    Object.keys(state.filters).forEach((field) => { state.filters[field] = ""; });
    state.search = "";
    state.page = 1;
    state.breadcrumb = [];
    const search = byId("detail-search");
    if (search) search.value = "";
    syncSelectValues();
    if (rerender) rerenderAll();
  }

  function toggleSort(key) {
    if (state.sortKey === key) {
      state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
    } else {
      state.sortKey = key;
      state.sortDirection = key === "amount" ? "desc" : "asc";
    }
    loadDetailTable();
  }

  function exportCurrentSelectionToCsv() {
    const url = `${apiBaseUrl}/export.csv?${buildQueryParams(false).toString()}`;
    window.open(url, "_blank");
  }

  function buildQueryParams(includePaging = true) {
    const params = new URLSearchParams();
    Object.entries(state.filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    if (state.search) params.set("search", state.search);
    params.set("sort_key", state.sortKey);
    params.set("sort_direction", state.sortDirection);
    if (includePaging) {
      params.set("page", String(state.page));
      params.set("page_size", String(state.pageSize));
    }
    return params;
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

  function flattenL1Categories(nodes) {
    return (nodes || []).map((node) => ({ id: node.id, label: node.label, total_amount: Number(node.total_amount || 0) })).sort((a, b) => b.total_amount - a.total_amount);
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
      margin: { l: 32, r: 14, t: 20, b: 24 },
      title: title ? { text: title, font: { size: 15 } } : undefined,
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      xaxis: amountAxisTemplate,
      yaxis: amountAxisTemplate,
      legend: { orientation: "h" },
    };
  }

  function statusLabel(value) {
    return statusLabels[value] || value;
  }

  function slug(value) {
    const rawValue = String(value || "").trim().toLowerCase();
    const transliterated = Array.from(rawValue).map((char) => cyrillicToLatin[char] ?? char).join("");
    return transliterated
      .normalize("NFKD")
      .replace(/[^\w\s-]/g, "")
      .replace(/[^0-9a-z]+/g, "_")
      .replace(/^_+|_+$/g, "") || "unknown";
  }

  function formatKpiValue(kpi) {
    if (typeof kpi.value === "string") return kpi.value;
    if (String(kpi.id || "").includes("amount")) return `${formatThousandsNumber(kpi.value / 1000)} тыс. руб.`;
    return new Intl.NumberFormat("ru-RU").format(Number(kpi.value || 0));
  }

  function formatAmountThousands(value) {
    return `${formatThousandsNumber(toThousands(value))} тыс. руб.`;
  }

  function formatThousandsNumber(value) {
    return new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value || 0));
  }

  function formatPercent(value) {
    return new Intl.NumberFormat("ru-RU", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(value || 0));
  }

  function formatSignedThousands(value) {
    const sign = Number(value || 0) >= 0 ? "+" : "−";
    return `${sign}${formatThousandsNumber(Math.abs(toThousands(value)))} тыс. руб.`;
  }

  function toThousands(value) {
    return Number(value || 0) / 1000;
  }

  function setText(id, value) {
    const node = byId(id);
    if (node) node.textContent = value || "";
  }

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function escAttr(value) {
    return esc(value).replace(/"/g, "&quot;");
  }
})();
