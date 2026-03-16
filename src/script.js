const screens = Array.from(document.querySelectorAll(".mm-screen"));
const navLinks = Array.from(document.querySelectorAll(".mm-nav-link"));
const headerLoginBtn = document.querySelector(".mm-login-btn");
const screenButtons = Array.from(
  document.querySelectorAll("[data-screen]:not(.mm-nav-link)")
);

function showScreen(id) {
  screens.forEach((section) => {
    section.classList.toggle("mm-screen--active", section.id === `screen-${id}`);
  });

  navLinks.forEach((link) => {
    const target = link.getAttribute("data-screen");
    link.classList.toggle("mm-nav-link--active", target === id);
  });
}

navLinks.forEach((link) => {
  link.addEventListener("click", () => {
    const id = link.getAttribute("data-screen");
    if (id) showScreen(id);
  });
});

if (headerLoginBtn) {
  headerLoginBtn.addEventListener("click", () => {
    const id = headerLoginBtn.getAttribute("data-screen");
    if (id) showScreen(id);
  });
}

screenButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const id = btn.getAttribute("data-screen");
    if (id) showScreen(id);
  });
});

const sidebarLinks = Array.from(document.querySelectorAll(".mm-sidebar-link"));

sidebarLinks.forEach((link) => {
  link.addEventListener("click", () => {
    const id = link.getAttribute("data-screen");

    const parentSidebar = link.closest(".mm-dashboard-sidebar");
    if (parentSidebar) {
      parentSidebar
        .querySelectorAll(".mm-sidebar-link")
        .forEach((sibling) =>
          sibling.classList.toggle("mm-sidebar-link--active", sibling === link)
        );
    }

    if (id) showScreen(id);
  });
});

const heroSlides = Array.from(
  document.querySelectorAll(".mm-hero-slide")
);
const prevBtn = document.querySelector("[data-hero-prev]");
const nextBtn = document.querySelector("[data-hero-next]");

let currentHeroIndex = 0;

function updateHeroSlides() {
  heroSlides.forEach((slide, index) => {
    slide.classList.toggle("mm-hero-slide--active", index === currentHeroIndex);
  });
}

function goToNextHero() {
  if (!heroSlides.length) return;
  currentHeroIndex = (currentHeroIndex + 1) % heroSlides.length;
  updateHeroSlides();
}

function goToPrevHero() {
  if (!heroSlides.length) return;
  currentHeroIndex =
    (currentHeroIndex - 1 + heroSlides.length) % heroSlides.length;
  updateHeroSlides();
}

if (nextBtn) nextBtn.addEventListener("click", goToNextHero);
if (prevBtn) prevBtn.addEventListener("click", goToPrevHero);

if (heroSlides.length) {
  updateHeroSlides();
  setInterval(goToNextHero, 6000);
}

showScreen("home");

