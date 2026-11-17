/* ==========================================================================
   enter.js - draws the two charts on the "Enter your numbers" page.

   * A pie chart: how the buyers are spread across Most, Regular and Least.
   * A bar chart: every number the owner typed, side by side, with the number
     printed on each bar.

   Colours come from the CSS variables in styles.css, so both charts follow
   the light / dark switch without any extra code.
   ========================================================================== */

(function () {
  "use strict";

  // Read one colour from the stylesheet. That keeps every chart in step with
  // the rest of the dashboard.
  function cssVar(name, fallback) {
    const value = getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
    return value || fallback;
  }

  function themeTokens() {
    return {
      text: cssVar("--chart-text", "#475569"),
      textStrong: cssVar("--chart-text-strong", "#1e293b"),
      grid: cssVar("--chart-grid", "rgba(71,85,105,0.16)"),
      sliceBorder: cssVar("--chart-slice-border", "#ffffff"),
      tooltipBg: cssVar("--chart-tooltip-bg", "#1e293b"),
      tooltipText: cssVar("--chart-tooltip-text", "#f1f5f9"),
    };
  }

  // Which colour each box uses. These are the same CSS variables as the cards
  // and the badges on the results page.
  const CARD_VARS = {
    total: "--seg-champions",
    most: "--seg-champions-2",
    regular: "--seg-loyal",
    least: "--seg-hibernating-2",
    frequent: "--seg-fallback",
    last_month: "--seg-hibernating",
    big_spenders: "--seg-fallback-2",
  };

  // The pie shows "how many buyers are in each group", so it uses the three
  // strong, evenly spaced colours rather than the pale ones. Blue, teal and
  // amber read clearly side by side and all three hold white text.
  const PIE_VARS = {
    most: "--seg-champions-2",
    regular: "--seg-loyal",
    least: "--seg-hibernating-2",
  };

  const PIE_LABEL_COLOUR = "#ffffff";
  const PIE_LABEL_FONT = "Inter, system-ui, sans-serif";

  function colourFor(key) {
    return cssVar(CARD_VARS[key] || "--seg-fallback", "#475569");
  }

  function pieColourFor(key) {
    return cssVar(PIE_VARS[key] || CARD_VARS[key] || "--seg-fallback", "#475569");
  }

  // 1000 -> "1,000"
  const comma = (n) => new Intl.NumberFormat("en-US").format(Number(n) || 0);

  const charts = [];
  // `data` is the results object built by the server: { total, numbers, cards,
  // percentages, sentences }.
  let data = null;

  const prefersReducedMotion =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ------------------------------------------------------------------
  // The pie chart
  // ------------------------------------------------------------------
  function drawPie() {
    const canvas = document.getElementById("chart-entry-pie");
    if (!canvas) return;

    const t = themeTokens();
    const numbers = data.numbers || {};
    const total = data.total || 0;

    // The three order groups. We only show the ones that are filled in.
    const groups = [
      { key: "most", label: "Most buyers" },
      { key: "regular", label: "Regular buyers" },
      { key: "least", label: "Least buyers" },
    ].filter((g) => numbers[g.key] !== undefined);

    charts.push(
      new Chart(canvas, {
        type: "doughnut",
        data: {
          labels: groups.map((g) => g.label),
          datasets: [
            {
              data: groups.map((g) => numbers[g.key] || 0),
              backgroundColor: groups.map((g) => pieColourFor(g.key)),
              borderColor: t.sliceBorder,
              borderWidth: 2,
            },
          ],
        },
        // Writes each number inside its own slice. The size is chosen for that
        // slice alone, and a label that still cannot fit moves outside the pie
        // on a short line. Nothing is ever cut in half.
        plugins: [
          { id: "pieSliceLabels", afterDatasetsDraw: drawSliceLabels },
        ],
        options: {
          // Room so a label placed outside the pie is not clipped by the box.
          layout: { padding: 40 },
          responsive: true,
          maintainAspectRatio: false,
          animation: prefersReducedMotion ? false : { duration: 450 },
          cutout: "52%",
          plugins: {
            // The legend spells out every group name and its percentage, so
            // the chart still makes sense without seeing the colours.
            legend: {
              position: "bottom",
              labels: {
                color: t.textStrong,
                font: { family: "Inter, system-ui, sans-serif", size: 13, weight: "500" },
                usePointStyle: true,
                pointStyle: "circle",
                padding: 14,
                generateLabels(chart) {
                  const values = chart.data.datasets[0].data;
                  return chart.data.labels.map((label, i) => ({
                    text: `${label} - ${percentOf(values[i], total)}%`,
                    fillStyle: chart.data.datasets[0].backgroundColor[i],
                    strokeStyle: chart.data.datasets[0].backgroundColor[i],
                    lineWidth: 0,
                    index: i,
                    pointStyle: "circle",
                  }));
                },
              },
            },
            tooltip: {
              backgroundColor: t.tooltipBg,
              titleColor: t.tooltipBg,
              bodyColor: t.tooltipText,
              padding: 10,
              cornerRadius: 8,
              callbacks: {
                label(ctx) {
                  const value = Number(ctx.raw) || 0;
                  return ` ${comma(value)} buyers (${percentOf(value, total)}%)`;
                },
              },
            },
          },
        },
      })
    );
  }

  // 233 out of 1000 -> "23.3"
  function percentOf(value, total) {
    if (!total) return "0";
    return (Math.round((Number(value) * 1000) / total) / 10).toString();
  }

  // ------------------------------------------------------------------
  // Numbers written on the pie slices
  // ------------------------------------------------------------------
  // Each label is sized for its own slice: as large as that slice allows, down
  // to 8px, and if even that is too tight it moves outside the pie on a short
  // line. A number is never drawn half over a slice edge or half off the chart.
  function drawSliceLabels(chart) {
    const slices = chart.getDatasetMeta(0).data;
    if (!slices.length) return;

    const { ctx, chartArea } = chart;
    const values = chart.data.datasets[0].data;
    const outer = slices[0].outerRadius;
    const inner = slices[0].innerRadius;
    const cx = slices[0].x;
    const cy = slices[0].y;

    // The space a label has: across the ring, and along its slice.
    const ringRoom = outer - inner - 10;
    const midRadius = (inner + outer) / 2;

    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = PIE_LABEL_COLOUR;

    slices.forEach((slice, i) => {
      if (!chart.getDataVisibility(i)) return;

      const text = comma(values[i]);
      const angleSpan = Math.abs(slice.endAngle - slice.startAngle);
      const alongRoom = midRadius * angleSpan - 10;
      const mid = (slice.startAngle + slice.endAngle) / 2;
      const dx = Math.cos(mid);
      const dy = Math.sin(mid);

      // The largest size that fits both ways, or 0 if none does.
      let size = 0;
      for (const candidate of [15, 14, 13, 12, 11, 10, 9, 8]) {
        ctx.font = `700 ${candidate}px ${PIE_LABEL_FONT}`;
        if (
          ctx.measureText(text).width <= alongRoom &&
          candidate + 3 <= ringRoom
        ) {
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

      ctx.strokeStyle = PIE_LABEL_COLOUR;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(cx + dx * (outer + 5), cy + dy * (outer + 5));
      ctx.lineTo(cx + dx * (outer + 14), cy + dy * (outer + 14));
      ctx.lineTo(endX, endY);
      ctx.stroke();

      // Point the text away from the pie, and keep it inside the chart box.
      ctx.font = `700 13px ${PIE_LABEL_FONT}`;
      const align = dx < -0.15 ? "right" : dx > 0.15 ? "left" : "center";
      ctx.textAlign = align;
      const textX = endX + (align === "right" ? -4 : align === "left" ? 4 : 0);
      const textY = Math.min(Math.max(endY, chartArea.top + 8), chartArea.bottom - 8);
      ctx.fillText(text, textX, textY);
      ctx.textAlign = "center";
    });

    ctx.restore();
  }

  // ------------------------------------------------------------------
  // The bar chart
  // ------------------------------------------------------------------
  function drawBar() {
    const canvas = document.getElementById("chart-entry-bar");
    if (!canvas) return;

    const t = themeTokens();
    const cards = data.cards || [];

    charts.push(
      new Chart(canvas, {
        type: "bar",
        data: {
          labels: cards.map((c) => c.label),
          datasets: [
            {
              data: cards.map((c) => c.number),
              backgroundColor: cards.map((c) => colourFor(c.key)),
              borderRadius: 6,
              borderSkipped: false,
              maxBarThickness: 34,
            },
          ],
        },
        options: {
          indexAxis: "y",           // bars run left to right: the names fit better
          responsive: true,
          maintainAspectRatio: false,
          animation: prefersReducedMotion ? false : { duration: 450 },
          layout: { padding: { right: 28 } },
          scales: {
            x: {
              beginAtZero: true,
              grid: { color: t.grid, drawBorder: false },
              title: {
                display: true,
                text: "Number of buyers",
                color: t.text,
                font: { family: "Inter, system-ui, sans-serif", size: 12, weight: "500" },
              },
              ticks: {
                color: t.text,
                font: { family: "Inter, system-ui, sans-serif", size: 12 },
                callback: (value) => comma(value),
              },
            },
            y: {
              grid: { display: false, drawBorder: false },
              ticks: {
                color: t.textStrong,
                font: { family: "Inter, system-ui, sans-serif", size: 12.5, weight: "500" },
              },
            },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: t.tooltipBg,
              titleColor: t.tooltipBg,
              bodyColor: t.tooltipText,
              padding: 10,
              cornerRadius: 8,
              displayColors: false,
              callbacks: { label: (ctx) => `${comma(ctx.raw)} buyers` },
            },
          },
        },
        // A small custom plugin writes each bar's value beside the bar.
        plugins: [
          {
            id: "barValueLabels",
            afterDatasetsDraw(chart) {
              const { ctx } = chart;
              const meta = chart.getDatasetMeta(0);
              ctx.save();
              ctx.fillStyle = t.textStrong;
              ctx.font = "600 12.5px Inter, system-ui, sans-serif";
              ctx.textBaseline = "middle";
              meta.data.forEach((bar, i) => {
                const value = chart.data.datasets[0].data[i];
                ctx.fillText(comma(value), bar.x + 6, bar.y);
              });
              ctx.restore();
            },
          },
        ],
      })
    );
  }

  // ------------------------------------------------------------------
  // Redraw everything after a theme change
  // ------------------------------------------------------------------
  function redraw() {
    charts.forEach((chart) => chart.destroy());
    charts.length = 0;
    drawPie();
    drawBar();
  }

  document.addEventListener("DOMContentLoaded", () => {
    const holder = document.getElementById("entry-data");
    if (!holder) return;

    try {
      data = JSON.parse(holder.textContent);
    } catch (err) {
      return;
    }
    if (!data || !data.cards) return;

    drawPie();
    drawBar();

    // The theme switch in theme.js fires this event, so the charts can
    // pick up the new colours straight away.
    document.addEventListener("themechange", redraw);
  });
})();
