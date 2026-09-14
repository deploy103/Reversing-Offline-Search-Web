// Light/dark theme toggle. Hand-written, no dependencies.
// Stores choice in localStorage("theme") = "light" | "dark".
// Falls back to prefers-color-scheme when no explicit choice was made.
(function () {
  "use strict";

  function applyTheme(theme) {
    if (theme === "light" || theme === "dark") {
      document.documentElement.setAttribute("data-theme", theme);
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }

  function currentTheme() {
    try {
      return window.localStorage.getItem("theme");
    } catch (e) {
      return null;
    }
  }

  function setTheme(theme) {
    try {
      window.localStorage.setItem("theme", theme);
    } catch (e) {
      // localStorage unavailable (e.g. some file:// sandboxes) -- ignore.
    }
    applyTheme(theme);
    updateButtonLabel();
  }

  function effectiveIsDark() {
    var stored = currentTheme();
    if (stored === "dark") return true;
    if (stored === "light") return false;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function updateButtonLabel() {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.textContent = effectiveIsDark() ? "라이트 모드" : "다크 모드";
  }

  // Apply stored preference immediately (before DOMContentLoaded) to avoid flash.
  applyTheme(currentTheme());

  document.addEventListener("DOMContentLoaded", function () {
    updateButtonLabel();
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        setTheme(effectiveIsDark() ? "light" : "dark");
      });
    }
  });
})();
