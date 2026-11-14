/* One set of original content nodes: a table on desktop, labelled cards on phones. */
(function () {
  "use strict";
  var phone = window.matchMedia("(max-width: 767px)");
  var known = new WeakMap();
  var active = [];
  var sequence = 0;

  function restore(state) {
    if (!state.cards) return;
    state.fields.forEach(function (field) {
      if (field.placeholder) field.value.textContent = "";
      while (field.value.firstChild) field.cell.appendChild(field.value.firstChild);
    });
    state.cards.remove();
    state.cards = null;
    state.fields = [];
  }

  function showCards(state) {
    if (state.cards) return;
    var cards = document.createElement("div");
    cards.className = "mineral-cards";
    state.rows.forEach(function (row, rowIndex) {
      var card = document.createElement("div");
      card.className = "mineral-card";
      if (state.rows.length > 1) {
        var title = document.createElement("p");
        title.className = "mineral-card__title";
        var identity = state.identityColumn >= 0 ? row.cells[state.identityColumn] : null;
        title.textContent = identity && identity.textContent.trim() || "Registro " + (rowIndex + 1);
        card.appendChild(title);
      }
      var properties = document.createElement("dl");
      Array.from(row.cells).forEach(function (cell, index) {
        var field = document.createElement("div");
        field.className = "mineral-card__field";
        var label = document.createElement("dt");
        label.textContent = state.labels[index];
        var value = document.createElement("dd");
        value.className = "mineral-card__value";
        while (cell.firstChild) value.appendChild(cell.firstChild);
        var placeholder = !value.childNodes.length;
        if (placeholder) value.textContent = "—";
        field.append(label, value);
        properties.appendChild(field);
        state.fields.push({cell: cell, value: value, placeholder: placeholder});
      });
      card.appendChild(properties);
      cards.appendChild(card);
    });
    state.host.insertBefore(cards, state.wrapper);
    state.cards = cards;
  }

  function render(state) {
    var useCards = phone.matches && state.preferCards;
    if (useCards) showCards(state);
    else restore(state);
    state.wrapper.hidden = useCards;
    state.button.textContent = useCards ? "Ver como tabla" : "Ver como ficha";
    state.button.setAttribute("aria-expanded", String(!useCards));
  }

  function enhance() {
    active = [];
    document.querySelectorAll("article table").forEach(function (table) {
      var existing = known.get(table);
      if (existing) {
        active.push(existing);
        render(existing);
        return;
      }
      var headers = Array.from(table.querySelectorAll("thead tr:first-child th"));
      var rows = Array.from(table.querySelectorAll("tbody > tr"));
      if (headers.length < 2 || !rows.length) return;
      if (headers.length === 2 && !table.querySelector("img")) return;
      if (table.querySelector("[colspan], [rowspan]")) return;
      if (rows.some(function (row) { return row.cells.length !== headers.length; })) return;
      var wrapper = table.closest(".md-typeset__scrollwrap") || table;
      var host = wrapper.parentNode;
      var toolbar = document.createElement("div");
      toolbar.className = "mineral-table-controls";
      var hint = document.createElement("span");
      hint.textContent = "Lectura en móvil";
      var button = document.createElement("button");
      button.type = "button";
      button.className = "mineral-table-toggle";
      var id = "mineral-table-" + (++sequence);
      /* Do not replace user-authored IDs or fragment links. */
      if (!wrapper.id) wrapper.id = id;
      button.setAttribute("aria-controls", wrapper.id);
      toolbar.append(hint, button);
      host.insertBefore(toolbar, wrapper);
      var labels = headers.map(function (header) { return header.textContent.trim(); });
      var state = {
        wrapper: wrapper, host: host, rows: rows, labels: labels,
        identityColumn: labels.findIndex(function (label) { return /^(fuente|mineral)$/i.test(label); }),
        button: button, preferCards: true, cards: null, fields: []
      };
      button.addEventListener("click", function () {
        state.preferCards = !state.preferCards;
        render(state);
      });
      known.set(table, state);
      active.push(state);
      render(state);
    });
  }

  if (phone.addEventListener) phone.addEventListener("change", function () { active.forEach(render); });
  else phone.addListener(function () { active.forEach(render); });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", enhance);
  else enhance();
  if (typeof document$ !== "undefined") document$.subscribe(enhance);
}());
