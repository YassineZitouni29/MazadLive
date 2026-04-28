function formatCountdown(targetDate) {
    const delta = targetDate.getTime() - Date.now();
    if (delta <= 0) {
        return { label: "Closed", expired: true };
    }

    const minutes = Math.floor(delta / 60000);
    const days = Math.floor(minutes / 1440);
    const hours = Math.floor((minutes % 1440) / 60);
    const mins = minutes % 60;

    if (days > 0) {
        return { label: `Ends in ${days}d ${hours}h`, expired: false };
    }
    if (hours > 0) {
        return { label: `Ends in ${hours}h ${mins}m`, expired: false };
    }
    return { label: `Ends in ${mins}m`, expired: false };
}

function updateCountdowns() {
    document.querySelectorAll("[data-countdown]").forEach((element) => {
        const raw = element.getAttribute("data-countdown");
        const targetDate = new Date(raw);
        if (Number.isNaN(targetDate.getTime())) {
            return;
        }
        const countdown = formatCountdown(targetDate);
        element.textContent = countdown.label;
        element.dataset.expired = countdown.expired ? "true" : "false";
    });
}

function setupNavigation() {
    const toggle = document.querySelector("[data-nav-toggle]");
    const nav = document.querySelector("[data-nav]");
    const headerSide = document.querySelector(".header-side");
    if (!toggle || !nav || !headerSide) {
        return;
    }

    toggle.addEventListener("click", () => {
        const isOpen = nav.classList.toggle("is-open");
        headerSide.classList.toggle("is-open", isOpen);
        toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
}

function setupRevealAnimation() {
    const items = document.querySelectorAll(".reveal-on-scroll");
    if (!("IntersectionObserver" in window)) {
        items.forEach((item) => item.classList.add("is-visible"));
        return;
    }

    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.12 }
    );

    items.forEach((item) => observer.observe(item));
}

document.addEventListener("DOMContentLoaded", () => {
    setupNavigation();
    setupRevealAnimation();
    updateCountdowns();
    window.setInterval(updateCountdowns, 60000);
});
