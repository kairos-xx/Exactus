/* Offline dashboard. Checklist data is text, never executable HTML. */
(() => {
  /**
   * Find a dashboard control by its stable DOM identifier.
   * @param {string} id - Identifier in the dashboard template.
   * @returns {any} Matching control; the template always provides it.
   * @throws {Error} When the template lacks the control.
   */
  const byId = id => {
    const element = document.getElementById(id);
    if (!element) throw new Error(`The dashboard template has no #${id}.`);
    return element;
  };
  const data = JSON.parse(byId("task-data").textContent);
  /** @type {TodoTask[]} */
  const tasks = data.tasks;
  const state = {
    query: "",
    group: "none",
    sort: "document",
    filters: new Map(),
    theme: "dark",
    view: "tasks",
  };
  const fields = [
    "status",
    "category",
    "priority",
    "workstream",
    "prefix",
    "ongoing",
  ];
  /**
   * Create a DOM element using text content rather than HTML parsing.
   * @param {string} tag - HTML element name.
   * @param {string|number} text - Literal display text.
   * @param {string} className - Space-separated styling classes.
   * @returns {any} Newly created element.
   */
  const node = (tag, text = "", className = "") => {
    const element = document.createElement(tag);
    element.textContent = String(text);
    element.className = className;
    return element;
  };
  /**
   * Map task fields to human-readable facet values.
   * @param {TodoTask} task - Parsed checklist task and its metadata.
   * @param {string} field - Facet field to display.
   * @returns {string} Facet value used for filtering and grouping.
   */
  const value = (task, field) =>
    field === "status"
      ? task.done
        ? "Done"
        : "Open"
      : field === "ongoing"
        ? task.ongoing
          ? "ONGOING"
          : "Not ongoing"
        : String(task[field] || "None");
  /**
   * Normalize text for case-insensitive subsequence matching.
   * @param {string} text - Query token or searchable task text.
   * @returns {string} Lowercase Unicode-normalized text.
   */
  const normalize = text =>
    String(text).toLocaleLowerCase().normalize("NFKD");
  // Exact tokens outrank subsequences; all query tokens must match.
  /**
   * Rank a task against every query token, preferring exact matches.
   * @param {TodoTask} task - Task containing identifiers and searchable text.
   * @returns {number} Nonnegative relevance score, or -1 for a nonmatch.
   */
  const score = task => {
    const haystack = normalize(
      [task.id, task.text, task.priority, ...task.wpath].join(" "),
    );
    let total = 0;
    for (const token of normalize(state.query)
      .trim()
      .split(/\s+/)
      .filter(Boolean)) {
      if (haystack.includes(token)) {
        total += 100;
        continue;
      }
      let position = 0;
      for (const letter of haystack)
        if (letter === token[position]) position += 1;
      if (position !== token.length) return -1;
      total += 10;
    }
    return total;
  };
  /**
   * Check the query and all active facet selections for a task.
   * @param {TodoTask} task - Task whose metadata is compared with filters.
   * @param {string} ignored - Facet omitted when calculating choice counts.
   * @returns {boolean} Whether the task satisfies the remaining filters.
   */
  const matches = (task, ignored = "") =>
    fields.every(field => {
      const selected = state.filters.get(field);
      return (
        field === ignored || !selected?.size || selected.has(value(task, field))
      );
    }) && score(task) >= 0;
  /** Store view, query and facet selections in the local URL fragment. */
  const persist = () => {
    const payload = {
      ...state,
      filters: [...state.filters].map(([key, values]) => [key, [...values]]),
    };
    // URL fragments stay local and make state shareable without storage access.
    history.replaceState(
      null,
      "",
      `${location.pathname}${location.search}#s=${encodeURIComponent(JSON.stringify(payload))}`,
    );
  };
  /**
   * Switch between filtered task cards and the verbatim source document.
   * @param {string} view - Requested view: tasks or doc.
   */
  const setView = view => {
    state.view = view;
    const documentView = view === "doc";
    byId("docWorkspace").hidden = !documentView;
    /** @type {HTMLElement} */ (document.querySelector(".layout")).hidden =
      documentView;
    byId("tabDoc").classList.toggle("active", documentView);
    byId("tabTasks").classList.toggle("active", !documentView);
    byId("tabDoc").setAttribute("aria-pressed", String(documentView));
    byId("tabTasks").setAttribute("aria-pressed", String(!documentView));
    persist();
  };
  /**
   * Create a source link that opens and scrolls the document view.
   * @param {string} text - Literal link label.
   * @param {number} line - One-based source line to reveal.
   * @param {string} className - Styling classes for the link.
   * @returns {HTMLAnchorElement} Link with a document-view click handler.
   */
  const lineLink = (text, line, className = "") => {
    const anchor = node("a", text, className);
    anchor.href = `#L${line}`;
    anchor.addEventListener("click", (/** @type {Event} */ event) => {
      event.preventDefault();
      setView("doc");
      byId(`L${line}`)?.scrollIntoView({
        block: "center",
      });
    });
    return anchor;
  };
  /**
   * Rebuild facet choices and counts while preserving selection state.
   * @param {() => void} onChange - Re-render callback after selection.
   */
  const renderFilters = onChange => {
    const root = byId("dynamicFilters");
    root.replaceChildren();
    for (const field of fields) {
      const wrapper = node("section", "", "filter");
      wrapper.append(
        node("div", field === "prefix" ? "ID prefix" : field, "filter-title"),
      );
      const choices = node("div", "", "choices");
      const values = [
        ...new Set(tasks.map(task => value(task, field))),
      ].sort();
      for (const label of values) {
        const button = node("button", "", "chip");
        button.type = "button";
        const selected = state.filters.get(field)?.has(label) || false;
        button.classList.toggle("active", selected);
        button.setAttribute("aria-pressed", String(selected));
        button.append(
          node("span", label),
          node(
            "span",
            tasks.filter(
              task => matches(task, field) && value(task, field) === label,
            ).length,
            "count",
          ),
        );
        button.addEventListener("click", () => {
          const filters = state.filters.get(field) || new Set();
          if (filters.has(label)) filters.delete(label);
          else filters.add(label);
          state.filters.set(field, filters);
          onChange();
          // Rebuilt filter controls retain keyboard focus.
          [...byId("dynamicFilters").querySelectorAll("button")]
            .find(
              item =>
                item.getAttribute("data-field") === field &&
                item.getAttribute("data-label") === label,
            )
            ?.focus();
        });
        button.dataset.field = field;
        button.dataset.label = label;
        choices.append(button);
      }
      wrapper.append(choices);
      root.append(wrapper);
    }
  };
  /**
   * Render one task card with status, category and source breadcrumbs.
   * @param {TodoTask} task - Checklist task with labels and source locations.
   * @returns {HTMLElement} Completed task card ready for insertion.
   */
  const renderTask = task => {
    const article = node("article", "", `task${task.done ? " done" : ""}`);
    article.dataset.priority = task.priority;
    const body = node("div", "", "task-body");
    const header = node("div", "", "task-header");
    header.append(lineLink(task.id || "UNTAGGED", task.line, "task-id"));
    if (task.priority)
      header.append(
        node(
          "span",
          task.priority,
          `badge priority ${task.priority.toLowerCase()}`,
        ),
      );
    header.append(node("span", task.category, "badge category"));
    if (task.ongoing) header.append(node("span", "ONGOING", "badge ongoing"));
    header.append(node("span", task.done ? "Done" : "Open", "task-status"));
    body.append(header, lineLink(task.text, task.line, "task-title"));
    const context = node("div", "", "task-context");
    const breadcrumb = node("div", "", "breadcrumb");
    task.wpath.forEach((part, index) => {
      if (index) breadcrumb.append(node("span", " / "));
      breadcrumb.append(lineLink(part, task.wlines[index] ?? 0, "crumb"));
    });
    context.append(
      breadcrumb,
      lineLink(`Source · line ${task.line}`, task.line, "task-source"),
    );
    body.append(context);
    article.append(node("div", "", "task-rail"), body);
    return article;
  };
  /** Rebuild sorted task groups, statistics and facets from current state. */
  const render = () => {
    const rows = tasks.filter(task => matches(task));
    rows.sort((a, b) => {
      if (state.sort === "relevance")
        return score(b) - score(a) || a.line - b.line;
      if (state.sort === "document") return a.line - b.line;
      return (
        String(a[state.sort] || "ZZZ").localeCompare(
          String(b[state.sort] || "ZZZ"),
          undefined,
          {
            numeric: true,
          },
        ) || a.line - b.line
      );
    });
    const root = byId("tasks");
    root.replaceChildren();
    if (!rows.length)
      root.append(
        node(
          "div",
          "No matching tasks. Broaden a filter or clear the search.",
          "empty",
        ),
      );
    /** @type {Map<string, TodoTask[]>} */
    const groups = new Map();
    for (const task of rows) {
      const key = state.group === "none" ? "" : value(task, state.group);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)?.push(task);
    }
    for (const [key, group] of groups) {
      if (key) {
        const summary = node("section", "", "group-card");
        summary.append(
          node("div", key, "group-name"),
          node(
            "span",
            `${group.length} tasks · ${group.filter((task) => !task.done).length} open`,
            "group-count",
          ),
        );
        root.append(summary);
      }
      group.forEach(task => {
        root.append(renderTask(task));
      });
    }
    const done = tasks.filter(task => task.done).length;
    byId("matching").textContent = rows.length.toLocaleString();
    byId("matchingFoot").textContent = `of ${tasks.length} total`;
    byId("openStat").textContent = rows.filter(task => !task.done).length;
    byId("p0Stat").textContent = rows.filter(
      task => !task.done && task.priority === "P0",
    ).length;
    byId("completion").textContent =
      `${tasks.length ? ((done / tasks.length) * 100).toFixed(1) : "0.0"}%`;
    byId("completionFoot").textContent =
      `${done} done · ${tasks.length - done} open`;
    byId("resultTitle").textContent = `${rows.length} matching tasks`;
    byId("resultSub").textContent =
      [...state.filters.values()]
        .flatMap(values => [...values])
        .join(" · ") || "All tasks";
    renderFilters(render);
    persist();
  };
  const source = byId("docView");
  const nav = byId("docNav");
  // Verbatim source retains code, comments, table text and acceptance evidence.
  data.md
    .split("\n")
    .forEach((/** @type {string} */ text, /** @type {number} */ index) => {
      const line = node("div", text || " ", "source-line");
      line.id = `L${index + 1}`;
      source.append(line);
      const heading = /^(#{1,3})\s+(.+)/.exec(text);
      if (heading)
        nav.append(lineLink(heading[2] ?? "", index + 1, "doc-nav-link"));
    });
  try {
    const saved = JSON.parse(
      decodeURIComponent(location.hash.match(/^#s=(.*)$/)?.[1] || "null"),
    );
    if (saved && typeof saved === "object") {
      if (typeof saved.query === "string") state.query = saved.query;
      if (
        ["none", "category", "priority", "workstream", "prefix"].includes(
          saved.group,
        )
      )
        state.group = saved.group;
      if (
        ["document", "relevance", "priority", "category", "id"].includes(
          saved.sort,
        )
      )
        state.sort = saved.sort;
      if (["light", "dark"].includes(saved.theme)) state.theme = saved.theme;
      if (["tasks", "doc"].includes(saved.view)) state.view = saved.view;
      if (Array.isArray(saved.filters))
        for (const pair of saved.filters) {
          if (
            Array.isArray(pair) &&
            fields.includes(pair[0]) &&
            Array.isArray(pair[1]) &&
            pair[1].every(item => typeof item === "string")
          )
            state.filters.set(pair[0], new Set(pair[1]));
        }
    }
  } catch {
    /* A malformed URL state must not prevent rendering. */
  }
  byId("search").value = state.query;
  byId("search").setAttribute("aria-label", "Search tasks");
  byId("group").value = state.group;
  byId("group").setAttribute("aria-label", "Group results");
  byId("sort").value = state.sort;
  byId("sort").setAttribute("aria-label", "Sort tasks");
  document.documentElement.setAttribute("data-theme", state.theme);
  byId("search").addEventListener("input", () => {
    state.query = byId("search").value;
    render();
  });
  byId("group").addEventListener("change", () => {
    state.group = byId("group").value;
    render();
  });
  byId("sort").addEventListener("change", () => {
    state.sort = byId("sort").value;
    render();
  });
  byId("reset").addEventListener("click", () => {
    state.filters.clear();
    state.query = "";
    state.group = "none";
    state.sort = "document";
    byId("search").value = "";
    byId("group").value = "none";
    byId("sort").value = "document";
    render();
  });
  byId("theme").addEventListener("click", () => {
    state.theme = state.theme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", state.theme);
    persist();
  });
  byId("tabTasks").addEventListener("click", () => setView("tasks"));
  byId("tabDoc").addEventListener("click", () => setView("doc"));
  byId("mobileFilter").addEventListener("click", () => {
    const expanded = byId("filters").classList.toggle("open");
    byId("mobileFilter").setAttribute("aria-expanded", String(expanded));
  });
  byId("mobileFilter").setAttribute("aria-controls", "filters");
  byId("export").addEventListener("click", () => {
    const blob = new Blob(
      [
        JSON.stringify(
          tasks.filter(task => matches(task)),
          null,
          2,
        ),
      ],
      {
        type: "application/json",
      },
    );
    const anchor = node("a");
    const url = URL.createObjectURL(blob);
    anchor.href = url;
    anchor.download = "todo-filtered.json";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  });
  document.addEventListener("keydown", event => {
    if (
      event.key === "/" &&
      !["INPUT", "SELECT", "TEXTAREA"].includes(
        document.activeElement?.tagName ?? "",
      )
    ) {
      event.preventDefault();
      byId("search").focus();
    }
    if (event.key === "Escape" && document.activeElement === byId("search")) {
      state.query = "";
      byId("search").value = "";
      render();
    }
  });
  render();
  setView(state.view);
})();
