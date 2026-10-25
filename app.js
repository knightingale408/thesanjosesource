(() => {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const reveals = document.querySelectorAll("[data-reveal]");
  if (reduceMotion || !("IntersectionObserver" in window)) {
    reveals.forEach((el) => el.classList.add("is-in"));
  } else {
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            io.unobserve(entry.target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 }
    );
    reveals.forEach((el) => io.observe(el));
  }

  const form = document.getElementById("subscribe-form");
  const email = document.getElementById("email");
  const status = document.getElementById("subscribe-status");
  const note = document.getElementById("subscribe-note");

  if (!form || !email || !status) return;

  const SUBSTACK_SUBSCRIBE = "https://thesanjosesource.substack.com/subscribe";

  function looksLikeEmail(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  }

  form.addEventListener("submit", (event) => {
    const value = String(email.value || "").trim().toLowerCase();
    if (!looksLikeEmail(value)) {
      event.preventDefault();
      showStatus("Enter a valid email address.", "error");
      email.focus();
      return;
    }

    // Prefer Substack’s no-JS form POST; if that path fails in some browsers,
    // fall back to the subscribe page with email prefilled.
    showStatus("Opening Substack to confirm your subscription…", "ok");
    window.setTimeout(() => {
      if (document.visibilityState === "visible") {
        const url = new URL(SUBSTACK_SUBSCRIBE);
        url.searchParams.set("email", value);
        window.open(url.toString(), "_blank", "noopener,noreferrer");
      }
    }, 1200);
  });

  function showStatus(message, kind) {
    status.hidden = false;
    status.textContent = message;
    status.dataset.kind = kind;
    if (note) note.hidden = kind === "ok";
  }
})();
