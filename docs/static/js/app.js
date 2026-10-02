// Интерфейс «Логоса»: тема, прогресс чтения, мелкие улучшения.
(function () {
  const root = document.documentElement;

  /* ---------- Тема ---------- */
  const toggle = document.getElementById("theme-toggle");
  const icon = toggle ? toggle.querySelector(".theme-icon") : null;

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    if (icon) icon.textContent = theme === "dark" ? "☀️" : "🌙";
    if (toggle) toggle.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
  }

  applyTheme(root.getAttribute("data-theme") || "light");

  if (toggle) {
    toggle.addEventListener("click", () => {
      const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
      try { localStorage.setItem("logos-theme", next); } catch (e) {}
    });
  }

  /* ---------- Прогресс чтения ---------- */
  const bar = document.getElementById("reading-progress");
  const article = document.querySelector(".post .prose");
  if (bar && article) {
    const update = () => {
      const start = article.offsetTop;
      const total = article.offsetHeight - window.innerHeight;
      const passed = window.scrollY - start;
      const ratio = total > 0 ? Math.min(1, Math.max(0, passed / total)) : 0;
      bar.style.width = (ratio * 100) + "%";
    };
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();
  }

  /* ---------- Копировать ссылку ---------- */
  const copyBtn = document.getElementById("copy-link");
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const original = copyBtn.textContent;
      try {
        await navigator.clipboard.writeText(window.location.href);
        copyBtn.textContent = "Ссылка скопирована ✓";
      } catch (e) {
        copyBtn.textContent = "Не удалось скопировать";
      }
      setTimeout(() => { copyBtn.textContent = original; }, 2000);
    });
  }

  /* ---------- Автовысота поля ввода ---------- */
  const textarea = document.querySelector(".editor-form textarea");
  if (textarea) {
    const resize = () => {
      textarea.style.height = "auto";
      textarea.style.height = Math.max(textarea.scrollHeight, 260) + "px";
    };
    textarea.addEventListener("input", resize);
    resize();
  }

  /* ---------- Подтверждение удаления ---------- */
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  /* ---------- Скрыть сообщения об успехе ---------- */
  document.querySelectorAll(".flash-success").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity .6s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 600);
    }, 4000);
  });
})();
