/* ==========================================================================
   theme.js - the light / dark switch, shared by the enter and entries pages.

   The choice is saved in localStorage. If the owner has never picked one, we
   follow whatever the computer is set to. Colours themselves live in
   styles.css as CSS variables, so this file only flips an attribute.
   ========================================================================== */

(function () {
  "use strict";

  const KEY = "segmentation-theme";

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") || "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(KEY, theme);

    const btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
      const label = document.getElementById("theme-label");
      if (label) label.textContent = theme === "dark" ? "Light" : "Dark";
    }

    // Let any page that draws charts know the colours have changed.
    document.dispatchEvent(new CustomEvent("themechange", { detail: { theme } }));
  }

  document.addEventListener("DOMContentLoaded", () => {
    const stored = localStorage.getItem(KEY);
    const systemDark =
      window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(stored || (systemDark ? "dark" : "light"));

    const btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", () => {
        applyTheme(currentTheme() === "dark" ? "light" : "dark");
      });
    }

    // Follow the computer's setting while the owner has not chosen one.
    if (!stored && window.matchMedia) {
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (event) => {
        if (!localStorage.getItem(KEY)) applyTheme(event.matches ? "dark" : "light");
      });
    }
  });
})();
