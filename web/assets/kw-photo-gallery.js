import PhotoSwipeLightbox from "./photoswipe-lightbox.esm.min.js?v=1.0";

/* ================================================================
   Configuration
   ================================================================ */

const lightbox = new PhotoSwipeLightbox({
  gallery: "#gallery",
  children: "a",
  pswpModule: () => import("./photoswipe.esm.min.js?v=1.0"),
  imageClickAction: "zoom",
  tapAction: "toggle-controls",
  bgOpacity: 0.95,
  padding: { top: 40, bottom: 40, left: 20, right: 20 },
  zoom: true,
  maxZoomLevel: 3,
  wheelToZoom: true,
});

/* ================================================================
   Helpers
   ================================================================ */

const fullscreenIconEnter =
  '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>';

const fullscreenIconExit =
  '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/></svg>';

const rotateLeftIcon =
  '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4v6h6"/><path d="M3.5 16A9 9 0 1 0 2 11"/></svg>';

const rotateRightIcon =
  '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6"/><path d="M20.5 16A9 9 0 1 1 22 11"/></svg>';

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen();
  }
}

function rotateSlide(pswp, degrees) {
  const slide = pswp.currSlide;
  if (!slide) return;

  const currentRotation = slide.data._rotation || 0;
  const newRotation = currentRotation + degrees;
  slide.data._rotation = newRotation;

  const img = slide.content.element;
  if (img) {
    img.style.transform = `rotate(${newRotation}deg)`;
    img.style.transition = "transform 0.3s ease";
  }
}

function resetRotation(pswp) {
  const slide = pswp.currSlide;
  if (slide?.data) {
    slide.data._rotation = 0;
  }
}

function updateHDButton(el, slide) {
  el.innerHTML = slide.data._isHD ? "WEB" : "HD";
  el.style.fontWeight = slide.data._isHD ? "bold" : "normal";
}

/* ================================================================
   UI Registration
   ================================================================ */

lightbox.on("uiRegister", function () {
  // --- Fullscreen ---
  lightbox.pswp.ui.registerElement({
    name: "fullscreen",
    order: 3,
    isButton: true,
    ariaLabel: "Fullscreen",
    title: "Toggle fullscreen",
    html: fullscreenIconEnter,

    onInit: (el, pswp) => {
      document.addEventListener("fullscreenchange", () => {
        el.innerHTML = document.fullscreenElement
          ? fullscreenIconExit
          : fullscreenIconEnter;
      });

      pswp.on("close", () => {
        if (document.fullscreenElement) {
          document.exitFullscreen();
        }
      });
    },

    onClick: toggleFullscreen,
  });

  // --- Rotate Left ---
  lightbox.pswp.ui.registerElement({
    name: "rotate-left",
    order: 12,
    isButton: true,
    ariaLabel: "Rotate left",
    title: "Rotate left",
    html: rotateLeftIcon,

    onInit: (el, pswp) => {
      pswp.on("change", () => resetRotation(pswp));
    },

    onClick: () => rotateSlide(lightbox.pswp, -90),
  });

  // --- Rotate Right ---
  lightbox.pswp.ui.registerElement({
    name: "rotate-right",
    order: 11,
    isButton: true,
    ariaLabel: "Rotate right",
    title: "Rotate right",
    html: rotateRightIcon,

    onInit: (el, pswp) => {
      pswp.on("change", () => resetRotation(pswp));
    },

    onClick: () => rotateSlide(lightbox.pswp, 90),
  });

  // --- Download ---
  lightbox.pswp.ui.registerElement({
    name: "download-button",
    order: 8,
    isButton: true,
    tagName: "a",

    html: {
      isCustomSVG: true,
      inner:
        '<path d="M20.5 14.3 17.1 18V10h-2.2v7.9l-3.4-3.6L10 16l6 6.1 6-6.1ZM23 23H9v2h14Z" id="pswp__icn-download"/>',
      outlineID: "pswp__icn-download",
    },

    onInit: (el, pswp) => {
      el.setAttribute("download", "");
      el.setAttribute("target", "_blank");
      el.setAttribute("rel", "noopener");
      el.title = "Download original";

      pswp.on("change", () => {
        const slide = pswp.currSlide;
        if (slide?.data?.element) {
          el.href = slide.data.element.dataset.raw;
          el.download = slide.data.element.dataset.download || "photo.jpg";
        }
      });
    },
  });

  // --- HD / WEB toggle ---
  lightbox.pswp.ui.registerElement({
    name: "toggle-hd",
    order: 7,
    isButton: true,
    ariaLabel: "Toggle quality",
    title: "Switch HD / WEB",
    html: "HD",

    onInit: (el, pswp) => {
      pswp.on("change", () => {
        el.innerHTML = "HD";
        el.style.fontWeight = "normal";
      });
    },

    onClick: (event, el) => {
      const pswp = lightbox.pswp;
      const slide = pswp.currSlide;
      const element = slide.data.element;
      const rawUrl = element?.dataset?.raw;
      const fullUrl = element?.href;

      if (!rawUrl || !fullUrl) return;

      const isHD = slide.data._isHD;
      const newSrc = isHD ? fullUrl : rawUrl;

      // Показать встроенный прелоадер
      const preloader = document.querySelector(
        ".pswp__top-bar .pswp__preloader",
      );
      preloader?.classList.add("pswp__preloader--active");

      const hidePreloader = () => {
        preloader?.classList.remove("pswp__preloader--active");
      };

      const img = new Image();
      img.onload = () => {
        const currentImg = slide.content.element;
        if (currentImg) {
          currentImg.style.transition = "opacity 0.3s ease";
          currentImg.style.opacity = "0";

          setTimeout(() => {
            currentImg.src = newSrc;
            currentImg.onload = () => {
              currentImg.style.opacity = "1";
              slide.data._isHD = !isHD;
              slide.data.src = newSrc;
              updateHDButton(el, slide);

              hidePreloader();
            };
          }, 300);
        } else {
          hidePreloader();
        }
      };

      img.onerror = () => {
        console.error("Failed to load HD image");
        hidePreloader();
      };

      img.src = newSrc;
    },
  });
});

/* ================================================================
   Init
   ================================================================ */

lightbox.init();
