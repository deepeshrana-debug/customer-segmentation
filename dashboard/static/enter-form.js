/* ==========================================================================
   enter-form.js - everything that happens inside the form.

   1. Switch between the "Type each number" and "Type a list" tabs.
   2. Check the boxes in the browser so mistakes show up straight away,
      without waiting for the server.
   3. Keep the Save button disabled until every box holds a whole number.
   4. Clear the form with the Reset button.
   ========================================================================== */

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("enter-form");
    if (!form) return;

    const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
    const tabField = document.getElementById("tab-field");
    const saveBtn = document.getElementById("save-btn");
    const resetBtn = document.getElementById("reset-btn");
    const inputs = Array.from(form.querySelectorAll("input[data-key]"));

    // ---------------------------------------------------------------
    // 1. Tabs
    // ---------------------------------------------------------------
    function showTab(name) {
      tabButtons.forEach((b) => {
        b.setAttribute("aria-pressed", b.dataset.tab === name ? "true" : "false");
      });
      form.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.hidden = panel.dataset.panel !== name;
      });
      if (tabField) tabField.value = name;
    }

    tabButtons.forEach((btn) => {
      btn.addEventListener("click", () => showTab(btn.dataset.tab));
    });

    // ---------------------------------------------------------------
    // 2. Checks for one box
    // ---------------------------------------------------------------
    // A box is fine when it holds a whole number of 0 or more.
    function checkBox(input) {
      const raw = input.value.trim();
      if (raw === "") return "Please type a number here.";
      if (!/^\d+$/.test(raw)) return "Please type a whole number, like 10.";
      return "";
    }

    function showError(input, message) {
      input.classList.toggle("has-error", Boolean(message));
      input.setAttribute("aria-invalid", message ? "true" : "false");

      const box = document.getElementById("error-" + input.dataset.key);
      if (box) {
        box.textContent = message;
        box.hidden = !message;
      }
    }

    // ---------------------------------------------------------------
    // 3. Save button stays disabled until every box is filled
    // ---------------------------------------------------------------
    function refreshSaveButton() {
      // Only the boxes on the visible tab block saving. On the list tab the
      // server does the reading, so we let the owner press Save.
      const onListTab = tabField && tabField.value === "list";
      const allFilled = inputs.every((input) => checkBox(input) === "");
      if (saveBtn) saveBtn.disabled = onListTab ? false : !allFilled;
    }

    inputs.forEach((input) => {
      // Show a message as soon as the owner leaves a box.
      input.addEventListener("blur", () => {
        showError(input, checkBox(input));
        refreshSaveButton();
      });
      input.addEventListener("input", () => {
        if (input.classList.contains("has-error")) {
          showError(input, checkBox(input));
        }
        refreshSaveButton();
      });
    });

    // ---------------------------------------------------------------
    // 4. Reset
    // ---------------------------------------------------------------
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        form.reset();
        inputs.forEach((input) => showError(input, ""));
        refreshSaveButton();
        const first = inputs[0];
        if (first) first.focus();
      });
    }

    // Final check when the owner presses Save: stop the page if anything
    // is wrong, and show the message next to the bad boxes.
    form.addEventListener("submit", (event) => {
      const onListTab = tabField && tabField.value === "list";
      if (onListTab) return; // the list tab is checked on the server

      let firstBad = null;
      inputs.forEach((input) => {
        const message = checkBox(input);
        showError(input, message);
        if (message && !firstBad) firstBad = input;
      });

      if (firstBad) {
        event.preventDefault();
        firstBad.focus();
      }
    });

    // Start with the right tab showing and the button in the right state.
    const openTab = tabField ? tabField.value : "form";
    showTab(openTab);
    refreshSaveButton();
  });
})();
