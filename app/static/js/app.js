// Небольшие улучшения интерфейса «Логоса».
(function () {
  const textarea = document.querySelector(".editor-form textarea");
  if (textarea) {
    const resize = () => {
      textarea.style.height = "auto";
      textarea.style.height = Math.max(textarea.scrollHeight, 260) + "px";
    };
    textarea.addEventListener("input", resize);
    resize();
  }

  // Плавно убрать сообщения об успехе.
  document.querySelectorAll(".flash-success").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity .6s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 600);
    }, 4000);
  });
})();
