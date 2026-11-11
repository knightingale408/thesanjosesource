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

// Tracker: renders the Promised vs. Actual scorecards from the generated
// public-data/projects.json (built from the canonical data layer). The
// old CSV table is retired; no figures live in this file.
function initTracker(root) {
  const jsonUrl = root.dataset.json || "../public-data/projects.json";
  const cardsEl = document.getElementById("tracker-cards");
  const searchInput = document.getElementById("tracker-search");
  const resultCount = document.getElementById("tracker-result-count");
  const emptyState = document.getElementById("tracker-empty");
  const clearBtn = document.getElementById("tracker-clear");
  const filterGroups = {
    category: document.getElementById("tracker-filters-category"),
    status: document.getElementById("tracker-filters-status"),
    fund: document.getElementById("tracker-filters-fund"),
  };

  if (!cardsEl || !searchInput || !resultCount) {
    return;
  }

  const NOT_REPORTED = "not reported";
  const STATUS_LABELS = {
    on_track: "On the City's schedule",
    delayed: "Later than first promised",
    complete: "Delivered",
    watch: "On the City's schedule",
    over_budget: "Over the original budget",
    delayed_and_over_budget: "Later than first promised",
    scope_changed: "Scope has changed",
    paused: "No current date",
    cancelled: "No current date",
    insufficient_information: "No current date",
  };
  const STATUS_PILL = {
    complete: "tracker-pill--on-track",
    on_track: "tracker-pill--design",
    watch: "tracker-pill--design",
    delayed: "tracker-pill--late",
    over_budget: "tracker-pill--budget",
    delayed_and_over_budget: "tracker-pill--late",
    scope_changed: "tracker-pill--neutral",
  };
  // Display stepper groups procurement with pre-construction (the data
  // keeps them distinct). Lifecycle != performance status.
  const STAGES = ["Planning", "Design", "Pre-construction", "Construction", "Complete"];
  const STAGE_STEP = { planning: 0, design: 1, permitting: 2, procurement: 2, construction: 3, complete: 4 };
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"];

  let projects = [];
  let state = { category: "all", status: "all", fund: "all", q: "" };

  fetch(jsonUrl)
    .then((res) => {
      if (!res.ok) {
        throw new Error(`Could not load tracker data (${res.status})`);
      }
      return res.json();
    })
    .then((payload) => {
      projects = (payload && payload.projects) || [];
      if (projects.length === 0) {
        throw new Error("No project rows in the generated data");
      }
      readStateFromHash();
      window.addEventListener("hashchange", () => {
        readStateFromHash();
        buildFilterButtons();
        render();
      });
      buildFilterButtons();
      render();
    })
    .catch((err) => {
      resultCount.textContent =
        "Could not load project data. Please refresh or try again later.";
      console.error(err);
    });

  searchInput.addEventListener("input", () => {
    state.q = searchInput.value.trim().toLowerCase();
    render();
  });

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      state = { category: "all", status: "all", fund: "all", q: "" };
      searchInput.value = "";
      const hash = "#";
      if (location.hash !== hash) {
        history.replaceState(null, "", hash);
      }
      buildFilterButtons();
      render();
    });
  }

  function readStateFromHash() {
    const params = new URLSearchParams(
      (location.hash || "").replace(/^#/, "")
    );
    const dims = ["category", "status", "fund"];
    for (const dim of dims) {
      const value = (params.get(dim) || "").trim().toLowerCase();
      state[dim] = value || "all";
    }
    // A hash that omits q resets the search, so navigating to a shared
    // filter link never keeps a stale query applied.
    const q = (params.get("q") || "").trim();
    state.q = q.toLowerCase();
    if (document.activeElement !== searchInput) {
      searchInput.value = q;
    }
  }

  function writeStateToHash() {
    const params = new URLSearchParams();
    for (const dim of ["category", "status", "fund"]) {
      if (state[dim] !== "all") {
        params.set(dim, state[dim]);
      }
    }
    if (state.q) {
      params.set("q", state.q);
    }
    const hash = "#" + params.toString();
    if (location.hash !== hash) {
      history.replaceState(null, "", hash);
    }
  }

  function buildFilterButtons() {
    const dims = [
      {
        key: "category",
        label: (p) => p.category_label || p.category,
        match: (p, value) => p.category === value,
      },
      {
        key: "status",
        label: (p) => STATUS_LABELS[p.position.status && p.position.status.status_code] || "No current date",
        match: (p, value) => (p.position.status && p.position.status.status_code) === value,
      },
      {
        key: "fund",
        label: (p) => p.fund === "measure-t" ? "Measure T" : p.fund,
        match: (p, value) => p.fund === value,
      },
    ];
    for (const dim of dims) {
      const container = filterGroups[dim.key];
      if (!container) {
        continue;
      }
      // Rebuilding the buttons removes the button that currently has
      // keyboard focus; remember it and restore focus after the rebuild.
      const activeBtn = container.querySelector("button:focus");
      const activeDim = activeBtn && activeBtn.dataset.dim;
      const activeValue = activeBtn && activeBtn.dataset.value;
      const values = [];
      const seen = new Set();
      for (const p of projects) {
        const value = dim.key === "category" ? p.category : dim.key === "status" ? (p.position.status && p.position.status.status_code) : p.fund;
        if (!value || seen.has(value)) {
          continue;
        }
        seen.add(value);
        values.push({ value, label: dim.label(p) });
      }
      values.sort((a, b) => a.label.localeCompare(b.label));
      container.replaceChildren();
      const allBtn = filterButton(dim.key, "all", "All", state[dim.key] === "all");
      container.appendChild(allBtn);
      for (const v of values) {
        container.appendChild(filterButton(dim.key, v.value, v.label, state[dim.key] === v.value));
      }
      if (activeDim === dim.key && activeValue) {
        const restore = container.querySelector(
          `button[data-dim="${activeDim}"][data-value="${activeValue}"]`
        );
        if (restore) {
          restore.focus();
        }
      }
    }
  }

  function filterButton(dim, value, label, active) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tracker-filter btn btn--outline" + (active ? " is-active" : "");
    btn.dataset.dim = dim;
    btn.dataset.value = value;
    btn.setAttribute("aria-pressed", active ? "true" : "false");
    btn.textContent = label;
    btn.addEventListener("click", () => {
      state[dim] = value;
      buildFilterButtons();
      render();
    });
    return btn;
  }

  function render() {
    const visible = projects.filter(matchesAll);
    cardsEl.replaceChildren();
    for (const p of visible) {
      cardsEl.appendChild(buildCard(p));
    }
    writeStateToHash();

    const total = projects.length;
    const shown = visible.length;
    if (shown === 0) {
      resultCount.textContent = `No tracked projects match the current filters.`;
      emptyState.hidden = false;
    } else {
      emptyState.hidden = true;
      const notes = [];
      if (state.category !== "all") {
        notes.push(categoryLabel(state.category));
      }
      if (state.status !== "all") {
        notes.push(STATUS_LABELS[state.status] || state.status);
      }
      if (state.fund !== "all") {
        notes.push(state.fund === "measure-t" ? "Measure T" : state.fund);
      }
      const note = notes.length ? ` (${notes.join(", ")})` : "";
      resultCount.textContent =
        shown === total
          ? `Showing all ${shown} tracked projects${note}.`
          : `Showing ${shown} of ${total} tracked projects${note}.`;
    }
  }

  function categoryLabel(key) {
    const p = projects.find((x) => x.category === key);
    return (p && (p.category_label || p.category)) || key;
  }

  function matchesAll(p) {
    if (state.category !== "all" && p.category !== state.category) {
      return false;
    }
    if (state.status !== "all" && (!p.position.status || p.position.status.status_code !== state.status)) {
      return false;
    }
    if (state.fund !== "all" && p.fund !== state.fund) {
      return false;
    }
    if (state.q) {
      const haystack = [
        p.project_name,
        p.category_label,
        p.department,
        p.measure_or_fund,
        p.baseline.completion_label,
        p.position.completion && p.position.completion.label,
        p.position.status && p.position.status.change_reason,
      ].filter(Boolean).join(" ").toLowerCase();
      if (!haystack.includes(state.q)) {
        return false;
      }
    }
    return true;
  }

  function buildCard(p) {
    const card = document.createElement("article");
    card.className = "t-card";

    // Header: name, category, status pill, verification flag.
    const head = document.createElement("header");
    head.className = "t-card__head";
    const headText = document.createElement("div");
    const name = document.createElement("h3");
    name.className = "t-card__name";
    name.textContent = p.project_name;
    const meta = document.createElement("p");
    meta.className = "t-card__meta";
    meta.textContent = [
      p.category_label,
      p.department,
      p.measure_or_fund,
    ].filter(Boolean).join(" · ");
    headText.appendChild(name);
    headText.appendChild(meta);
    head.appendChild(headText);

    const statusConcept = p.position.status;
    const statusCode = statusConcept && statusConcept.status_code;
    const pill = document.createElement("span");
    pill.className = "tracker-pill " + (STATUS_PILL[statusCode] || "tracker-pill--neutral");
    pill.textContent = STATUS_LABELS[statusCode] || "No current date";
    head.appendChild(pill);
    card.appendChild(head);

    // Verification flag: reported values are visible while review is
    // pending, but the reader is told. Nothing is silently published.
    const accepted = isAccepted(p);
    if (!accepted) {
      const flag = document.createElement("p");
      flag.className = "t-card__flag";
      flag.textContent =
        "Verification pending: these values are from City records and have not yet completed our source check.";
      card.appendChild(flag);
    }

    // Promised vs. latest reported.
    const grid = document.createElement("div");
    grid.className = "t-card__grid";

    grid.appendChild(factBlock("What the City promised", scheduleText(p.baseline.completion_label, p.baseline.completion), budgetText(p.baseline.budget_label, p.baseline.budget_usd)));
    const latest = factBlock("Latest reported", scheduleText(p.position.completion && p.position.completion.label, p.position.completion && p.position.completion.date), budgetText(p.position.budget && p.position.budget.label, p.position.budget && p.position.budget.usd));
    const deltaNote = deltaLine(p);
    if (deltaNote) {
      const delta = document.createElement("p");
      delta.className = "t-fact__delta";
      delta.textContent = deltaNote;
      latest.appendChild(delta);
    }
    grid.appendChild(latest);
    card.appendChild(grid);

    // Lifecycle stepper (or a plain label for abnormal states).
    card.appendChild(stepper(p));

    // Change history.
    if (p.history && p.history.length) {
      const details = document.createElement("details");
      details.className = "t-history";
      const summary = document.createElement("summary");
      summary.textContent = `Change history (${p.history.length} entr${p.history.length === 1 ? "y" : "ies"})`;
      details.appendChild(summary);
      const list = document.createElement("ol");
      list.className = "t-history__list";
      for (const h of p.history) {
        list.appendChild(historyEntry(h));
      }
      details.appendChild(list);
      card.appendChild(details);
    }

    // Evidence: each value's own source.
    card.appendChild(evidence(p));

    return card;
  }

  const ACCEPTED_STATUSES = new Set(["accepted", "accepted_with_edits"]);

  function isAccepted(p) {
    // A card counts as verified only when every reported concept and the
    // baseline it is compared against have completed source review.
    // Superseded or rejected history rows are irrelevant here.
    if (!(p.baseline && ACCEPTED_STATUSES.has(p.baseline.review_status))) {
      return false;
    }
    const concepts = [p.position.budget, p.position.completion, p.position.status].filter(Boolean);
    return (
      concepts.length > 0 &&
      concepts.every((c) => ACCEPTED_STATUSES.has(c.review_status))
    );
  }

  function factBlock(title, scheduleText, budgetText) {
    const block = document.createElement("div");
    block.className = "t-fact";
    const h = document.createElement("h4");
    h.className = "t-fact__title";
    h.textContent = title;
    const schedule = document.createElement("p");
    schedule.className = "t-fact__value";
    schedule.textContent = scheduleText;
    const budget = document.createElement("p");
    budget.className = "t-fact__sub";
    budget.textContent = budgetText;
    block.appendChild(h);
    block.appendChild(schedule);
    block.appendChild(budget);
    return block;
  }

  // Labels keep the City's original wording; a missing value is NOT
  // REPORTED, never zero.
  function scheduleText(label, date) {
    return `Schedule: ${label || formatDate(date) || NOT_REPORTED}`;
  }

  function budgetText(label, value) {
    if (label) {
      return `Budget: ${label}`;
    }
    if (value !== null && value !== undefined) {
      return `Budget: ${value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })}`;
    }
    return `Budget: ${NOT_REPORTED}`;
  }

  function deltaLine(p) {
    const notes = [];
    const bd = p.budget_delta;
    if (bd && bd.delta !== null && isAccepted(p)) {
      let note = `Budget change: ${signedUsd(bd.delta)}`;
      if (bd.percent !== null) {
        const sign = bd.percent > 0 ? "+" : "";
        note += ` (${sign}${bd.percent}%)`;
      }
      notes.push(note);
    }
    const sd = p.schedule_delta;
    if (sd && sd.months !== null && sd.months > 0 && isAccepted(p)) {
      notes.push(`Schedule: +${sd.months} month${sd.months === 1 ? "" : "s"} (estimate)`);
    }
    return notes.join(" · ");
  }

  function signedUsd(v) {
    const sign = v > 0 ? "+" : v < 0 ? "−" : "";
    return sign + Math.abs(v).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  }

  function formatDate(iso) {
    if (!iso) {
      return "";
    }
    const parts = iso.split("-");
    const y = parts[0];
    if (parts.length === 1) {
      return y;
    }
    const m = MONTHS[parseInt(parts[1], 10) - 1] || parts[1];
    if (parts.length === 2) {
      return `${m} ${y}`;
    }
    return `${m} ${parseInt(parts[2], 10)}, ${y}`;
  }

  function stepper(p) {
    const statusCode = p.position.status && p.position.status.status_code;
    const wrap = document.createElement("div");
    wrap.className = "t-stepper";
    // Name paused and cancelled before any stage, including "unknown",
    // so the card does not announce ordinary progress.
    if (statusCode === "paused" || statusCode === "cancelled") {
      const note = document.createElement("p");
      note.className = "t-stepper__note";
      note.textContent = statusCode === "paused" ? "Paused." : "Cancelled.";
      wrap.appendChild(note);
      return wrap;
    }
    const stage = p.position.status && p.position.status.lifecycle_stage;
    if (!(stage in STAGE_STEP)) {
      const note = document.createElement("p");
      note.className = "t-stepper__note";
      note.textContent =
        stage === "unknown"
          ? "Current stage: not stated in the City record."
          : `Current stage: ${stage}.`;
      wrap.appendChild(note);
      return wrap;
    }
    const step = STAGE_STEP[stage];
    const list = document.createElement("ol");
    list.className = "t-stepper__list";
    STAGES.forEach((label, i) => {
      const li = document.createElement("li");
      li.className = "t-stepper__step" + (i < step ? " is-past" : "") + (i === step ? " is-current" : "");
      const dot = document.createElement("span");
      dot.className = "t-stepper__dot";
      dot.setAttribute("aria-hidden", "true");
      const text = document.createElement("span");
      text.className = "t-stepper__label";
      text.textContent = label;
      li.appendChild(dot);
      li.appendChild(text);
      list.appendChild(li);
    });
    // Screen readers get a concise sentence; the visual stepper is not
    // the only way to read the stage.
    const sr = document.createElement("p");
    sr.className = "sr-only";
    sr.textContent = `Current stage: ${STAGES[step]}. ${step + 1} of ${STAGES.length} stages reached.`;
    wrap.appendChild(list);
    wrap.appendChild(sr);
    return wrap;
  }

  function historyEntry(h) {
    const li = document.createElement("li");
    li.className = "t-history__entry";
    const when = document.createElement("p");
    when.className = "t-history__when";
    when.textContent = formatDate(h.reported_at) || h.reported_at;
    li.appendChild(when);
    const what = document.createElement("p");
    what.className = "t-history__what";
    const parts = [];
    if (h.budget_label) {
      parts.push(`Budget: ${h.budget_label}`);
    } else if (h.budget_usd !== null && h.budget_usd !== undefined) {
      parts.push(`Budget: ${h.budget_usd.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })}`);
    }
    if (h.completion_label || h.completion) {
      parts.push(`Schedule: ${h.completion_label || formatDate(h.completion)}`);
    }
    if (h.status_code) {
      parts.push(`Status: ${STATUS_LABELS[h.status_code] || h.status_code}`);
    }
    what.textContent = parts.join(" · ") || "Position recorded.";
    li.appendChild(what);
    if (h.change_reason) {
      const why = document.createElement("p");
      why.className = "t-history__why";
      why.textContent = `City's stated reason: ${h.change_reason}`;
      li.appendChild(why);
    }
    const src = sourceLink(h.source, h.source_pages);
    if (src) {
      const p = document.createElement("p");
      p.className = "t-history__src";
      p.appendChild(document.createTextNode("Source: "));
      p.appendChild(src);
      li.appendChild(p);
    }
    if (h.review_status && !ACCEPTED_STATUSES.has(h.review_status)) {
      const flag = document.createElement("p");
      flag.className = "t-history__flag";
      // Rejected claims and claims awaiting evidence are distinct from a
      // first review that simply has not happened yet.
      flag.textContent =
        h.review_status === "rejected"
          ? "Rejected: this entry is not shown as a current fact."
          : h.review_status === "needs_more_evidence"
            ? "Needs more evidence before this entry is verified."
            : "Verification pending on this entry.";
      li.appendChild(flag);
    }
    return li;
  }

  function evidence(p) {
    const footer = document.createElement("footer");
    footer.className = "t-card__evidence";
    const heading = document.createElement("h4");
    heading.className = "t-card__evidence-title";
    heading.textContent = "Evidence";
    footer.appendChild(heading);
    const seen = new Set();
    const links = [];
    const concepts = [p.baseline, p.position.budget, p.position.completion, p.position.status];
    for (const c of concepts) {
      if (!c || !c.source_id) {
        continue;
      }
      // Same document cited at different pages stays as two citations.
      const key = `${c.source_id}|${c.source_pages || ""}`;
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      const link = sourceLink(c.source || { source_id: c.source_id }, c.source_pages);
      if (link) {
        links.push(link);
      }
    }
    if (links.length === 0) {
      const none = document.createElement("p");
      none.textContent = "Sources: not stated.";
      footer.appendChild(none);
    } else {
      const list = document.createElement("ul");
      list.className = "t-card__sources";
      for (const link of links) {
        const li = document.createElement("li");
        li.appendChild(link);
        list.appendChild(li);
      }
      footer.appendChild(list);
    }
    return footer;
  }

  function sourceLink(source, entryPages) {
    if (!source) {
      return null;
    }
    const a = document.createElement("a");
    a.href = source.source_document_url || "#";
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    // Update-level page references win; source-level bounds are the
    // fallback when the row does not cite specific pages.
    let pages = "";
    if (entryPages) {
      pages = ` (pp. ${entryPages})`;
    } else if (source.page_start) {
      pages = ` (pp. ${source.page_start}${source.page_end && source.page_end !== source.page_start ? "-" + source.page_end : ""})`;
    }
    a.textContent = (source.document_title || source.source_id) + pages;
    return a;
  }
}
