/**
 * Home page AJAX sections: New Arrivals, Top Selling, Recently Viewed.
 * Section-specific card layouts: tall (new-arrivals), compact (top-selling), mini (recently-viewed).
 * Auto-hides Recently Viewed when empty. Scroll shadow logic. Deal countdown timer.
 */
(function () {
    "use strict";

    var WISHLIST_SVG = '<svg class="wishlist-heart" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';

    // Cached wishlist IDs for the current user (variant for clothing, product for jewellery)
    var wishlistVariantIds = [];
    var wishlistProductIds = [];

    function formatPriceNoDecimals(val) {
        if (val == null || val === "") return "0";
        var n = parseFloat(val);
        if (isNaN(n)) return "0";
        return String(Math.round(n));
    }

    function formatPriceInr(val) {
        var s = formatPriceNoDecimals(val);
        if (s.length > 3) {
            var parts = [];
            while (s.length > 0) {
                parts.unshift(s.slice(-3));
                s = s.slice(0, -3);
            }
            s = parts.join(",");
        }
        return "₹ " + s;
    }

    function formatRatingDisplay(p) {
        var avg = p && (p.average_rating != null) ? Number(p.average_rating) : 0;
        var total = p && (p.total_reviews != null) ? parseInt(p.total_reviews, 10) : 0;
        if (isNaN(avg)) avg = 0;
        if (isNaN(total) || total < 0) total = 0;
        var avgStr = avg.toFixed(1);
        var countStr = total >= 1000 ? total + "+" : String(total);
        return '<span class="rating-star">★</span> ' + avgStr + ' <span class="rating-sep">|</span> ' + countStr;
    }

    function buildRefCardContent(p, imgWrap, info) {
        var nameEl = document.createElement("h3");
        nameEl.className = "home-card-name storefront-card-name card-title";
        nameEl.textContent = p.name || "";
        info.appendChild(nameEl);
        var variantLine = (p.category_name || "") + (p.color_name ? " · " + p.color_name : "");
        if (variantLine) {
            var variantEl = document.createElement("p");
            variantEl.className = "home-card-brand storefront-card-variant";
            variantEl.textContent = variantLine;
            info.appendChild(variantEl);
        }
        if (p.description && String(p.description).trim()) {
            var descEl = document.createElement("p");
            descEl.className = "storefront-card-description";
            descEl.textContent = String(p.description).trim().split(/\s+/).slice(0, 12).join(" ");
            info.appendChild(descEl);
        }
        var rating = document.createElement("span");
        rating.className = "storefront-card-rating";
        rating.innerHTML = formatRatingDisplay(p);
        info.appendChild(rating);
        if (p.original_price && parseFloat(p.original_price) > parseFloat(p.price || 0)) {
            var disc = document.createElement("span");
            disc.className = "storefront-card-discount-pct";
            disc.textContent = (p.discount_percent || 0) + "% off";
            info.appendChild(disc);
        }
        var priceWrap = document.createElement("div");
        priceWrap.className = "home-ref-prices storefront-card-prices card-price";
        var curr = document.createElement("span");
        curr.className = "current-price";
        curr.textContent = formatPriceInr(p.price);
        priceWrap.appendChild(curr);
        if (p.original_price && parseFloat(p.original_price) > parseFloat(p.price || 0)) {
            var orig = document.createElement("span");
            orig.className = "original-price";
            orig.textContent = formatPriceInr(p.original_price);
            priceWrap.appendChild(orig);
        }
        info.appendChild(priceWrap);
    }

    function buildCardTall(p) {
        if (!p || typeof p !== "object") return null;
        var card = document.createElement("div");
        card.className = "product-card-tall featured-product-card home-ref-card storefront-card";
        if (p.is_featured && p.is_active !== false) {
            var featBadge = document.createElement("span");
            featBadge.className = "card-badge-featured";
            featBadge.textContent = "Featured";
            card.appendChild(featBadge);
        }
        var imgSrc = (Array.isArray(p.card_images) ? p.card_images[0] : null) || p.image_url || "";
        var link = document.createElement("a");
        link.href = p.url || "#";
        link.className = "featured-product-link";
        var imgWrap = document.createElement("div");
        imgWrap.className = "home-ref-image storefront-card-image card-image product-card-image-slider" + ((p.card_images && p.card_images.length > 1) ? " js-product-card-slider" : "");
        if (p.card_images && p.card_images.length > 1) imgWrap.setAttribute("data-card-images", JSON.stringify(p.card_images));
        var img = document.createElement("img");
        img.src = imgSrc.trim() || "/static/images/banner.png";
        img.alt = p.name || "";
        img.loading = "lazy";
        img.className = "card-slider-img";
        img.setAttribute("decoding", "async");
        imgWrap.appendChild(img);
        var rating = document.createElement("span");
        rating.className = "home-card-rating";
        rating.innerHTML = formatRatingDisplay(p);
        imgWrap.appendChild(rating);
        if (p.discount_percent && p.discount_percent > 0) {
            var badge = document.createElement("span");
            badge.className = "home-card-badge is-discount";
            badge.textContent = "↓" + p.discount_percent + "%";
            imgWrap.appendChild(badge);
        }
        link.appendChild(imgWrap);
        var info = document.createElement("div");
        info.className = "home-ref-info storefront-card-info card-info featured-product-info";
        buildRefCardContent(p, imgWrap, info);
        link.appendChild(info);
        card.appendChild(link);
        var wishlist = document.createElement("button");
        wishlist.type = "button";
        wishlist.className = "product-card-wishlist js-wishlist-toggle";
        if (p.is_jewellery) {
            wishlist.setAttribute("data-product-id", p.id);
        } else {
            wishlist.setAttribute("data-variant-id", (p.variant_id != null ? p.variant_id : p.id));
        }
        wishlist.setAttribute("aria-label", "Add to wishlist");
        wishlist.innerHTML = WISHLIST_SVG;
        card.insertBefore(wishlist, card.firstChild);
        return card;
    }

    function buildCardCompact(p) {
        if (!p || typeof p !== "object") return null;
        var card = document.createElement("div");
        card.className = "product-card-compact featured-product-card home-ref-card storefront-card";
        if (p.is_featured && p.is_active !== false) {
            var featBadge = document.createElement("span");
            featBadge.className = "card-badge-featured";
            featBadge.textContent = "Featured";
            card.appendChild(featBadge);
        }
        var imgSrc = (Array.isArray(p.card_images) ? p.card_images[0] : null) || p.image_url || "";
        var wishlist = document.createElement("button");
        wishlist.type = "button";
        wishlist.className = "product-card-wishlist js-wishlist-toggle";
        if (p.is_jewellery) {
            wishlist.setAttribute("data-product-id", p.id);
        } else {
            wishlist.setAttribute("data-variant-id", (p.variant_id != null ? p.variant_id : p.id));
        }
        wishlist.setAttribute("aria-label", "Add to wishlist");
        wishlist.innerHTML = WISHLIST_SVG;
        card.appendChild(wishlist);
        var link = document.createElement("a");
        link.href = p.url || "#";
        link.className = "featured-product-link";
        var imgWrap = document.createElement("div");
        imgWrap.className = "home-ref-image storefront-card-image card-image featured-product-image";
        var img = document.createElement("img");
        img.src = imgSrc.trim() || "/static/images/banner.png";
        img.alt = p.name || "";
        img.loading = "lazy";
        img.setAttribute("decoding", "async");
        imgWrap.appendChild(img);
        var rating = document.createElement("span");
        rating.className = "home-card-rating";
        rating.innerHTML = formatRatingDisplay(p);
        imgWrap.appendChild(rating);
        var badge = document.createElement("span");
        badge.className = "home-card-badge is-bestseller";
        badge.textContent = "BESTSELLER";
        imgWrap.appendChild(badge);
        link.appendChild(imgWrap);
        var info = document.createElement("div");
        info.className = "home-ref-info storefront-card-info card-info";
        buildRefCardContent(p, imgWrap, info);
        link.appendChild(info);
        card.appendChild(link);
        return card;
    }

    function buildCardMini(p) {
        if (!p || typeof p !== "object") return null;
        var card = document.createElement("a");
        card.href = p.url || "#";
        card.className = "product-card-mini featured-product-card home-ref-card";
        var imgSrc = (Array.isArray(p.card_images) ? p.card_images[0] : null) || p.image_url || "";
        var imgWrap = document.createElement("div");
        imgWrap.className = "home-ref-image card-image";
        var img = document.createElement("img");
        img.src = imgSrc.trim() || "/static/images/banner.png";
        img.alt = p.name || "";
        img.loading = "lazy";
        img.setAttribute("decoding", "async");
        imgWrap.appendChild(img);
        if (p.is_featured && p.is_active !== false) {
            var featBadge = document.createElement("span");
            featBadge.className = "card-badge-featured";
            featBadge.textContent = "Featured";
            imgWrap.appendChild(featBadge);
        }
        var rating = document.createElement("span");
        rating.className = "home-card-rating";
        rating.innerHTML = formatRatingDisplay(p);
        imgWrap.appendChild(rating);
        card.appendChild(imgWrap);
        var info = document.createElement("div");
        info.className = "home-ref-info card-info";
        if (p.category_name) {
            var brand = document.createElement("p");
            brand.className = "home-card-brand storefront-card-variant";
            brand.textContent = p.category_name + (p.color_name ? " · " + p.color_name : "");
            info.appendChild(brand);
        }
        var nameEl = document.createElement("h3");
        nameEl.className = "home-card-name storefront-card-name card-title";
        nameEl.textContent = p.name || "";
        info.appendChild(nameEl);
        var priceWrap = document.createElement("div");
        priceWrap.className = "home-ref-prices storefront-card-prices card-price";
        var curr = document.createElement("span");
        curr.className = "current-price";
        curr.textContent = formatPriceInr(p.price);
        priceWrap.appendChild(curr);
        info.appendChild(priceWrap);
        card.appendChild(info);
        return card;
    }

    function getCardBuilder(sectionType) {
        if (sectionType === "new-arrivals") return buildCardTall;
        if (sectionType === "top-selling") return buildCardCompact;
        if (sectionType === "recently-viewed") return buildCardMini;
        return buildCardTall;
    }

    // Apply "in-wishlist" class to wishlist toggle buttons (variant IDs or product IDs for jewellery).
    function applyWishlistState() {
        var variantSet = new Set();
        if (wishlistVariantIds && wishlistVariantIds.length) {
            wishlistVariantIds.forEach(function (id) {
                var num = parseInt(id, 10);
                if (!isNaN(num)) variantSet.add(num);
            });
        }
        var productSet = new Set();
        if (wishlistProductIds && wishlistProductIds.length) {
            wishlistProductIds.forEach(function (id) {
                var num = parseInt(id, 10);
                if (!isNaN(num)) productSet.add(num);
            });
        }
        document.querySelectorAll(".js-wishlist-toggle[data-variant-id]").forEach(function (btn) {
            var vid = parseInt(btn.getAttribute("data-variant-id") || "", 10);
            if (!isNaN(vid) && variantSet.has(vid)) btn.classList.add("in-wishlist");
        });
        document.querySelectorAll(".js-wishlist-toggle[data-product-id]").forEach(function (btn) {
            var pid = parseInt(btn.getAttribute("data-product-id") || "", 10);
            if (!isNaN(pid) && productSet.has(pid)) btn.classList.add("in-wishlist");
        });
    }

    // Fetch wishlist IDs for the logged-in user (if any). Safe for guests (returns empty list).
    function fetchWishlistIds() {
        var url = "/api/wishlist/ids/";
        try {
            fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
                .then(function (response) {
                    if (!response || !response.ok) return null;
                    return response.json();
                })
                .then(function (data) {
                    if (!data) return;
                    wishlistVariantIds = Array.isArray(data.variant_ids) ? data.variant_ids : [];
                    wishlistProductIds = Array.isArray(data.product_ids) ? data.product_ids : [];
                    applyWishlistState();
                })
                .catch(function () {
                    // Fail silently; wishlist hearts will still toggle on click via wishlist.js
                });
        } catch (e) {
            // Swallow any unexpected errors
        }
    }

    function loadSection(section) {
        var apiUrl = section.getAttribute("data-api-url");
        var sectionType = section.getAttribute("data-section-type") || "new-arrivals";
        var container = section.querySelector(".js-home-ajax-products");
        if (!apiUrl || !container) return;

        // New Arrivals: explicitly request up to 30 items
        if (sectionType === "new-arrivals") {
            var urlObj = new URL(apiUrl, window.location.origin);
            urlObj.searchParams.set("limit", "30");
            apiUrl = urlObj.toString();
        }

        fetch(apiUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } })
            .then(function (response) {
                if (!response.ok) return null;
                return response.json();
            })
            .then(function (data) {
                if (!data || !Array.isArray(data.products)) {
                    section.classList.add("is-empty");
                    return;
                }
                var products = data.products || [];
                if (products.length === 0) {
                    section.classList.add("is-empty");
                    return;
                }
                section.classList.remove("is-empty");
                var builder = getCardBuilder(sectionType);

                // Two-row horizontal layouts for some sections; New Arrivals now uses a vertical grid
                container.innerHTML = "";
                if (sectionType === "recently-viewed" || sectionType === "you-may-like") {
                    var rowSize = (sectionType === "you-may-like") ? 8 : 10;
                    var row1 = document.createElement("div");
                    row1.className = "variant-row";
                    products.slice(0, rowSize).forEach(function (p) {
                        var node = builder(p);
                        if (node) row1.appendChild(node);
                    });
                    if (row1.children.length) container.appendChild(row1);
                    var row2Products = products.slice(rowSize, rowSize * 2);
                    if (row2Products.length) {
                        var row2 = document.createElement("div");
                        row2.className = "variant-row";
                        row2Products.forEach(function (p) {
                            var node2 = builder(p);
                            if (node2) row2.appendChild(node2);
                        });
                        if (row2.children.length) container.appendChild(row2);
                    }
                } else {
                    products.forEach(function (p) {
                        var node = builder(p);
                        if (node) container.appendChild(node);
                    });
                }
                // Ensure wishlist heart state is applied to any newly-added cards.
                applyWishlistState();
                if (typeof window.ProductCardSliderInit === "function") {
                    window.ProductCardSliderInit();
                }
            })
            .catch(function () {
                section.classList.add("is-empty");
            });
    }

    function updateScrollShadows(el) {
        if (!el || !el.classList) return;
        var wrapper = el.closest(".js-scroll-shadow");
        if (!wrapper) return;
        var left = el.scrollLeft > 8;
        var right = el.scrollLeft < el.scrollWidth - el.clientWidth - 8;
        wrapper.classList.toggle("has-scroll-left", left);
        wrapper.classList.toggle("has-scroll-right", right);
    }

    function initScrollShadows() {
        var sections = document.querySelectorAll(".js-scroll-shadow");
        sections.forEach(function (wrapper) {
            var scrollEl = wrapper.querySelector(".scroll-section");
            if (!scrollEl) return;
            updateScrollShadows(scrollEl);
            scrollEl.addEventListener("scroll", function () {
                updateScrollShadows(scrollEl);
            });
            window.addEventListener("resize", function () {
                updateScrollShadows(scrollEl);
            });
        });
    }

    function initDealCountdown() {
        var countdown = document.querySelector(".js-deal-countdown");
        if (!countdown) return;
        var hrsEl = countdown.querySelector(".js-countdown-hours");
        var minsEl = countdown.querySelector(".js-countdown-mins");
        var secsEl = countdown.querySelector(".js-countdown-secs");
        if (!hrsEl || !minsEl || !secsEl) return;
        var endOfDay = function () {
            var d = new Date();
            d.setHours(23, 59, 59, 999);
            return d.getTime();
        };
        var pad = function (n) { return (n < 10 ? "0" : "") + n; };
        var tick = function () {
            var now = Date.now();
            var end = endOfDay();
            var diff = Math.max(0, end - now);
            if (diff <= 0) {
                hrsEl.textContent = "00";
                minsEl.textContent = "00";
                secsEl.textContent = "00";
                return;
            }
            var h = Math.floor(diff / 3600000);
            var m = Math.floor((diff % 3600000) / 60000);
            var s = Math.floor((diff % 60000) / 1000);
            hrsEl.textContent = pad(h);
            minsEl.textContent = pad(m);
            secsEl.textContent = pad(s);
        };
        tick();
        setInterval(tick, 1000);
    }

    var DEAL_AUTO_SCROLL_INTERVAL_MS = 4500;
    var DEAL_AUTO_SCROLL_PAUSE_AFTER_USER_MS = 8000;

    function initDealAutoScroll() {
        var scrollEl = document.querySelector(".deal-products-scroll");
        if (!scrollEl) return;
        var inner = scrollEl.querySelector(".deal-products-inner");
        if (!inner) return;
        var cards = inner.querySelectorAll(".featured-product-card");
        if (cards.length <= 1) return;

        var step = 0;
        var userScrollTimeout = null;

        function getScrollStep() {
            var first = cards[0];
            if (!first) return 0;
            var gap = 20;
            var style = window.getComputedStyle(inner);
            if (style.gap) gap = parseFloat(style.gap) || 20;
            return first.offsetWidth + gap;
        }

        function scrollToNext() {
            var scrollStep = getScrollStep();
            var maxScroll = scrollEl.scrollWidth - scrollEl.clientWidth;
            if (maxScroll <= 0) return;
            step += 1;
            var target = step * scrollStep;
            if (target >= maxScroll) {
                step = 0;
                target = 0;
            }
            scrollEl.scrollTo({ left: target, behavior: "smooth" });
            var wrapper = scrollEl.closest(".js-scroll-shadow");
            if (wrapper) setTimeout(function () { updateScrollShadows(scrollEl); }, 350);
        }

        var autoScrollTimer = setInterval(scrollToNext, DEAL_AUTO_SCROLL_INTERVAL_MS);

        function pauseAndResume() {
            clearInterval(autoScrollTimer);
            if (userScrollTimeout) clearTimeout(userScrollTimeout);
            userScrollTimeout = setTimeout(function () {
                userScrollTimeout = null;
                var scrollStep = getScrollStep();
                step = scrollStep > 0 ? Math.round(scrollEl.scrollLeft / scrollStep) : 0;
                autoScrollTimer = setInterval(scrollToNext, DEAL_AUTO_SCROLL_INTERVAL_MS);
            }, DEAL_AUTO_SCROLL_PAUSE_AFTER_USER_MS);
        }

        scrollEl.addEventListener("scroll", function () {
            if (userScrollTimeout) return;
            pauseAndResume();
        }, { passive: true });
        scrollEl.addEventListener("touchstart", pauseAndResume, { passive: true });
    }

    function init() {
        document.querySelectorAll(".js-home-ajax-section").forEach(loadSection);
        // Load wishlist product IDs once and apply prefilled heart state where relevant.
        fetchWishlistIds();
        initScrollShadows();
        initDealCountdown();
        initDealAutoScroll();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
