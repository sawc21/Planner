(() => {
  "use strict";

  document.querySelectorAll("[data-autosubmit] input[type='checkbox']").forEach((checkbox) => {
    checkbox.addEventListener("change", () => checkbox.form?.requestSubmit());
  });

  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const prompt = form.dataset.confirm;
      if (prompt && !window.confirm(prompt)) {
        event.preventDefault();
        return;
      }
      form.classList.add("is-submitting");
      form.querySelectorAll("button[type='submit']").forEach((button) => {
        button.setAttribute("aria-disabled", "true");
      });
    });
  });

  document.querySelectorAll("[data-dismiss]").forEach((button) => {
    button.addEventListener("click", () => button.closest("[data-flash]")?.remove());
  });

  document.querySelectorAll("[data-go-back]").forEach((button) => {
    button.addEventListener("click", () => {
      if (history.length > 1) {
        history.back();
      } else {
        window.location.assign("/");
      }
    });
  });
})();
