(() => {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const reveals = document.querySelectorAll("[data-reveal]");
  if (reduceMotion || !("IntersectionObserver" in window)) {
    reveals.forEach((el) => el.classList.add("is-in"));
  } else {
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            io.unobserve(entry.target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 }
    );
    reveals.forEach((el) => io.observe(el));
  }

  const trackerApp = document.getElementById("tracker-app");
  if (trackerApp) {
    initTracker(trackerApp);
  }
})();

function initTracker(root) {
  const csvUrl = root.dataset.csv || "../promised-vs-actual.csv";
  const tbody = document.getElementById("tracker-tbody");
  const searchInput = document.getElementById("tracker-search");
  const resultCount = document.getElementById("tracker-result-count");
  const emptyState = document.getElementById("tracker-empty");
  const filterButtons = root.querySelectorAll(".tracker-filter");

  if (!tbody || !searchInput || !resultCount) {
    return;
  }

  let rows = [];
  let activeCategory = "All";
  let searchQuery = "";

  filterButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      activeCategory = btn.dataset.category || "All";
      filterButtons.forEach((b) => {
        const on = b === btn;
        b.classList.toggle("is-active", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
      render();
    });
  });

  searchInput.addEventListener("input", () => {
    searchQuery = searchInput.value.trim().toLowerCase();
    render();
  });

  fetch(csvUrl)
    .then((res) => {
      if (!res.ok) {
        throw new Error(`Could not load tracker data (${res.status})`);
      }
      return res.text();
    })
    .then((text) => {
      rows = parseCsv(text);
      if (rows.length === 0) {
        throw new Error("No project rows in CSV");
      }
      render();
    })
    .catch((err) => {
      resultCount.textContent =
        "Could not load project data. Please refresh or try again later.";
      console.error(err);
    });

  function render() {
    const filtered = rows.filter((row) => matchesCategory(row, activeCategory));
    const visible = filtered.filter((row) => matchesSearch(row, searchQuery));

    tbody.replaceChildren();
    for (const row of visible) {
      tbody.appendChild(buildRow(row));
    }

    const total = rows.length;
    const shown = visible.length;
    if (shown === 0) {
      resultCount.textContent =
        activeCategory === "All"
          ? "No projects match your search."
          : `No ${activeCategory} projects match your search.`;
      emptyState.hidden = false;
    } else {
      emptyState.hidden = true;
      const categoryNote =
        activeCategory === "All" ? "" : ` in ${activeCategory}`;
      resultCount.textContent =
        shown === total
          ? `Showing all ${shown} tracked projects${categoryNote}.`
          : `Showing ${shown} of ${total} tracked projects${categoryNote}.`;
    }
  }
}

function matchesCategory(row, category) {
  if (category === "All") {
    return true;
  }
  return (row.category || "").trim() === category;
}

function matchesSearch(row, query) {
  if (!query) {
    return true;
  }
  const haystack = [
    row.category,
    row.project,
    row.status,
    row.promised,
    row.revised,
    row.actual,
    row.slip_days,
    row.budget_variance,
    row.sources,
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
}

function buildRow(row) {
  const tr = document.createElement("tr");

  tr.appendChild(cellText(row.project, "th", { scope: "row" }));
  tr.appendChild(cellStatus(row.status));
  tr.appendChild(cellText(row.promised));
  tr.appendChild(cellText(row.revised));
  tr.appendChild(cellText(row.actual));
  tr.appendChild(cellVariance(row.slip_days, "slip"));
  tr.appendChild(cellVariance(row.budget_variance, "budget"));
  tr.appendChild(cellSources(row.sources));

  return tr;
}

function cellText(value, tagName = "td", attrs = {}) {
  const el = document.createElement(tagName);
  for (const [key, val] of Object.entries(attrs)) {
    el.setAttribute(key, val);
  }
  el.textContent = value || "";
  return el;
}

function cellStatus(status) {
  const td = document.createElement("td");
  const pill = document.createElement("span");
  pill.className = `tracker-pill ${statusClass(status)}`;
  pill.textContent = status || "";
  td.appendChild(pill);
  return td;
}

function statusClass(status) {
  const s = (status || "").toLowerCase();
  if (s.includes("completed") || s.includes("late")) {
    return "tracker-pill--late";
  }
  if (s.includes("slipped")) {
    return "tracker-pill--slipped";
  }
  if (s.includes("design")) {
    return "tracker-pill--design";
  }
  if (s.includes("on track")) {
    return "tracker-pill--on-track";
  }
  return "tracker-pill--neutral";
}

function cellVariance(value, kind) {
  const td = document.createElement("td");
  const text = (value || "").trim();
  const span = document.createElement("span");
  span.className = varianceClass(text, kind);
  span.textContent = formatVariance(text, kind);
  td.appendChild(span);
  return td;
}

function varianceClass(text, kind) {
  if (!text || /^not stated$/i.test(text)) {
    return "tracker-variance tracker-variance--na";
  }
  if (kind === "slip") {
    const days = parseSlipDays(text);
    if (days !== null && days > 0) {
      return "tracker-variance tracker-variance--warn";
    }
    if (days === 0) {
      return "tracker-variance tracker-variance--ok";
    }
  }
  if (kind === "budget") {
    if (/[\$]|%|over|under|\+|\-/i.test(text) && !/^not stated$/i.test(text)) {
      return "tracker-variance tracker-variance--warn";
    }
  }
  return "tracker-variance tracker-variance--neutral";
}

function formatVariance(text, kind) {
  if (!text) {
    return "not stated";
  }
  if (kind === "slip") {
    const days = parseSlipDays(text);
    if (days !== null && days > 0) {
      return `+${days.toLocaleString()} days`;
    }
  }
  return text;
}

function parseSlipDays(text) {
  if (/^not stated$/i.test(text.trim())) {
    return null;
  }
  const digits = text.replace(/,/g, "").match(/\d+/);
  if (!digits) {
    return null;
  }
  return parseInt(digits[0], 10);
}

function cellSources(raw) {
  const td = document.createElement("td");
  td.className = "tracker-sources";
  const links = parseSourceLinks(raw);
  if (links.length === 0) {
    td.textContent = "not stated";
    return td;
  }
  links.forEach((link, index) => {
    if (index > 0) {
      td.appendChild(document.createTextNode(", "));
    }
    const a = document.createElement("a");
    a.href = link.url;
    a.textContent = link.label;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    td.appendChild(a);
  });
  return td;
}

function parseSourceLinks(raw) {
  if (!raw || !raw.trim()) {
    return [];
  }
  return raw
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const pipe = part.indexOf("|");
      if (pipe === -1) {
        return null;
      }
      const label = part.slice(0, pipe).trim();
      const url = part.slice(pipe + 1).trim();
      if (!label || !url) {
        return null;
      }
      return { label, url };
    })
    .filter(Boolean);
}

function parseCsv(text) {
  const records = parseCsvRecords(text);
  if (records.length < 2) {
    return [];
  }
  const headers = records[0].map((h) => h.trim());
  return records.slice(1).map((fields) => {
    const row = {};
    headers.forEach((header, i) => {
      row[header] = fields[i] !== undefined ? fields[i] : "";
    });
    return row;
  });
}

function parseCsvRecords(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (inQuotes) {
      if (char === '"' && next === '"') {
        field += '"';
        i += 1;
      } else if (char === '"') {
        inQuotes = false;
      } else {
        field += char;
      }
      continue;
    }

    if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && next === "\n") {
        i += 1;
      }
      row.push(field);
      if (row.some((cell) => cell.trim() !== "")) {
        rows.push(row);
      }
      row = [];
      field = "";
    } else {
      field += char;
    }
  }

  row.push(field);
  if (row.some((cell) => cell.trim() !== "")) {
    rows.push(row);
  }

  return rows;
}
