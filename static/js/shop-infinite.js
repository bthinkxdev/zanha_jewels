/**
 * Shop page infinite scroll (shop.html).
 * Reuses the collection-infinite.js approach but targets #shopProductGrid and the
 * existing AJAX partial (partials/product_cards_gadget.html).
 *
 * Constraints:
 * - No HTML structure changes required (uses existing pagination as the trigger region).
 * - Preserves all active filters via window.location.search.
 */
(function () {
    "use strict";

    var grid = document.getElementById("shopProductGrid");
    if (!grid) return;

    // Use the existing pagination nav as our observation target (no extra sentinel needed).
    var paginationNav = document.querySelector('nav[aria-label="Shop pagination"]');
    if (!paginationNav) return;

    var loading = false;
    var observer = null;

    function getNextHrefFromPagination() {
        try {
            var links = paginationNav.querySelectorAll("a.page-link");
            for (var i = 0; i < links.length; i++) {
                var a = links[i];
                if (!a) continue;
                var txt = (a.textContent || "").trim().toLowerCase();
                if (txt === "next") return a.getAttribute("href") || "";
            }
        } catch (e) {}
        return "";
    }

    function parseFragment(html) {
        var parser = new DOMParser();
        var doc = parser.parseFromString(html, "text/html");
        var fragment = doc.querySelector(".js-collection-fragment");
        if (!fragment) return { nodes: [], nextPage: null, hasNext: false };

        var hasNext = fragment.getAttribute("data-has-next") === "true";
        var nextPage = fragment.getAttribute("data-next-page");
        var nextNum = (nextPage && !isNaN(parseInt(nextPage, 10))) ? parseInt(nextPage, 10) : null;

        var nodes = [];
        while (fragment.firstChild) {
            nodes.push(fragment.firstChild);
            fragment.removeChild(fragment.firstChild);
        }
        return { nodes: nodes, nextPage: nextNum, hasNext: hasNext };
    }

    function replacePagination(nextPage, hasNext) {
        if (!paginationNav) return;
        // Keep the existing pagination UI intact for non-JS users; for JS infinite scroll,
        // we only need its "Next" href to be correct. When we hit the end, we can hide it.
        if (!hasNext || nextPage == null) {
            paginationNav.style.display = "none";
            return;
        }
        // Update only the Next link href to reflect the next page while preserving filters.
        try {
            var nextLinks = paginationNav.querySelectorAll("a.page-link");
            for (var i = 0; i < nextLinks.length; i++) {
                var a = nextLinks[i];
                if (!a) continue;
                var txt = (a.textContent || "").trim().toLowerCase();
                if (txt !== "next") continue;
                var url = new URL(window.location.href);
                url.searchParams.set("page", String(nextPage));
                a.setAttribute("href", url.pathname + "?" + url.searchParams.toString());
                break;
            }
        } catch (e) {}
    }

    function loadMore() {
        if (loading) return;

        var nextHref = getNextHrefFromPagination();
        if (!nextHref) {
            // If there's no Next, nothing to do.
            if (observer) observer.disconnect();
            return;
        }

        loading = true;

        // Always request as AJAX so ProductListView returns the partial.
        fetch(nextHref, {
            method: "GET",
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
            .then(function (response) {
                if (!response.ok) throw new Error("Network response was not ok");
                return response.text();
            })
            .then(function (html) {
                if (!html || html.trim() === "") {
                    replacePagination(null, false);
                    if (observer) observer.disconnect();
                    return;
                }

                var result = parseFragment(html);
                if (!result.nodes.length) {
                    // Fallback: if fragment missing, stop infinite scroll but keep pagination visible.
                    if (observer) observer.disconnect();
                    return;
                }

                for (var i = 0; i < result.nodes.length; i++) {
                    grid.appendChild(result.nodes[i]);
                }

                // Update next-page state in the existing pagination (no DOM structure changes).
                replacePagination(result.nextPage, result.hasNext);

                if (!result.hasNext || result.nextPage == null) {
                    if (observer) observer.disconnect();
                }
            })
            .catch(function () {
                // Graceful fallback: on error, keep pagination usable.
                if (observer) observer.disconnect();
            })
            .then(function () {
                loading = false;
            });
    }

    observer = new IntersectionObserver(
        function (entries) {
            var entry = entries[0];
            if (!entry || !entry.isIntersecting) return;
            loadMore();
        },
        {
            root: null,
            rootMargin: "200px 0px",
            threshold: 0
        }
    );

    observer.observe(paginationNav);
})();

