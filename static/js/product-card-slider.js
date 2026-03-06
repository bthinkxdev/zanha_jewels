/**
 * Product card image slider: auto-slide on hover (desktop) and touch (mobile).
 * - Slide interval: 1.25s
 * - First image change occurs immediately on hover for visible feedback
 * - On leave/touch end/scroll: stop and reset to first image
 * - Single image: no behaviour
 * - No duplicate intervals; preload next image to avoid flash
 */
(function () {
    var SLIDE_INTERVAL_MS = 1250;
    var FADE_MS = 300;

    function parseImages(el) {
        try {
            var raw = el.getAttribute("data-card-images");
            if (!raw || raw.trim() === "[]") return [];
            var arr = JSON.parse(raw);
            return Array.isArray(arr) ? arr.filter(Boolean) : [];
        } catch (e) { return []; }
    }

    function getImg(el) {
        return el.querySelector(".card-slider-img");
    }

    function preload(url) {
        if (url) { var i = new Image(); i.src = url; }
    }

    function showIndex(el, index) {
        var images = el._si;
        var img = getImg(el);
        if (!images || !img) return;
        index = ((index % images.length) + images.length) % images.length;
        el._idx = index;
        img.style.opacity = "0";
        setTimeout(function () {
            img.src = images[index];
            img.style.opacity = "1";
            preload(images[(index + 1) % images.length]);
        }, FADE_MS);
    }

    function stopSliding(el) {
        if (el._timer) { clearInterval(el._timer); el._timer = null; }
        el._active = false;
    }

    function startSliding(el) {
        if (el._si.length <= 1) return;
        stopSliding(el);
        el._active = true;
        showIndex(el, 1);
        el._timer = setInterval(function () {
            showIndex(el, (el._idx || 0) + 1);
        }, SLIDE_INTERVAL_MS);
    }

    function resetToFirst(el) {
        stopSliding(el);
        var img = getImg(el);
        if (!img || !el._si || !el._si[0]) return;
        img.style.opacity = "0";
        setTimeout(function () {
            img.src = el._si[0];
            img.style.opacity = "1";
        }, FADE_MS);
        el._idx = 0;
    }

    function addArrows(el) {
        if (el.querySelector(".tpc-arrow")) return; // already added

        var prev = document.createElement("button");
        prev.type = "button";
        prev.className = "tpc-arrow tpc-prev";
        prev.setAttribute("aria-label", "Previous");
        prev.innerHTML = "&#8249;";

        var next = document.createElement("button");
        next.type = "button";
        next.className = "tpc-arrow tpc-next";
        next.setAttribute("aria-label", "Next");
        next.innerHTML = "&#8250;";

        el.appendChild(prev);
        el.appendChild(next);

        prev.addEventListener("click", function (e) {
            e.preventDefault(); e.stopPropagation();
            stopSliding(el);
            showIndex(el, (el._idx || 0) - 1);
        });

        next.addEventListener("click", function (e) {
            e.preventDefault(); e.stopPropagation();
            stopSliding(el);
            showIndex(el, (el._idx || 0) + 1);
        });
    }

    function bindSlider(el) {
        if (el._bound) return;
        var images = parseImages(el);
        if (images.length <= 1) return;

        el._si = images;
        el._idx = 0;
        el._bound = true;

        // Set up img transition
        var img = getImg(el);
        if (img) {
            img.style.transition = "opacity " + FADE_MS + "ms ease";
        }

        addArrows(el);

        el.addEventListener("mouseenter", function () { startSliding(el); }, { passive: true });
        el.addEventListener("mouseleave", function () { resetToFirst(el); }, { passive: true });

        // Mobile long-press
        el.addEventListener("touchstart", function () {
            el._touchTimer = setTimeout(function () { startSliding(el); }, 400);
        }, { passive: true });
        el.addEventListener("touchend",   function () {
            clearTimeout(el._touchTimer); resetToFirst(el);
        }, { passive: true });
        el.addEventListener("touchcancel", function () {
            clearTimeout(el._touchTimer); resetToFirst(el);
        }, { passive: true });
    }

    function init() {
        document.querySelectorAll(".js-product-card-slider").forEach(bindSlider);
    }

    window.addEventListener("scroll", function () {
        document.querySelectorAll(".js-product-card-slider").forEach(function (el) {
            if (el._active) resetToFirst(el);
        });
    }, { passive: true });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

    window.ProductCardSliderInit = init;
})();