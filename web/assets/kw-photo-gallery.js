import PhotoSwipeLightbox from "./photoswipe-lightbox.esm.min.js?v=1.0";

const lightbox = new PhotoSwipeLightbox({
  gallery: "#gallery",
  children: "a",
  pswpModule: () => import("./photoswipe.esm.min.js?v=1.0"),
  imageClickAction: "zoom", // Клик = зум
  tapAction: "toggle-controls", // Двойной тап = контролы
  bgOpacity: 0.95,
  padding: { top: 40, bottom: 40, left: 20, right: 20 },

  // Настройки зума
  zoom: true,
  maxZoomLevel: 3,
  wheelToZoom: true, // Зум колесиком
});

// Функция поворота (общая для обеих кнопок)
function rotateSlide(pswp, degrees) {
  const slide = pswp.currSlide;
  if (!slide) return;

  const currentRotation = slide.data._rotation || 0;
  const newRotation = currentRotation + degrees;
  slide.data._rotation = newRotation;

  console.log(slide.content)
  const img = slide.content.element;
  console.log('img', img);
  const container = slide.holderElement;

  if (img) {
    img.style.transform = `rotate(${newRotation}deg)`;
    img.style.transition = "transform 0.3s ease";
  }
}

lightbox.on("uiRegister", function () {
  // Кнопка поворота влево
  lightbox.pswp.ui.registerElement({
    name: "rotate-left",
    order: 10,
    isButton: true,
    ariaLabel: "Повернуть влево",
    title: "Повернуть влево",
    html: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4v6h6"/><path d="M3.5 16A9 9 0 1 0 2 11"/></svg>',
    onInit: (el, pswp) => {
      // Сбрасываем поворот при смене слайда
      pswp.on("change", () => {
        const slide = pswp.currSlide;
        if (slide?.data) {
          slide.data._rotation = 0;
        }
      });
    },
    onClick: () => {
      rotateSlide(lightbox.pswp, -90);
    },
  });

  // Кнопка поворота вправо
  lightbox.pswp.ui.registerElement({
    name: "rotate-right",
    order: 11,
    isButton: true,
    ariaLabel: "Повернуть вправо",
    title: "Повернуть вправо",
    html: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6"/><path d="M20.5 16A9 9 0 1 1 22 11"/></svg>',
    onInit: (el, pswp) => {
      // Сбрасываем поворот при смене слайда
      pswp.on("change", () => {
        const slide = pswp.currSlide;
        if (slide?.data) {
          slide.data._rotation = 0;
        }
      });
    },
    onClick: () => {
      rotateSlide(lightbox.pswp, 90);
    },
  });
  // Кнопка скачивания RAW
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

  // Кнопка переключения HD/WEB
  lightbox.pswp.ui.registerElement({
    name: "toggle-hd",
    order: 7,
    isButton: true,
    ariaLabel: "Переключить качество",
    title: "Переключить качество в HD/WEB",
    html: "HD",

    onInit: (el, pswp) => {
      // Сбрасываем кнопку при смене слайда
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
      const fullUrl = element?.href; // AVIF

      if (!rawUrl || !fullUrl) return;

      const isHD = slide.data._isHD;
      const newSrc = isHD ? fullUrl : rawUrl;

      // Показать индикатор загрузки
      pswp.dispatch("loadingIndicatorDisplay", { isDisplayed: true });

      // Предзагрузка изображения
      const img = new Image();
      img.onload = () => {
        const currentImg = slide.content.element;
        if (currentImg) {
          // Плавная смена
          currentImg.style.transition = "opacity 0.3s ease";
          currentImg.style.opacity = "0";

          setTimeout(() => {
            currentImg.src = newSrc;
            currentImg.onload = () => {
              currentImg.style.opacity = "1";
              slide.data._isHD = !isHD;
              slide.data.src = newSrc;

              // Обновить кнопку
              el.innerHTML = slide.data._isHD ? "WEB" : "HD";
              el.style.fontWeight = slide.data._isHD ? "bold" : "normal";
            };
          }, 300);
        }

        pswp.dispatch("loadingIndicatorDisplay", { isDisplayed: false });
      };

      img.onerror = () => {
        console.error("Failed to load HD image");
        pswp.dispatch("loadingIndicatorDisplay", { isDisplayed: false });
      };

      img.src = newSrc;
    },
  });
});

lightbox.init();
