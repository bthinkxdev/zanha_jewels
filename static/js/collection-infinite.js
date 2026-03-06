/**
 * Collection page: infinite scroll via IntersectionObserver.
 * Preserves backend pagination; appends only new product cards.
 * No full re-render, loading spinner, duplicate/error handling.
 */
(function () {
    "use strict";

    var container = document.getElementById("product-container");
    var sentinel = document.getElementById("scroll-sentinel");
    var loadingEl = document.getElementById("collection-loading");
    if (!container || !sentinel) return;

    var loading = false;
    var observer = null;

    function getNextPage() {
        var next = container.getAttribute("data-next-page");
        if (next === "" || next === null) return null;
        var n = parseInt(next, 10);
        return isNaN(n) ? null : n;
    }

    function getHasNext() {
        return container.getAttribute("data-has-next") === "true";
    }

    function setNextPage(nextPage, hasNext) {
        container.setAttribute("data-next-page", hasNext && nextPage ? String(nextPage) : "");
        container.setAttribute("data-has-next", hasNext ? "true" : "false");
    }

    function buildQueryString(overrides) {
        var params = new URLSearchParams(window.location.search);
        if (overrides) {
            Object.keys(overrides).forEach(function (key) {
                if (overrides[key] === "" || overrides[key] == null) {
                    params.delete(key);
                } else {
                    params.set(key, String(overrides[key]));
                }
            });
        }
        var qs = params.toString();
        return qs ? "?" + qs : "";
    }

    function showSpinner() {
        if (loadingEl) loadingEl.style.display = "flex";
    }

    function hideSpinner() {
        if (loadingEl) loadingEl.style.display = "none";
    }

    function appendCards(html) {
        var parser = new DOMParser();
        var doc = parser.parseFromString(html, "text/html");
        var fragment = doc.querySelector(".js-collection-fragment");
        if (!fragment) return { nextPage: null, hasNext: false };

        var nextPage = fragment.getAttribute("data-next-page");
        var hasNext = fragment.getAttribute("data-has-next") === "true";
        var nextNum = (nextPage && !isNaN(parseInt(nextPage, 10))) ? parseInt(nextPage, 10) : null;

        while (fragment.firstChild) {
            container.appendChild(fragment.firstChild);
        }
        return { nextPage: nextNum, hasNext: hasNext };
    }

    function loadMore() {
        var nextPage = getNextPage();
        if (nextPage == null || !getHasNext()) return;
        if (loading) return;

        loading = true;
        showSpinner();

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
                    setNextPage(null, false);
                    return;
                }
                var result = appendCards(html);
                setNextPage(result.nextPage, result.hasNext);
                if (!result.hasNext && observer && sentinel) {
                    observer.disconnect();
                    observer = null;
                    sentinel.style.display = "none";
                }
            })
            .catch(function () {
                setNextPage(nextPage, true);
                sentinel.style.display = "none";
            })
            .then(function () {
                loading = false;
                hideSpinner();
            });
    }

    observer = new IntersectionObserver(
        function (entries) {
            var entry = entries[0];
            if (!entry || !entry.isIntersecting) return;
            if (!getHasNext() || getNextPage() == null) return;
            loadMore();
        },
        {
            root: null,
            rootMargin: "200px 0px",
            threshold: 0
        }
    );

    observer.observe(sentinel);

    if (!getHasNext() || getNextPage() == null) {
        sentinel.style.display = "none";
    }
})();
