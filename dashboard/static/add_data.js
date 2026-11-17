/* ==========================================================================
   add_data.js - what happens on the "Add your data" page.

   1. Switch between the two big tabs (upload / typed).
   2. The upload box: accept only .csv, stop at 20 MB, show the file name,
      and change colour while a file is dragged over it.
   3. A spinner so the page never looks frozen while a file is worked out.
   4. The typed form: check each box and keep Save disabled until it is filled.
   ========================================================================== */

(function () {
  "use strict";

  const MAX_BYTES = 20 * 1024 * 1024; // 20 MB, same limit as the server

  document.addEventListener("DOMContentLoaded", () => {
    const bigTabs = Array.from(document.querySelectorAll(".big-tab"));
    const panels = Array.from(document.querySelectorAll(".tab-panel"));

    // ---------------------------------------------------------------
    // 1. The two big tabs
    // ---------------------------------------------------------------
    function showTab(name) {
      bigTabs.forEach((tab) => {
        tab.setAttribute("aria-pressed", tab.dataset.tab === name ? "true" : "false");
      });
      panels.forEach((panel) => {
        panel.hidden = panel.dataset.panel !== name;
      });
    }

    bigTabs.forEach((tab) => {
      tab.addEventListener("click", () => showTab(tab.dataset.tab));
    });

    // ---------------------------------------------------------------
    // 2. The upload box
    // ---------------------------------------------------------------
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("csv-file");
    const uploadName = document.getElementById("upload-name");
    const uploadButton = document.getElementById("upload-btn");
    const chosenName = document.getElementById("dropzone-file");
    const uploadForm = document.getElementById("upload-form");

    // A plain message under the box. `bad` makes it red.
    function sayUpload(text, bad) {
      if (!uploadName) return;
      uploadName.textContent = text;
      uploadName.classList.toggle("field-error", Boolean(bad));
    }

    // Returns true when the file is acceptable.
    function checkFile(file) {
      if (!file) {
        sayUpload("No file chosen yet.", false);
        if (uploadButton) uploadButton.disabled = true;
        if (chosenName) chosenName.hidden = true;
        return false;
      }

      if (!file.name.toLowerCase().endsWith(".csv")) {
        sayUpload("Please upload a CSV file.", true);
        if (uploadButton) uploadButton.disabled = true;
        if (chosenName) chosenName.hidden = true;
        return false;
      }

      if (file.size > MAX_BYTES) {
        sayUpload("That file is too big. The largest size is 20 MB.", true);
        if (uploadButton) uploadButton.disabled = true;
        if (chosenName) chosenName.hidden = true;
        return false;
      }

      const kb = Math.max(1, Math.round(file.size / 1024));
      sayUpload(`Ready to upload: ${file.name} (${kb.toLocaleString()} KB)`, false);
      if (chosenName) {
        chosenName.textContent = file.name;
        chosenName.hidden = false;
      }
      if (uploadButton) uploadButton.disabled = false;
      return true;
    }

    if (fileInput) {
      fileInput.addEventListener("change", () => checkFile(fileInput.files[0]));
    }

    // Drag and drop. The label is the drop target.
    if (dropzone) {
      ["dragenter", "dragover"].forEach((eventName) => {
        dropzone.addEventListener(eventName, (event) => {
          event.preventDefault();
          dropzone.classList.add("is-dragging");
        });
      });

      ["dragleave", "drop"].forEach((eventName) => {
        dropzone.addEventListener(eventName, (event) => {
          event.preventDefault();
          dropzone.classList.remove("is-dragging");
        });
      });

      dropzone.addEventListener("drop", (event) => {
        const file = event.dataTransfer && event.dataTransfer.files[0];
        if (!file || !fileInput) return;
        // Put the dropped file into the real file box, so the form sends it.
        const transfer = new DataTransfer();
        transfer.items.add(file);
        fileInput.files = transfer.files;
        checkFile(file);
      });
    }

    // Reset clears the chosen file.
    const uploadReset = document.getElementById("upload-reset");
    if (uploadReset) {
      uploadReset.addEventListener("click", () => {
        if (uploadForm) uploadForm.reset();
        if (fileInput) fileInput.value = "";
        checkFile(null);
      });
    }

    // ---------------------------------------------------------------
    // 3. The spinner
    // ---------------------------------------------------------------
    const spinner = document.getElementById("spinner");

    function showSpinner() {
      if (spinner) spinner.hidden = false;
    }

    if (uploadForm) {
      uploadForm.addEventListener("submit", (event) => {
        const file = fileInput && fileInput.files[0];
        if (!checkFile(file)) {
          event.preventDefault();
          return;
        }
        showSpinner();
      });
    }

    // ---------------------------------------------------------------
    // 4. The typed form
    // ---------------------------------------------------------------
    const typedForm = document.getElementById("typed-form");
    if (typedForm) {
      const inputs = Array.from(typedForm.querySelectorAll("input[data-key]"));
      const saveButton = document.getElementById("save-btn");
      const resetButton = document.getElementById("reset-btn");
      const innerTab = document.getElementById("typed-tab");
      const innerButtons = Array.from(document.querySelectorAll(".tab-btn"));
      const innerPanels = Array.from(document.querySelectorAll(".inner-panel"));

      // Switch between "Type each number" and "Type a list".
      innerButtons.forEach((button) => {
        button.addEventListener("click", () => {
          const name = button.dataset.innerTab;
          innerButtons.forEach((b) => {
            b.setAttribute("aria-pressed", b.dataset.innerTab === name ? "true" : "false");
          });
          innerPanels.forEach((panel) => {
            panel.hidden = panel.dataset.innerPanel !== name;
          });
          if (innerTab) innerTab.value = name;
          refreshSave();
        });
      });

      // A box is fine when it holds a whole number of 0 or more.
      function checkBox(input) {
        const raw = input.value.trim();
        if (raw === "") return "Please type a number here.";
        if (!/^\d+$/.test(raw)) return "Please type a whole number, like 10. No letters or dots.";
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

      function refreshSave() {
        // The list tab is read on the server, so Save is allowed there.
        const onList = innerTab && innerTab.value === "list";
        const allFilled = inputs.every((input) => checkBox(input) === "");
        if (saveButton) saveButton.disabled = onList ? false : !allFilled;
      }

      inputs.forEach((input) => {
        input.addEventListener("blur", () => {
          showError(input, checkBox(input));
          refreshSave();
        });
        input.addEventListener("input", () => {
          if (input.classList.contains("has-error")) showError(input, checkBox(input));
          refreshSave();
        });
      });

      if (resetButton) {
        resetButton.addEventListener("click", () => {
          typedForm.reset();
          inputs.forEach((input) => showError(input, ""));
          refreshSave();
          if (inputs[0]) inputs[0].focus();
        });
      }

      typedForm.addEventListener("submit", (event) => {
        const onList = innerTab && innerTab.value === "list";
        if (onList) {
          showSpinner();
          return;
        }

        let firstBad = null;
        inputs.forEach((input) => {
          const message = checkBox(input);
          showError(input, message);
          if (message && !firstBad) firstBad = input;
        });

        if (firstBad) {
          event.preventDefault();
          firstBad.focus();
          return;
        }
        showSpinner();
      });

      refreshSave();
    }
  });
})();
