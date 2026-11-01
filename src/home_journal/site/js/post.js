document.onkeydown = checkKey;
var activePanorama = null;

function checkKey(e) {
  e = e || window.event;
  var modal = document.getElementById("delete-dialog");
  var modal_open = modal && modal.classList.contains("active");
  const tag = (e.target && e.target.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA") {
    if (e.key === "Escape") {
      close_delete_modal();
    }
    return;
  }

  if (e.key === "Escape") {
    closePanorama();
    close_delete_modal();
    return;
  }
  if (modal_open) {
    return;
  }

  if (e.keyCode == "37") {
    const elem = document.getElementById("previous");
    window.location.href = elem.href;
  } else if (e.keyCode == "39") {
    const elem = document.getElementById("next");
    window.location.href = elem.href;
  }
}

function delete_modal() {
  var modal = document.getElementById("delete-dialog");
  if (modal.classList.contains("active")) {
    close_delete_modal();
  } else {
    open_delete_modal();
  }
}

function open_delete_modal() {
  document.getElementById("delete-dialog").classList.add("active");
  document.getElementById("delete-overlay").classList.add("active");
  setTimeout(() => {
    var passcode = document.getElementById("delete_passcode");
    passcode.focus();
    passcode.select();
  }, 200);
}

function close_delete_modal() {
  var modal = document.getElementById("delete-dialog");
  var overlay = document.getElementById("delete-overlay");
  if (modal) {
    modal.classList.remove("active");
  }
  if (overlay) {
    overlay.classList.remove("active");
  }
  var error = document.getElementById("delete_error");
  if (error) {
    error.textContent = "";
  }
}

function submit_delete(event) {
  event.preventDefault();
  var error = document.getElementById("delete_error");
  error.textContent = "";
  fetch("/delete", {
    method: "POST",
    body: new FormData(event.target),
  }).then((res) => {
    if (res.ok) {
      window.location.href = "/";
      return;
    }
    if (res.status === 403) {
      error.textContent = "Wrong passcode";
      return;
    }
    error.textContent = "Could not delete this post";
  }).catch(() => {
    error.textContent = "Could not delete this post";
  });
  return false;
}

function initializePanorama(container, index, viewerElement) {
  if (!window.pannellum) {
    return null;
  }
  var image = container.querySelector("img");
  if (!image || !image.naturalWidth || !image.naturalHeight) {
    return null;
  }

  var verticalView = Math.min(180, (360 * image.naturalHeight) / image.naturalWidth);
  viewerElement.id = "pannellum-fullscreen-viewer-" + index;
  return pannellum.viewer(viewerElement.id, {
    autoLoad: true,
    haov: 360,
    panorama:
      image.dataset.panoramaSrc || image.dataset.fullSrc || container.dataset.panorama,
    type: "equirectangular",
    vaov: verticalView,
    vOffset: 0,
  });
}

function resizePanorama(viewer) {
  if (!viewer) {
    return;
  }
  requestAnimationFrame(function () {
    viewer.resize();
  });
}

function closePanorama() {
  if (!activePanorama) {
    return;
  }
  var panorama = activePanorama;
  activePanorama = null;
  if (panorama.viewer && panorama.viewer.destroy) {
    panorama.viewer.destroy();
  }
  panorama.overlay.remove();
  document.body.classList.remove("pannellum-open");
  panorama.container.focus({ preventScroll: true });
}

function openPanorama(container, index) {
  if (activePanorama) {
    closePanorama();
  }

  var overlay = document.createElement("div");
  overlay.className = "pannellum-overlay";
  overlay.setAttribute("aria-hidden", "false");
  var viewerElement = document.createElement("div");
  var closeButton = document.createElement("button");
  closeButton.className = "pannellum-close";
  closeButton.type = "button";
  closeButton.setAttribute("aria-label", "Close panorama");
  closeButton.textContent = "X";
  closeButton.addEventListener("click", function (event) {
    event.stopPropagation();
    closePanorama();
  });
  overlay.appendChild(viewerElement);
  overlay.appendChild(closeButton);
  document.body.appendChild(overlay);
  document.body.classList.add("pannellum-open");
  var viewer = initializePanorama(container, index, viewerElement);
  if (!viewer) {
    overlay.remove();
    document.body.classList.remove("pannellum-open");
    return;
  }
  activePanorama = { container: container, overlay: overlay, viewer: viewer };
  resizePanorama(viewer);
}

function initializePanoramas() {
  var containers = Array.from(document.querySelectorAll(".pannellum-panorama"));
  containers.forEach(function (container, index) {
    container.tabIndex = -1;
    container.addEventListener("click", function () {
      openPanorama(container, index);
    });
  });
}

function slowConnection() {
  var connection = navigator.connection || navigator.mozConnection || {};
  if (connection.saveData) {
    return true;
  }
  if (/2g|3g/.test(connection.effectiveType || "")) {
    return true;
  }
  return typeof connection.downlink === "number" && connection.downlink > 0 && connection.downlink < 1.5;
}

function hydrateImage(image) {
  if (!image.dataset.src) {
    return;
  }
  image.src = image.dataset.src;
  delete image.dataset.src;
}

function hydratePoster(video) {
  if (!video.dataset.poster) {
    return;
  }
  video.poster = video.dataset.poster;
  delete video.dataset.poster;
}

function hydrateMedia() {
  var elements = Array.from(
    document.querySelectorAll("img[data-src], video[data-poster]")
  );
  var reveal = function (element) {
    if (element.tagName === "VIDEO") {
      hydratePoster(element);
    } else {
      hydrateImage(element);
    }
  };
  if (!("IntersectionObserver" in window)) {
    elements.forEach(reveal);
    return;
  }
  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) {
          return;
        }
        reveal(entry.target);
        observer.unobserve(entry.target);
      });
    },
    { rootMargin: "0px" }
  );
  elements.forEach(function (element) {
    observer.observe(element);
  });
}

function loadFullImage(image) {
  var fullSrc = image.dataset.fullSrc;
  if (
    !fullSrc ||
    image.closest(".pannellum-panorama") ||
    image.dataset.fullLoading ||
    image.dataset.fullLoaded
  ) {
    return;
  }

  image.dataset.fullLoading = "true";
  var fullImage = new Image();
  fullImage.decoding = "async";
  fullImage.onload = function () {
    image.src = fullSrc;
    image.dataset.fullLoaded = "true";
    delete image.dataset.fullLoading;
    image.classList.add("progressive-image-loaded");
  };
  fullImage.onerror = function () {
    delete image.dataset.fullLoading;
    image.classList.add("progressive-image-failed");
  };
  fullImage.src = fullSrc;
}

function loadProgressiveImages() {
  // Phones read the 640px preview, which already covers their screen; pulling a
  // multi-megabyte original while scrolling is what saturates a weak link. Tapping
  // an image still upgrades it to the full size (see upgradeOnTap), and a slow
  // connection keeps previews even on a wide screen.
  if (slowConnection() || !window.matchMedia("(min-width: 768px)").matches) {
    return;
  }
  var images = Array.from(document.querySelectorAll("img[data-full-src]"));
  if (!("IntersectionObserver" in window)) {
    images.forEach(loadFullImage);
    return;
  }

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) {
          return;
        }
        var image = entry.target;
        observer.unobserve(image);
        if (image.dataset.src) {
          hydrateImage(image);
        }
        if (!image.complete) {
          var load = function () {
            loadFullImage(image);
          };
          image.addEventListener("load", load, { once: true });
          image.addEventListener("error", load, { once: true });
          return;
        }
        loadFullImage(image);
      });
    },
    { rootMargin: "0px" }
  );
  images.forEach(function (image) {
    observer.observe(image);
  });
}

function upgradeOnTap(image) {
  var fullSrc = image.dataset.fullSrc;
  if (!fullSrc || image.dataset.fullLoaded || image.dataset.fullLoading) {
    return;
  }
  image.dataset.fullLoaded = "true";
  image.src = fullSrc;
}

function initializeUpgradeOnTap() {
  var images = Array.from(document.querySelectorAll("img[data-full-src]"));
  images.forEach(function (image) {
    image.addEventListener(
      "pointerdown",
      function () {
        upgradeOnTap(image);
      },
      { passive: true }
    );
  });
}

function startMedia() {
  if (startMedia.done) {
    return;
  }
  startMedia.done = true;
  initializePanoramas();
  hydrateMedia();
  initializeUpgradeOnTap();
  loadProgressiveImages();
  const lightboxImages = Array.from(document.querySelectorAll("img")).filter(
    function (image) {
      return !image.closest(".pannellum-panorama");
    }
  );
  Lightense(lightboxImages);
}

// Start once the document has painted: images must never compete with the post
// itself, and a stalled subresource must not hold them back forever.
window.addEventListener("load", startMedia, false);
window.addEventListener("DOMContentLoaded", function () {
  setTimeout(startMedia, 1000);
}, false);
