/* ===================================================
   The Quantum Qanary — Dashboard Logic
   ES5-compatible. No arrow functions, const, let, or template literals.
   =================================================== */

(function () {
  "use strict";

  var DATA_BASE = "data/";
  var LEVEL_COLORS = {
    GREEN: "#22c55e",
    YELLOW: "#eab308",
    ORANGE: "#f97316",
    RED: "#ef4444"
  };

  var COMPONENT_COLORS = [
    "#06b6d4",
    "#8b5cf6",
    "#f97316",
    "#22c55e",
    "#ef4444",
    "#eab308"
  ];

  // ─────────────────────────────────────────
  // Utility helpers
  // ─────────────────────────────────────────
  function fetchJSON(path) {
    return fetch(DATA_BASE + path).then(function (r) {
      if (!r.ok) throw new Error("Failed to load " + path);
      return r.json();
    });
  }

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str || ""));
    return div.innerHTML;
  }

  function formatStatus(s) {
    return (s || "").replace(/_/g, " ");
  }

  // ─────────────────────────────────────────
  // Data loading
  // ─────────────────────────────────────────
  var dataPromises = {
    alerts: fetchJSON("alerts/status.json"),
    factoring: fetchJSON("factoring/records.json"),
    hardware: fetchJSON("hardware/qubit_records.json"),
    adoption: fetchJSON("adoption/pqc_deployments.json"),
    blockchain: fetchJSON("blockchain/pqc_status.json"),
    funding: fetchJSON("funding/investments.json"),
    qday: fetchJSON("composite/qday_distance.json"),
    milestones: fetchJSON("milestones/timeline.json"),
    arxiv: fetchJSON("arxiv/processed/paper_counts.json").catch(function () { return null; }),
    divincenzo: fetchJSON("hardware/divincenzo.json").catch(function () { return null; })
  };

  // Load all data then render
  Promise.all([
    dataPromises.alerts,
    dataPromises.factoring,
    dataPromises.hardware,
    dataPromises.adoption,
    dataPromises.blockchain,
    dataPromises.funding,
    dataPromises.qday,
    dataPromises.milestones,
    dataPromises.arxiv,
    dataPromises.divincenzo
  ]).then(function (results) {
    var data = {
      alerts: results[0],
      factoring: results[1],
      hardware: results[2],
      adoption: results[3],
      blockchain: results[4],
      funding: results[5],
      qday: results[6],
      milestones: results[7],
      arxiv: results[8],
      divincenzo: results[9]
    };

    renderAll(data);
  }).catch(function (err) {
    console.error("Dashboard load error:", err);
  });

  // ─────────────────────────────────────────
  // Master render
  // ─────────────────────────────────────────
  function renderAll(data) {
    renderHeader(data);
    renderAlertHero(data.alerts);
    renderQdayDistance(data.qday);
    renderLadders(data.factoring);
    renderHardwareChart(data.hardware);
    renderDiVincenzo(data.divincenzo);
    renderPqcTable(data.adoption);
    renderBlockchain(data.blockchain);
    renderFundingChart(data.funding);
    renderArxivChart(data.arxiv);
    initMosca(data.qday);
  }

  // ─────────────────────────────────────────
  // 1. Header
  // ─────────────────────────────────────────
  function renderHeader(data) {
    var date = data.alerts.metadata && data.alerts.metadata.last_updated
      ? data.alerts.metadata.last_updated
      : "Unknown";
    $("lastUpdated").textContent = "Last updated: " + date;
  }

  // ─────────────────────────────────────────
  // 2. Alert Status Hero
  // ─────────────────────────────────────────
  function renderAlertHero(alerts) {
    var level = alerts.override || alerts.current_level || "GREEN";
    var levelInfo = alerts.levels[level] || {};

    // Activate traffic light
    var lights = document.querySelectorAll(".light");
    for (var i = 0; i < lights.length; i++) {
      var l = lights[i];
      if (l.getAttribute("data-level") === level) {
        l.classList.add("active");
      } else {
        l.classList.remove("active");
      }
    }

    // Level text
    var labelEl = $("alertLevelLabel");
    labelEl.textContent = level + " — " + (levelInfo.label || "");
    labelEl.style.color = LEVEL_COLORS[level] || "#f1f5f9";

    $("alertLevelDesc").textContent = levelInfo.description || "";

    // Triggered milestones
    var timelineEl = $("triggeredTimeline");
    var timelineHtml = "";
    var triggered = alerts.triggered || [];
    triggered.forEach(function (item) {
      timelineHtml += '<div class="triggered-item">'
        + '<span class="triggered-dot dot-' + escapeHtml(item.level) + '"></span>'
        + '<span class="triggered-date">' + escapeHtml(item.date) + '</span>'
        + '<span class="triggered-event">' + escapeHtml(item.event) + '</span>'
        + '</div>';
    });
    timelineEl.innerHTML = timelineHtml;

    // Watch items
    var watchEl = $("watchItems");
    var watchHtml = "";
    var watchItems = alerts.watch_items || [];
    watchItems.forEach(function (item) {
      watchHtml += '<div class="watch-item">'
        + '<span class="watch-tag watch-tag-' + escapeHtml(item.level) + '">' + escapeHtml(item.level) + '</span>'
        + escapeHtml(item.event)
        + '</div>';
    });
    watchEl.innerHTML = watchHtml;
  }

  // ─────────────────────────────────────────
  // 3. Q-Day Distance
  // ─────────────────────────────────────────
  function renderQdayDistance(qday) {
    var est = qday.estimate || {};
    var low = est.low_years;
    var high = est.high_years;

    $("qdayNumber").textContent = low + "\u2013" + high + " years";

    // Component bar
    var components = qday.components || {};
    var keys = Object.keys(components);
    var barEl = $("componentsBar");
    var detailEl = $("componentsDetail");
    var barHtml = "";
    var detailHtml = "";

    var componentLabels = {
      factoring: "Factoring Progress",
      logical_qubits: "Logical Qubits",
      roadmap_consensus: "Roadmap Consensus",
      error_correction: "Error Correction",
      investment: "Investment Trend",
      divincenzo: "DiVincenzo Completeness"
    };

    keys.forEach(function (key, idx) {
      var comp = components[key];
      var color = COMPONENT_COLORS[idx % COMPONENT_COLORS.length];
      var weightPct = (comp.weight * 100).toFixed(0);

      barHtml += '<div class="component-segment" style="width:' + weightPct + '%; background:' + color + '; opacity:0.8;"></div>';

      var progress = 0;
      var detailText = "";

      if (key === "factoring") {
        progress = comp.progress_pct || 0;
        detailText = comp.current_bits + "-bit / " + comp.target_bits + "-bit target";
      } else if (key === "logical_qubits") {
        progress = comp.progress_pct || 0;
        detailText = comp.current + " / " + comp.target.toLocaleString() + " target";
      } else if (key === "roadmap_consensus") {
        progress = Math.max(0, Math.min(100, (1 - comp.years_out / 15) * 100));
        detailText = "Avg target year: " + comp.avg_target_year;
      } else if (key === "error_correction") {
        progress = comp.score || 0;
        detailText = comp.below_threshold_demonstrated ? "Below-threshold: Yes" : "Below-threshold: No";
      } else if (key === "investment") {
        progress = Math.min(100, comp.yoy_growth_pct * 2);
        detailText = comp.yoy_growth_pct + "% YoY growth";
      } else if (key === "divincenzo") {
        progress = comp.progress_pct || 0;
        detailText = (comp.leading_vendor || "?") + ": " + (comp.core_score || 0) + "/" + (comp.max_score || 15) + " core criteria";
      }

      detailHtml += '<div class="comp-card">'
        + '<div class="comp-name" style="color:' + color + ';">' + escapeHtml(componentLabels[key] || key) + '</div>'
        + '<div class="comp-weight">Weight: ' + weightPct + '%</div>'
        + '<div class="comp-progress-bar"><div class="comp-progress-fill" style="width:' + progress.toFixed(1) + '%; background:' + color + ';"></div></div>'
        + '<div class="comp-detail-text">' + escapeHtml(detailText) + '</div>'
        + '</div>';
    });

    barEl.innerHTML = barHtml;
    detailEl.innerHTML = detailHtml;

    $("caveatText").textContent = qday.caveat || "";
  }

  // ─────────────────────────────────────────
  // 4. Canary Ladders
  // ─────────────────────────────────────────
  function renderLadders(factoring) {
    renderSingleLadder($("rsaLadder"), (factoring.rsa_ladder || []).slice().reverse());
    renderSingleLadder($("ecdlpLadder"), (factoring.ecdlp_ladder || []).slice().reverse());
    renderClassicalContext(factoring.classical_context || []);
  }

  function renderSingleLadder(el, rungs) {
    var html = "";
    rungs.forEach(function (rung) {
      var isAchieved = rung.status === "achieved";
      var isCurrent = rung.status === "current";
      var isCanary = rung.canary === true;
      var isQday = rung.qday === true;

      var rungClass = "ladder-rung";
      var iconClass = "rung-icon rung-icon-pending";
      var iconChar = "\u25CB"; // open circle

      if (isQday) {
        rungClass += " rung-qday";
        iconClass = "rung-icon rung-icon-qday";
        iconChar = "\u2620"; // skull
      } else if (isCanary) {
        rungClass += " rung-canary";
        iconClass = "rung-icon rung-icon-canary";
        iconChar = "\uD83D\uDC26"; // bird
      } else if (isAchieved) {
        rungClass += " rung-achieved";
        iconClass = "rung-icon rung-icon-achieved";
        iconChar = "\u2713"; // checkmark
      } else if (isCurrent) {
        rungClass += " rung-current";
        iconClass = "rung-icon rung-icon-current";
        iconChar = "\u25C9"; // fisheye
      }

      var signalText = rung.signal || rung.note || rung.method || "";
      var dateText = rung.date || "";

      html += '<div class="' + rungClass + '">'
        + '<span class="' + iconClass + '">' + iconChar + '</span>'
        + '<div class="rung-body">'
        + '<div class="rung-label">' + escapeHtml(rung.label) + '</div>';

      if (rung.bits > 0) {
        html += '<div class="rung-bits">' + rung.bits + '-bit</div>';
      }

      if (signalText) {
        html += '<div class="rung-signal">' + escapeHtml(signalText) + '</div>';
      }

      html += '</div>';

      if (dateText) {
        html += '<span class="rung-date">' + escapeHtml(dateText) + '</span>';
      }

      html += '</div>';
    });
    el.innerHTML = html;
  }

  function renderClassicalContext(ctx) {
    var el = $("classicalContext");
    if (!ctx.length) { el.innerHTML = ""; return; }
    var item = ctx[0];
    el.innerHTML = '<div class="classical-context-title">Classical Context</div>'
      + '<div class="classical-context-text">'
      + escapeHtml(item.label) + " factored classically (" + escapeHtml(item.date) + ") via " + escapeHtml(item.method)
      + (item.note ? ". " + escapeHtml(item.note) : "")
      + '</div>';
  }

  // ─────────────────────────────────────────
  // 5. Hardware Chart
  // ─────────────────────────────────────────
  function renderHardwareChart(hardware) {
    var milestones = hardware.milestones || [];
    var roadmap = hardware.roadmap_targets || [];

    // Build scatter data grouped by vendor
    var vendorColors = {
      IBM: "#4589ff",
      Google: "#22c55e",
      IonQ: "#a78bfa",
      "Atom Computing": "#f97316",
      Microsoft: "#06b6d4",
      Quantinuum: "#eab308",
      DOE: "#ef4444",
      Industry: "#94a3b8"
    };

    // Collect unique vendors
    var vendors = {};
    milestones.forEach(function (m) {
      if (!vendors[m.vendor]) vendors[m.vendor] = [];
      vendors[m.vendor].push({
        x: m.date,
        y: m.physical_qubits,
        label: m.event,
        vendor: m.vendor
      });
    });

    var datasets = [];
    Object.keys(vendors).forEach(function (v) {
      datasets.push({
        label: v,
        data: vendors[v].map(function (pt) {
          var parts = pt.x.split("-");
          var yr = parseInt(parts[0], 10);
          var mo = parts[1] ? parseInt(parts[1], 10) - 1 : 0;
          return { x: new Date(yr, mo, 15).getTime(), y: pt.y };
        }),
        backgroundColor: vendorColors[v] || "#94a3b8",
        borderColor: vendorColors[v] || "#94a3b8",
        pointRadius: 6,
        pointHoverRadius: 9,
        showLine: false
      });
    });

    // Add roadmap targets as a separate dataset
    var roadmapPoints = [];
    roadmap.forEach(function (r) {
      roadmapPoints.push({
        x: new Date(r.target_year, 6, 1).getTime(),
        y: 10000, // representative target scale
        label: r.vendor + ": " + r.target
      });
    });

    if (roadmapPoints.length > 0) {
      datasets.push({
        label: "Roadmap Targets",
        data: roadmapPoints,
        backgroundColor: "rgba(255, 255, 255, 0.3)",
        borderColor: "rgba(255, 255, 255, 0.5)",
        pointRadius: 8,
        pointHoverRadius: 11,
        pointStyle: "triangle",
        showLine: false,
        borderDash: [5, 5]
      });
    }

    var ctx = $("hardwareChart").getContext("2d");
    new Chart(ctx, {
      type: "scatter",
      data: { datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: "#94a3b8", font: { family: "system-ui", size: 12 } }
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                var ds = context.dataset;
                var pt = context.raw;
                var d = new Date(pt.x);
                var dateStr = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
                return ds.label + ": " + pt.y.toLocaleString() + " qubits (" + dateStr + ")";
              }
            }
          },
          annotation: {
            annotations: {
              targetLine: {
                type: "line",
                yMin: 4000,
                yMax: 4000,
                borderColor: "rgba(239, 68, 68, 0.5)",
                borderWidth: 2,
                borderDash: [8, 4],
                label: {
                  display: true,
                  content: "~4,000 logical qubits for RSA-2048",
                  color: "#ef4444",
                  font: { size: 11, family: "system-ui" },
                  position: "start"
                }
              }
            }
          }
        },
        scales: {
          x: {
            type: "linear",
            title: { display: true, text: "Year", color: "#94a3b8" },
            ticks: {
              color: "#64748b",
              callback: function (val) {
                return new Date(val).getFullYear();
              }
            },
            grid: { color: "rgba(51, 65, 85, 0.5)" }
          },
          y: {
            type: "logarithmic",
            title: { display: true, text: "Physical Qubits", color: "#94a3b8" },
            min: 3,
            max: 100000,
            ticks: {
              color: "#64748b",
              callback: function (val) {
                if ([5, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000].indexOf(val) !== -1) {
                  return val.toLocaleString();
                }
                return "";
              }
            },
            grid: { color: "rgba(51, 65, 85, 0.5)" }
          }
        }
      }
    });

    // Roadmap targets below chart
    var targetsEl = $("roadmapTargets");
    var targetsHtml = "";
    roadmap.forEach(function (r) {
      targetsHtml += '<div class="roadmap-tag">'
        + '<span class="roadmap-tag-year">' + r.target_year + '</span>'
        + escapeHtml(r.vendor) + " \u2014 " + escapeHtml(r.target)
        + '</div>';
    });
    targetsEl.innerHTML = targetsHtml;
  }

  // ─────────────────────────────────────────
  // 5b. DiVincenzo Scorecard
  // ─────────────────────────────────────────
  function renderDiVincenzo(dv) {
    var scorecardEl = $("dvScorecard");
    var legendEl = $("dvLegend");

    if (!dv || !dv.vendors) {
      scorecardEl.innerHTML = '<div class="placeholder-msg"><span class="placeholder-icon">&#9881;</span>DiVincenzo Criteria data not yet available.</div>';
      return;
    }

    var coreCriteria = dv.criteria.core || [];
    var networkCriteria = dv.criteria.networking || [];
    var allCriteria = coreCriteria.concat(networkCriteria);
    var statusLevels = dv.status_levels || {};
    var vendors = dv.vendors || [];

    // Status to numeric value for sorting
    var statusRank = { scalable: 4, demonstrated: 3, partial: 2, not_demonstrated: 1 };

    // Sort vendors by overall_score descending
    vendors.sort(function (a, b) {
      return (b.overall_score || 0) - (a.overall_score || 0);
    });

    // Build the heatmap grid
    var html = '<div class="dv-grid">';

    // Header row: empty corner + criteria
    html += '<div class="dv-header-cell dv-corner"></div>';
    for (var ci = 0; ci < allCriteria.length; ci++) {
      var c = allCriteria[ci];
      var isNet = ci >= coreCriteria.length;
      html += '<div class="dv-header-cell' + (isNet ? ' dv-net-header' : '') + '" title="' + escapeHtml(c.description) + '">'
        + '<span class="dv-criterion-id">' + escapeHtml(c.id) + '</span>'
        + '<span class="dv-criterion-name">' + escapeHtml(c.name) + '</span>'
        + '</div>';
    }
    // Score header
    html += '<div class="dv-header-cell dv-score-header">Score</div>';

    // Vendor rows
    for (var vi = 0; vi < vendors.length; vi++) {
      var vendor = vendors[vi];
      var assessments = vendor.assessments || {};

      html += '<div class="dv-vendor-cell">'
        + '<span class="dv-vendor-name">' + escapeHtml(vendor.name) + '</span>'
        + '<span class="dv-vendor-platform">' + escapeHtml(vendor.platform) + '</span>'
        + '</div>';

      for (var cj = 0; cj < allCriteria.length; cj++) {
        var criterion = allCriteria[cj];
        var assessment = assessments[criterion.id] || {};
        var status = assessment.status || "not_demonstrated";
        var levelInfo = statusLevels[status] || {};
        var color = levelInfo.color || "#64748b";
        var rank = statusRank[status] || 1;

        // Build tooltip content
        var tooltipParts = [escapeHtml(levelInfo.label || status)];
        if (assessment.metric) {
          tooltipParts.push(escapeHtml(assessment.metric));
        }
        if (assessment.evidence) {
          tooltipParts.push(escapeHtml(assessment.evidence));
        }
        var tooltip = tooltipParts.join(" | ");

        html += '<div class="dv-cell dv-cell-' + escapeHtml(status) + '" title="' + tooltip + '" data-rank="' + rank + '">'
          + '<span class="dv-cell-dot" style="background:' + color + ';"></span>'
          + '<span class="dv-cell-label">' + escapeHtml(levelInfo.label || status) + '</span>'
          + '</div>';
      }

      // Score cell
      html += '<div class="dv-score-cell">'
        + '<span class="dv-score-number">' + (vendor.overall_score || 0) + '</span>'
        + '<span class="dv-score-max">/5</span>'
        + '</div>';
    }

    html += '</div>';
    scorecardEl.innerHTML = html;

    // Legend
    var legendHtml = '<div class="dv-legend-items">';
    var levelKeys = ["not_demonstrated", "partial", "demonstrated", "scalable"];
    for (var li = 0; li < levelKeys.length; li++) {
      var lk = levelKeys[li];
      var lv = statusLevels[lk] || {};
      legendHtml += '<div class="dv-legend-item">'
        + '<span class="dv-legend-dot" style="background:' + (lv.color || "#64748b") + ';"></span>'
        + '<span class="dv-legend-label">' + escapeHtml(lv.label || lk) + '</span>'
        + '</div>';
    }
    legendHtml += '</div>';
    legendEl.innerHTML = legendHtml;
  }

  // ─────────────────────────────────────────
  // 6a. PQC Adoption Table
  // ─────────────────────────────────────────
  function renderPqcTable(adoption) {
    var deployments = adoption.deployments || [];
    var tbody = $("pqcTableBody");
    var html = "";

    // Sort: deployed first, then by category
    var statusOrder = { deployed: 0, testing: 1, in_development: 2, not_started: 3 };
    deployments.sort(function (a, b) {
      var sa = statusOrder[a.status] !== undefined ? statusOrder[a.status] : 9;
      var sb = statusOrder[b.status] !== undefined ? statusOrder[b.status] : 9;
      if (sa !== sb) return sa - sb;
      if (a.category < b.category) return -1;
      if (a.category > b.category) return 1;
      return 0;
    });

    deployments.forEach(function (d) {
      html += "<tr>"
        + "<td><strong>" + escapeHtml(d.entity) + "</strong></td>"
        + '<td><span class="category-label">' + escapeHtml(d.category) + "</span></td>"
        + '<td><span class="status-badge badge-' + escapeHtml(d.status) + '">' + escapeHtml(formatStatus(d.status)) + "</span></td>"
        + "<td>" + escapeHtml(d.standard || "\u2014") + "</td>"
        + "<td>" + escapeHtml(d.date || "\u2014") + "</td>"
        + "</tr>";
    });
    tbody.innerHTML = html;
  }

  // ─────────────────────────────────────────
  // 6b. Blockchain PQC Status
  // ─────────────────────────────────────────
  function renderBlockchain(blockchain) {
    var chains = blockchain.chains || [];
    var gridEl = $("blockchainGrid");
    var html = "";

    // Sort by status priority
    var statusOrder = { mainnet: 0, testnet: 1, in_development: 2, planned: 3, discussed: 4, not_acknowledged: 5 };
    chains.sort(function (a, b) {
      var sa = statusOrder[a.status] !== undefined ? statusOrder[a.status] : 9;
      var sb = statusOrder[b.status] !== undefined ? statusOrder[b.status] : 9;
      return sa - sb;
    });

    chains.forEach(function (chain) {
      html += '<div class="chain-card">'
        + '<div class="chain-header">'
        + '<div><span class="chain-name">' + escapeHtml(chain.name) + '</span>'
        + '<span class="chain-ticker">' + escapeHtml(chain.ticker) + '</span></div>'
        + '<span class="chain-status-badge chain-badge-' + escapeHtml(chain.status) + '">' + escapeHtml(formatStatus(chain.status)) + '</span>'
        + '</div>'
        + '<div class="chain-detail">' + escapeHtml(chain.detail) + '</div>'
        + '<div class="chain-exposure">' + escapeHtml(chain.exposure) + '</div>'
        + '</div>';
    });
    gridEl.innerHTML = html;
  }

  // ─────────────────────────────────────────
  // 7a. Funding Chart
  // ─────────────────────────────────────────
  function renderFundingChart(funding) {
    var annual = funding.annual || [];
    var years = annual.map(function (a) { return a.year; });

    var countries = [
      { key: "china", label: "China", color: "#ef4444" },
      { key: "us", label: "United States", color: "#4589ff" },
      { key: "eu", label: "European Union", color: "#22c55e" },
      { key: "uk", label: "United Kingdom", color: "#a78bfa" },
      { key: "japan", label: "Japan", color: "#f97316" },
      { key: "other", label: "Other", color: "#64748b" }
    ];

    var datasets = countries.map(function (c) {
      return {
        label: c.label,
        data: annual.map(function (a) { return a[c.key] || 0; }),
        backgroundColor: c.color,
        borderColor: "transparent",
        borderWidth: 0
      };
    });

    var ctx = $("fundingChart").getContext("2d");
    new Chart(ctx, {
      type: "bar",
      data: {
        labels: years,
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: "#94a3b8", font: { family: "system-ui", size: 11 } }
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                return context.dataset.label + ": $" + context.raw.toFixed(1) + "B";
              }
            }
          }
        },
        scales: {
          x: {
            stacked: true,
            ticks: { color: "#64748b" },
            grid: { color: "rgba(51, 65, 85, 0.3)" }
          },
          y: {
            stacked: true,
            title: { display: true, text: "USD Billions", color: "#94a3b8" },
            ticks: { color: "#64748b" },
            grid: { color: "rgba(51, 65, 85, 0.3)" }
          }
        }
      }
    });

    // Cumulative note
    var noteEl = $("fundingNote");
    noteEl.innerHTML = "Cumulative total: <strong>$" + (funding.cumulative_total_bn || 0).toFixed(1) + "B</strong> across all tracked countries.";
  }

  // ─────────────────────────────────────────
  // 7b. Research Velocity (arXiv)
  // ─────────────────────────────────────────
  function renderArxivChart(arxiv) {
    var canvasEl = $("arxivChart");

    if (!arxiv || !arxiv.categories) {
      var parent = canvasEl.parentNode;
      parent.innerHTML = '<div class="placeholder-msg"><span class="placeholder-icon">&#128202;</span>Collecting data... arXiv paper counts will appear here once processing completes.</div>';
      return;
    }

    var categories = arxiv.categories;
    var catKeys = Object.keys(categories);

    var catColors = {
      shor_implementation: "#ef4444",
      pqc_deployment: "#22c55e",
      error_correction: "#8b5cf6"
    };

    // Build labels from first category (all should share same dates)
    var firstCat = categories[catKeys[0]];
    var labels = firstCat.monthly.map(function (m) { return m.date; });

    var datasets = catKeys.map(function (key) {
      var cat = categories[key];
      return {
        label: cat.label || key,
        data: cat.monthly.map(function (m) { return m.count; }),
        borderColor: catColors[key] || "#06b6d4",
        backgroundColor: "transparent",
        pointRadius: 2,
        pointHoverRadius: 5,
        borderWidth: 2,
        tension: 0.3
      };
    });

    var ctx = canvasEl.getContext("2d");
    new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: "#94a3b8", font: { family: "system-ui", size: 11 } }
          }
        },
        scales: {
          x: {
            ticks: {
              color: "#64748b",
              maxTicksLimit: 12,
              maxRotation: 45
            },
            grid: { color: "rgba(51, 65, 85, 0.3)" }
          },
          y: {
            title: { display: true, text: "Papers / month", color: "#94a3b8" },
            ticks: { color: "#64748b" },
            grid: { color: "rgba(51, 65, 85, 0.3)" },
            beginAtZero: true
          }
        }
      }
    });
  }

  // ─────────────────────────────────────────
  // 8. Mosca's Theorem Calculator
  // ─────────────────────────────────────────
  function initMosca(qday) {
    var midpoint = qday.estimate ? qday.estimate.midpoint_years : 15;
    var threatSlider = $("threatSlider");

    // Set initial threat value from Q-Day estimate
    threatSlider.value = Math.round(midpoint);
    $("threatValue").textContent = Math.round(midpoint);

    var shelfSlider = $("shelfLifeSlider");
    var migrationSlider = $("migrationSlider");

    function updateMosca() {
      var shelf = parseInt(shelfSlider.value, 10);
      var migration = parseInt(migrationSlider.value, 10);
      var threat = parseInt(threatSlider.value, 10);

      $("shelfLifeValue").textContent = shelf;
      $("migrationValue").textContent = migration;
      $("threatValue").textContent = threat;

      var need = shelf + migration;
      var resultEl = $("moscaResult");
      var textEl = $("moscaResultText");

      // Remove previous classes
      resultEl.className = "mosca-result";

      if (need > threat) {
        var over = need - threat;
        resultEl.classList.add("mosca-result-danger");
        textEl.textContent = "\u26A0\uFE0F You should have started " + over + " year" + (over !== 1 ? "s" : "") + " ago";
      } else if (need === threat) {
        resultEl.classList.add("mosca-result-warning");
        textEl.textContent = "\u26A0 You need to start this year";
      } else {
        var margin = threat - need;
        resultEl.classList.add("mosca-result-safe");
        textEl.textContent = "\u2705 You have " + margin + " year" + (margin !== 1 ? "s" : "") + " of margin";
      }

      // Update visual timeline bar
      var maxYears = Math.max(shelf + migration, threat, 1);
      var barWidth = 100; // percent
      var pxPerYear = barWidth / maxYears;

      $("moscaBarShelf").style.width = (shelf * pxPerYear) + "%";
      $("moscaBarMigration").style.left = (shelf * pxPerYear) + "%";
      $("moscaBarMigration").style.width = (migration * pxPerYear) + "%";
      $("moscaBarThreat").style.left = Math.min(threat * pxPerYear, 99) + "%";
    }

    shelfSlider.addEventListener("input", updateMosca);
    migrationSlider.addEventListener("input", updateMosca);
    threatSlider.addEventListener("input", updateMosca);

    updateMosca();
  }

})();
