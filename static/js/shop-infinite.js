/**
 * Shop page infinite scroll (IntersectionObserver).
 * Reuses existing backend AJAX partial: templates/partials/product_cards_gadget.html
 * Appends into #shopProductGrid without changing layout/classes/IDs.
 */
(function () {
    "use strict";

    var grid = document.getElementById("shopProductGrid");
    var paginationNav = document.querySelector('nav[aria-label="Shop pagination"]');
    if (!grid || !paginationNav) return;

    var loading = false;
    var observer = null;

    function getHasNext() {
        return grid.getAttribute("data-has-next") === "true";
    }

    function getNextPage() {
        var next = grid.getAttribute("data-next-page");
        if (next === "" || next == null) return null;
        var n = parseInt(next, 10);
        return isNaN(n) ? null : n;
    }

    function setNext(nextPage, hasNext) {
        grid.setAttribute("data-next-page", hasNext && nextPage ? String(nextPage) : "");
        grid.setAttribute("data-has-next", hasNext ? "true" : "false");
    }

    function buildQueryString(overrides) {
        var params = new URLSearchParams(window.location.search);
        if (overrides) {
            Object.keys(overrides).forEach(function (key) {
                if (overrides[key] === "" || overrides[key] == null) params.delete(key);
                else params.set(key, String(overrides[key]));
            });
        }
        var qs = params.toString();
        return qs ? "?" + qs : "";
    }

    function appendFromHtml(html) {
        var parser = new DOMParser();
        var doc = parser.parseFromString(html, "text/html");
        var fragment = doc.querySelector(".js-shop-fragment");
        if (!fragment) return { hasNext: false, nextPage: null, appended: 0 };

        var nextAttr = fragment.getAttribute("data-next-page");
        var hasNext = fragment.getAttribute("data-has-next") === "true";
        var nextNum = nextAttr && !isNaN(parseInt(nextAttr, 10)) ? parseInt(nextAttr, 10) : null;

        var appended = 0;
        while (fragment.firstChild) {
            grid.appendChild(fragment.firstChild);
            appended += 1;
        }
        return { hasNext: hasNext, nextPage: nextNum, appended: appended };
    }

    function loadMore() {
        if (loading) return;
        var nextPage = getNextPage();
        if (nextPage == null || !getHasNext()) return;

        loading = true;
        var url = window.location.pathname + buildQueryString({ page: nextPage });

        fetch(url, {
            method: "GET",
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
            .then(function (response) {
                if (!response.ok) throw new Error("Network response was not ok");
                return response.text();
            })
            .then(function (html) {
                if (!html || html.trim() === "") {
                    setNext(null, false);
                    return;
                }
                var result = appendFromHtml(html);
                setNext(result.nextPage, result.hasNext);
                if (!result.hasNext && observer) {
                    observer.disconnect();
                    observer = null;
                }
            })
            .catch(function () {
                // Keep current state; user can still click classic pagination.
                observer && observer.disconnect();
                observer = null;
            })
            .then(function () {
                loading = false;
            });
    }

    observer = new IntersectionObserver(
        function (entries) {
            var entry = entries[0];
            if (!entry || !entry.isIntersecting) return;
            if (!getHasNext() || getNextPage() == null) return;
            loadMore();
        },
        { root: null, rootMargin: "250px 0px", threshold: 0 }
    );

    observer.observe(paginationNav);
})();

