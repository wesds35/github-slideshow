// Sanders Strength mockup — presentation-only interactivity (no backend, no persistence).

document.addEventListener("DOMContentLoaded", () => {
  // Tab groups: any [data-tabs] container toggles [data-tab-panel] visibility via [data-tab] buttons.
  document.querySelectorAll("[data-tabs]").forEach((group) => {
    const tabs = group.querySelectorAll(".tab");
    const panelSelector = group.getAttribute("data-tabs");
    const panels = document.querySelectorAll(`[data-tab-panel="${panelSelector}"]`);

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        tabs.forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        const target = tab.getAttribute("data-tab");
        panels.forEach((panel) => {
          panel.style.display = panel.getAttribute("data-tab") === target ? "" : "none";
        });
      });
    });
  });

  // Role select on splash routes to the two dashboards.
  document.querySelectorAll("[data-role-link]").forEach((card) => {
    card.addEventListener("click", () => {
      window.location.href = card.getAttribute("data-role-link");
    });
  });

  // Simple "log set" row adder for the workout logging page.
  document.querySelectorAll("[data-add-set]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const table = document.querySelector(btn.getAttribute("data-add-set"));
      if (!table) return;
      const rows = table.querySelectorAll("tbody tr");
      const nextSet = rows.length + 1;
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${nextSet}</td>
        <td><input type="number" placeholder="lb"></td>
        <td><input type="number" placeholder="reps"></td>
        <td class="muted">—</td>`;
      table.querySelector("tbody").appendChild(tr);
    });
  });
});
