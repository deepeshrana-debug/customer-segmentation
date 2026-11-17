/* ==========================================================================
   Customer Segmentation Dashboard - front-end logic

   Responsibilities
   ----------------
   1. Fetch /api/data once, which returns BOTH result sets (k = 2 and k = 4).
   2. Render summary cards, two pie charts, three bar charts and the table.
   3. Swap between result sets when the toggle is clicked.
   4. Toggle dark mode, remembering the choice in localStorage.
   5. Re-colour the charts when the theme changes.

   No frameworks, no build step: plain DOM + Chart.js (already loaded in the
   <script> tag in index.html).
   ========================================================================== */

(function () {
  "use strict";

  // ---------------------------------------------------------------------
  // Colour palette
  // ---------------------------------------------------------------------
  // Segment colours are NOT hard-coded here. Each name maps to the CSS
  // variable that holds its colour, and the value is read from the stylesheet
  // with getComputedStyle. That keeps one source of truth: change --seg-champions
  // in styles.css and the charts, legends and badges all update together.
  const SEGMENT_VARS = {
    "champions": "--seg-champions",
    "loyal customers": "--seg-loyal",
    "loyal": "--seg-loyal",
    "champions 2": "--seg-champions-2",
    "hibernating 2": "--seg-hibernating-2",
    "hibernating": "--seg-hibernating",
  };

  // Names the pipeline may produce in other runs (e.g. "Promising / New").
  const FALLBACK_VARS = ["--seg-fallback", "--seg-fallback-2", "--seg-fallback-3"];

  // ---------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------
  let payload = null;          // everything from /api/data
  let activeId = null;         // "k2" or "k4"
  const charts = {};           // chart instances, keyed by canvas id

  // ---------------------------------------------------------------------
  // Theme helpers
  // ---------------------------------------------------------------------
  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") || "light";
  }

  /**
   * Read one CSS custom property from the document.
   * Falls back to the given default when the variable is missing.
   */
  function cssVar(name, fallback) {
    const value = getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
    return value || fallback;
  }

  function themeTokens() {
    return {
      isDark: currentTheme() === "dark",
      // Every chart colour comes from a CSS variable, so the charts follow
      // whatever the stylesheet says for the current theme.
      text: cssVar("--chart-text", "#475569"),
      textStrong: cssVar("--chart-text-strong", "#1e293b"),
      grid: cssVar("--chart-grid", "rgba(71,85,105,0.16)"),
      sliceBorder: cssVar("--chart-slice-border", "#ffffff"),
      tooltipBg: cssVar("--chart-tooltip-bg", "#1e293b"),
      tooltipText: cssVar("--chart-tooltip-text", "#f1f5f9"),
    };
  }

  // Resolve a segment name to the CSS variable that holds its colour.
  // Matching is case-insensitive and trimmed so "Champions " works too.
  function colorVarFor(segmentName) {
    const key = String(segmentName).trim().toLowerCase();
    if (SEGMENT_VARS[key]) return SEGMENT_VARS[key];

    // Unknown name: pick a fallback deterministically from the name itself
    // so the same segment always gets the same colour.
    let hash = 0;
    for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) | 0;
    return FALLBACK_VARS[Math.abs(hash) % FALLBACK_VARS.length];
  }

  // The actual colour string for a segment, resolved for the current theme.
  function colorValue(segmentName) {
    const varName = colorVarFor(segmentName);
    return cssVar(varName, cssVar("--seg-fallback", "#475569"));
  }

  // ---------------------------------------------------------------------
  // Number formatting
  // ---------------------------------------------------------------------
  const nf0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  const nf2 = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  // 58271 -> "58,271"
  const fmtInt = (n) => nf0.format(Number(n) || 0);

  // 12802.8 -> "12,802.80"  (money: 2 decimals + thousands separators)
  const fmtMoney = (n) => nf2.format(Number(n) || 0);

  // 28.95 -> "29.0"        (days / averages: 1 decimal)
  const fmtOne = (n) => nf1.format(Number(n) || 0);

  // 97.8 -> "97.8%"
  const fmtPct = (n) => nf1.format(Number(n) || 0) + "%";

  // Large money for the summary card: "$1.24M" style keeps the card tidy.
  function fmtMoneyCompact(n) {
    const v = Number(n) || 0;
    if (v >= 1e9) return "$" + nf2.format(v / 1e9) + "B";
    if (v >= 1e6) return "$" + nf2.format(v / 1e6) + "M";
    if (v >= 1e3) return "$" + nf2.format(v / 1e3) + "K";
    return "$" + nf2.format(v);
  }

  // ---------------------------------------------------------------------
  // Charts
  // ---------------------------------------------------------------------
  const prefersReducedMotion =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function destroyChart(id) {
    if (charts[id]) {
      charts[id].destroy();
      delete charts[id];
    }
  }

  /**
   * Repaint every chart for the current theme WITHOUT rebuilding it.
   * We re-read the CSS variables and push them onto the existing chart
   * config, then call chart.update() as the brief asks.
   */
  function recolourCharts() {
    const t = themeTokens();

    Object.entries(charts).forEach(([id, chart]) => {
      const opts = chart.options;

      // --- Grid, axis titles and tick labels -----------------------------
      if (opts.scales) {
        Object.values(opts.scales).forEach((scale) => {
          if (scale.grid) scale.grid.color = t.grid;
          if (scale.ticks) scale.ticks.color = scale.id === "y" ? t.textStrong : t.text;
          if (scale.title) scale.title.color = t.text;
        });
      }

      // --- Pie legend names and the slice separators ---------------------
      if (opts.plugins && opts.plugins.legend && opts.plugins.legend.labels) {
        opts.plugins.legend.labels.color = t.textStrong;
        if (chart.data.datasets[0]) chart.data.datasets[0].borderColor = t.sliceBorder;
      }

      // --- Tooltip colours -----------------------------------------------
      const tip = opts.plugins && opts.plugins.tooltip;
      if (tip) {
        tip.backgroundColor = t.tooltipBg;
        tip.titleColor = t.tooltipBg;
        tip.bodyColor = t.tooltipText;
      }

      // --- Bar fills and pie slices --------------------------------------
      // Colours come from CSS, so every dataset is re-read per theme.
      chart.data.labels.forEach((label, i) => {
        const colour = colorValue(label);
        chart.data.datasets.forEach((ds) => {
          if (ds.backgroundColor && ds.backgroundColor.length !== undefined) {
            ds.backgroundColor[i] = colour;
          } else {
            ds.backgroundColor = colour;
          }
        });
      });

      chart.update();
    });
  }

  /**
   * Writes each number inside its own slice. The size is chosen for that slice
   * alone, and a label that still cannot fit moves outside the pie on a short
   * line, so a number is never cut in half.
   */
  function drawSliceLabels(chart, formatValue) {
    const slices = chart.getDatasetMeta(0).data;
    if (!slices.length) return;

    const { ctx, chartArea } = chart;
    const values = chart.data.datasets[0].data;
    const outer = slices[0].outerRadius;
    const inner = slices[0].innerRadius;
    const cx = slices[0].x;
    const cy = slices[0].y;
    const font = "Inter, system-ui, sans-serif";
    const colour = cssVar("--chart-slice-label", "#ffffff");

    // The space a label has: across the ring, and along its slice.
    const ringRoom = outer - inner - 10;
    const midRadius = (inner + outer) / 2;

    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = colour;

    slices.forEach((slice, i) => {
      if (!chart.getDataVisibility(i)) return;

      const text = formatValue(values[i]);
      const angleSpan = Math.abs(slice.endAngle - slice.startAngle);
      const alongRoom = midRadius * angleSpan - 10;
      const mid = (slice.startAngle + slice.endAngle) / 2;
      const dx = Math.cos(mid);
      const dy = Math.sin(mid);

      // The largest size that fits both ways, or 0 if none does.
      let size = 0;
      for (const candidate of [15, 14, 13, 12, 11, 10, 9, 8]) {
        ctx.font = `700 ${candidate}px ${font}`;
        if (ctx.measureText(text).width <= alongRoom && candidate + 3 <= ringRoom) {
          size = candidate;
          break;
        }
      }

      if (size) {
        ctx.fillText(text, cx + dx * midRadius, cy + dy * midRadius);
        return;
      }

      // Too tight inside: outside the pie, at the end of a short line.
      const endX = cx + dx * (outer + 30);
      const endY = cy + dy * (outer + 30);

      ctx.strokeStyle = colour;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(cx + dx * (outer + 5), cy + dy * (outer + 5));
      ctx.lineTo(cx + dx * (outer + 14), cy + dy * (outer + 14));
      ctx.lineTo(endX, endY);
      ctx.stroke();

      // Point the text away from the pie, and keep it inside the chart box.
      ctx.font = `700 13px ${font}`;
      const align = dx < -0.15 ? "right" : dx > 0.15 ? "left" : "center";
      ctx.textAlign = align;
      const textX = endX + (align === "right" ? -4 : align === "left" ? 4 : 0);
      const textY = Math.min(Math.max(endY, chartArea.top + 8), chartArea.bottom - 8);
      ctx.fillText(text, textX, textY);
      ctx.textAlign = "center";
    });

    ctx.restore();
  }

  /**
   * Pie / doughnut chart of a share column.
   *
   * @param {string} canvasId  id of the <canvas>
   * @param {Array}  segs      segment rows
   * @param {string} valueKey  "customers" or "revenue_share"
   * @param {string} totalFor  key whose sum is the 100% base
   */
  function renderPie(canvasId, segs, valueKey) {
    destroyChart(canvasId);
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const t = themeTokens();
    const labels = segs.map((s) => s.segment);
    const values = segs.map((s) => Number(s[valueKey]) || 0);
    const colors = segs.map((s) => colorValue(s.segment));

    // Work out percentages from whichever column we are plotting.
    // For customers: share of the total customer count.
    // For revenue: the CSV already stores the share, so use it directly.
    const total = values.reduce((a, b) => a + b, 0) || 1;

    charts[canvasId] = new Chart(canvas, {
      type: "doughnut", // a doughnut reads better than a solid pie (centre room for the total)
      data: {
        labels,
        datasets: [
          {
            data: values,
            backgroundColor: colors,
            borderColor: t.sliceBorder,
            borderWidth: 2,
            hoverOffset: 6,
          },
        ],
      },
      // The number is written on its own slice.
      plugins: [
        {
          id: "pieSliceLabels",
          afterDatasetsDraw(chart) {
            drawSliceLabels(chart, (value) =>
              valueKey === "customers" ? fmtInt(value) : fmtPct(value)
            );
          },
        },
      ],
      options: {
        responsive: true,          // resize with the container -> works on phones
        maintainAspectRatio: false, // height is controlled by CSS
        animation: prefersReducedMotion ? false : { duration: 450 },
        cutout: "52%",
        // Room so a label placed outside the pie is not clipped by the box.
        layout: { padding: 40 },
        plugins: {
          // Legend with the segment name and its percentage.
          legend: {
            position: "bottom",
            align: "center",
            labels: {
              color: t.textStrong,
              font: { family: "Inter, system-ui, sans-serif", size: 12.5, weight: "500" },
              boxWidth: 10,
              boxHeight: 10,
              usePointStyle: true,
              pointStyle: "circle",
              padding: 14,
              // Legend text: "Champions — 58.4%"
              generateLabels(chart) {
                const data = chart.data;
                return data.labels.map((label, i) => {
                  const raw = Number(data.datasets[0].data[i]) || 0;
                  const pct = (raw / total) * 100;
                  return {
                    text: `${label} — ${fmtPct(pct)}`,
                    fillStyle: data.datasets[0].backgroundColor[i],
                    strokeStyle: data.datasets[0].backgroundColor[i],
                    lineWidth: 0,
                    hidden: !chart.getDataVisibility(i),
                    index: i,
                    pointStyle: "circle",
                  };
                });
              },
            },
          },
          tooltip: {
            backgroundColor: t.tooltipBg,
            titleColor: t.tooltipBg,
            bodyColor: t.tooltipText,
            padding: 10,
            cornerRadius: 8,
            displayColors: true,
            boxPadding: 4,
            callbacks: {
              // Tooltip: name, raw value and percentage.
              label(ctx) {
                const raw = Number(ctx.raw) || 0;
                const pct = (raw / total) * 100;
                const rawText =
                  valueKey === "customers"
                    ? `${fmtInt(raw)} buyers`
                    : `${fmtPct(raw)} of spend`;
                return ` ${rawText} (${fmtPct(pct)} of ${valueKey === "customers" ? "buyers" : "spend"})`;
              },
            },
          },
        },
      },
    });
  }

  /**
   * Horizontal bar chart for one RFM measure.
   * Horizontal bars keep long segment names readable on a narrow card.
   *
   * @param {string} canvasId id of the <canvas>
   * @param {Array}  segs     segment rows
   * @param {string} key      "recency" | "frequency" | "monetary"
   * @param {string} axisTitle label for the value axis
   * @param {Function} format value formatter for ticks and tooltips
   */
  function renderBar(canvasId, segs, key, axisTitle, format) {
    destroyChart(canvasId);
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const t = themeTokens();
    // Sort descending so the longest bar is on top: easiest to compare.
    const ordered = segs.slice().sort((a, b) => (b[key] || 0) - (a[key] || 0));

    charts[canvasId] = new Chart(canvas, {
      type: "bar",
      data: {
        labels: ordered.map((s) => s.segment),
        datasets: [
          {
            label: axisTitle,
            data: ordered.map((s) => Number(s[key]) || 0),
            backgroundColor: ordered.map((s) => colorValue(s.segment)),
            borderRadius: 6,       // rounded corners to match the card style
            borderSkipped: false,
            maxBarThickness: 34,
          },
        ],
      },
      options: {
        indexAxis: "y", // horizontal bars
        responsive: true,
        maintainAspectRatio: false,
        animation: prefersReducedMotion ? false : { duration: 450 },
        layout: { padding: { top: 4, right: 12 } },
        scales: {
          x: {
            beginAtZero: true,
            grid: { color: t.grid, drawBorder: false },
            // Axis title makes the units unambiguous (days / orders / money)
            title: {
              display: true,
              text: axisTitle,
              color: t.text,
              font: { family: "Inter, system-ui, sans-serif", size: 11.5, weight: "500" },
            },
            ticks: {
              color: t.text,
              font: { family: "Inter, system-ui, sans-serif", size: 11.5 },
              maxTicksLimit: 6,
              callback: (value) => format(value),
            },
          },
          y: {
            grid: { display: false, drawBorder: false },
            ticks: {
              color: t.textStrong,
              font: { family: "Inter, system-ui, sans-serif", size: 12, weight: "500" },
              // Truncate very long names rather than shrinking the plot area
              callback(value) {
                const label = this.getLabelForValue(value);
                return label.length > 18 ? label.slice(0, 17) + "…" : label;
              },
            },
          },
        },
        plugins: {
          legend: { display: false }, // one series only: the axis title is enough
          tooltip: {
            backgroundColor: t.tooltipBg,
            titleColor: t.tooltipBg,
            bodyColor: t.tooltipText,
            padding: 10,
            cornerRadius: 8,
            displayColors: false,
            callbacks: {
              label(ctx) {
                return format(ctx.raw);
              },
            },
          },
        },
      },
    });
  }

  // ---------------------------------------------------------------------
  // Cards + table
  // ---------------------------------------------------------------------
  function renderSummary(data) {
    const s = data.summary;
    document.getElementById("stat-customers").textContent = fmtInt(s.total_customers);

    // Show the compact form in the card and the exact amount on hover.
    const revEl = document.getElementById("stat-revenue");
    revEl.textContent = fmtMoneyCompact(s.total_revenue);
    revEl.title = "$" + fmtMoney(s.total_revenue);

    document.getElementById("stat-segments").textContent = fmtInt(s.segment_count);
    document.getElementById("stat-top-share").textContent = fmtPct(s.top_segment_share);
    document.getElementById("stat-top-name").textContent = s.top_segment;
  }

  function renderTable(data) {
    const tbody = document.getElementById("segment-table-body");
    const total = data.summary.total_customers || 1;
    tbody.innerHTML = "";

    data.segments.forEach((s) => {
      const shareOfBase = (s.customers / total) * 100;
      const tr = document.createElement("tr");

      // Segment name as a coloured badge. The colour is passed through a CSS
      // custom property so the palette lives in one place (app.js).
      const nameCell = document.createElement("td");
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.style.setProperty("--badge", colorValue(s.segment));
      badge.textContent = s.segment;
      nameCell.appendChild(badge);
      tr.appendChild(nameCell);

      // Numeric cells: right-aligned, tabular numerals, formatted per the spec.
      const cells = [
        { text: fmtInt(s.customers) },            // thousands separator
        { text: fmtPct(shareOfBase) },            // percentage with %
        { text: fmtOne(s.recency) + " d" },       // days, 1 decimal
        { text: fmtOne(s.frequency) },            // average, 1 decimal
        { text: "$" + fmtMoney(s.monetary), strong: true }, // money, 2 decimals
        { text: fmtPct(s.revenue_share) },
      ];

      cells.forEach((c) => {
        const td = document.createElement("td");
        td.className = "num" + (c.strong ? " strong" : "");
        td.textContent = c.text;
        tr.appendChild(td);
      });

      tbody.appendChild(tr);
    });
  }

  // ---------------------------------------------------------------------
  // Rendering a whole result set
  // ---------------------------------------------------------------------
  function renderResultSet(id) {
    const data = payload && payload[id];
    if (!data) return;

    activeId = id;

    // Missing folder: show the banner, clear the page.
    const banner = document.getElementById("missing-banner");
    if (!data.available) {
      banner.hidden = false;
      banner.innerHTML =
        "No results in <code>" + data.folder + "/</code> yet. Make them with " +
        "<code>python src/main.py --k 4 --out " + data.folder + "</code>, then reload this page.";
      document.getElementById("stat-customers").textContent = "—";
      document.getElementById("stat-revenue").textContent = "—";
      document.getElementById("stat-segments").textContent = "—";
      document.getElementById("stat-top-share").textContent = "—";
      document.getElementById("stat-top-name").textContent = "";
      document.getElementById("segment-table-body").innerHTML = "";
      ["chart-customers", "chart-revenue", "chart-recency", "chart-frequency", "chart-monetary"]
        .forEach(destroyChart);
      return;
    }

    banner.hidden = true;

    // --- Header note (which k, how it was chosen) -------------------------
    const meta = (window.__RESULT_META__ || []).find((m) => m.id === id);
    const noteEl = document.getElementById("result-note");
    if (meta) {
      noteEl.textContent =
        `Showing ${meta.label} — ${meta.note.toLowerCase()} · reading from ${data.folder}/`;
    }

    const segs = data.segments;

    renderSummary(data);
    renderTable(data);

    // Two pies: customer share and revenue share.
    renderPie("chart-customers", segs, "customers");
    renderPie("chart-revenue", segs, "revenue_share");

    // Three small-multiple bar charts (different scales -> separate axes).
    // Labels use the full name and units, in plain words.
    renderBar("chart-recency", segs, "recency", "Average days since last purchase", (v) => fmtOne(v) + " days");
    renderBar("chart-frequency", segs, "frequency", "Average number of orders", (v) => fmtOne(v));
    renderBar("chart-monetary", segs, "monetary", "Average spend per buyer ($)", (v) => "$" + fmtMoney(v));
  }

  // ---------------------------------------------------------------------
  // Theme
  // ---------------------------------------------------------------------
  function applyTheme(theme, { redraw = true } = {}) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("segmentation-theme", theme);

    const btn = document.getElementById("theme-toggle");
    btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    document.getElementById("theme-label").textContent = theme === "dark" ? "Light" : "Dark";

    // Charts read their colours from the CSS variables, so after the theme
    // attribute flips we just re-read the variables and call chart.update().
    // No rebuild, so no flicker and no lost animations.
    if (redraw) recolourCharts();
  }

  function initTheme() {
    const stored = localStorage.getItem("segmentation-theme");
    const systemDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    const theme = stored || (systemDark ? "dark" : "light");
    applyTheme(theme, { redraw: false });

    // If the user has not picked a theme, follow the OS when it changes.
    if (!stored && window.matchMedia) {
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (event) => {
        applyTheme(event.matches ? "dark" : "light");
      });
    }
  }

  // ---------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------
  async function boot() {
    initTheme();

    // Dark mode button
    document.getElementById("theme-toggle").addEventListener("click", () => {
      applyTheme(currentTheme() === "dark" ? "light" : "dark");
    });

    // Fetch both result sets in one request.
    let data;
    try {
      const res = await fetch("/api/data", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      data = await res.json();
    } catch (err) {
      document.getElementById("result-note").textContent =
        "Could not load results from the server (" + err.message + ").";
      return;
    }
    payload = data;

    // Default to the first result set that actually has data.
    const firstAvailable = Object.keys(payload).find((k) => payload[k].available);
    const initialId = firstAvailable || Object.keys(payload)[0];

    // Wire the k toggle.
    const buttons = Array.from(document.querySelectorAll(".toggle-btn"));
    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        buttons.forEach((b) => b.setAttribute("aria-pressed", "false"));
        btn.setAttribute("aria-pressed", "true");
        renderResultSet(btn.dataset.resultId);
      });
    });
    buttons.forEach((b) => {
      b.setAttribute("aria-pressed", b.dataset.resultId === initialId ? "true" : "false");
    });

    renderResultSet(initialId);

    // Chart.js handles canvas resizing itself, but the container height can
    // change when the window crosses a CSS breakpoint. A debounced resize
    // keeps everything sharp.
    let resizeTimer = null;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        Object.values(charts).forEach((chart) => {
          if (chart && typeof chart.resize === "function") chart.resize();
        });
      }, 150);
    });
  }

  // Expose the result-set metadata that the template rendered server-side.
  document.addEventListener("DOMContentLoaded", () => {
    const metaEl = document.getElementById("result-meta");
    if (metaEl) {
      try {
        window.__RESULT_META__ = JSON.parse(metaEl.textContent);
      } catch (e) {
        window.__RESULT_META__ = [];
      }
    }
    boot();
  });
})();
