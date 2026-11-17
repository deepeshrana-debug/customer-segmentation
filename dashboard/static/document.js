/* ==========================================================================
   document.js - the "Upload a document" tab on the "Add your data" page.

   Accepts a Word file (.docx), a PDF, or a plain text file (.txt / .md),
   stops at 20 MB, shows the chosen file name, lets a file be dragged in,
   and shows the spinner while the server reads the numbers out.
   ========================================================================== */

(function () {
  "use strict";

  const MAX_BYTES = 20 * 1024 * 1024; // 20 MB, same limit as the server
  const KINDS = [".docx", ".pdf", ".txt", ".md"];

  document.addEventListener("DOMContentLoaded", () => {
    const dropzone = document.getElementById("document-drop");
    const fileInput = document.getElementById("document-file");
    const fileName = document.getElementById("document-file-name");
    const readButton = document.getElementById("document-btn");
    const form = document.getElementById("document-form");
    const resetButton = document.getElementById("document-reset");
    const spinner = document.getElementById("spinner");

    if (!fileInput) return;

    // A plain message under the box. `bad` makes it red.
    function say(text, bad) {
      if (!fileName) return;
      fileName.textContent = text;
      fileName.classList.toggle("field-error", Boolean(bad));
      fileName.hidden = !text;
    }

    // Returns true when the file is acceptable.
    function check(file) {
      if (!file) {
        say("", false);
        if (readButton) readButton.disabled = true;
        return false;
      }

      const name = file.name.toLowerCase();
      if (!KINDS.some((kind) => name.endsWith(kind))) {
        say("Please choose a Word file, a PDF, or a plain text file.", true);
        if (readButton) readButton.disabled = true;
        return false;
      }

      if (file.size > MAX_BYTES) {
        say("That file is too big. The largest size is 20 MB.", true);
        if (readButton) readButton.disabled = true;
        return false;
      }

      const kb = Math.max(1, Math.round(file.size / 1024));
      say(`${file.name} (${kb.toLocaleString()} KB)`, false);
      if (readButton) readButton.disabled = false;
      return true;
    }

    fileInput.addEventListener("change", () => check(fileInput.files[0]));

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
        if (!file) return;
        // Put the dropped file into the real file box, so the form sends it.
        const transfer = new DataTransfer();
        transfer.items.add(file);
        fileInput.files = transfer.files;
        check(file);
      });
    }

    if (resetButton) {
      resetButton.addEventListener("click", () => {
        if (form) form.reset();
        fileInput.value = "";
        check(null);
      });
    }

    if (form) {
      form.addEventListener("submit", (event) => {
        if (!check(fileInput.files[0])) {
          event.preventDefault();
          return;
        }
        if (spinner) spinner.hidden = false;
      });
    }

    // Coming back filled in from a document? Nothing to pick, but keep the
    // page consistent if the button was rendered disabled.
    check(null);
  });
})();
