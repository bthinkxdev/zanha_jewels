/**
 * Collection page: Sort redirect, Filter bottom sheet
 */
(function () {
    "use strict";

    var sortSelect = document.getElementById("collectionSort");
    var filterBtn = document.getElementById("filterBtn");
    var filterSheet = document.getElementById("filterSheet");
    var filterOverlay = document.getElementById("filterOverlay");

    function getQueryParams() {
        var params = new URLSearchParams(window.location.search);
        return params;
    }

    function buildUrl(overrides) {
        var params = getQueryParams();
        if (overrides) {
            Object.keys(overrides).forEach(function (key) {
                if (overrides[key] === "" || overrides[key] == null) {
                    params.delete(key);
                } else {
                    params.set(key, overrides[key]);
                }
            });
        }
        var qs = params.toString();
        return (window.location.pathname + (qs ? "?" + qs : ""));
    }

    if (sortSelect) {
        sortSelect.addEventListener("change", function () {
            window.location.href = buildUrl({ sort: this.value, page: "" });
        });
    }

    function openFilterSheet() {
        if (filterSheet) filterSheet.classList.add("is-open");
        if (filterOverlay) {
            filterOverlay.classList.add("is-open");
            filterOverlay.setAttribute("aria-hidden", "false");
        }
        if (filterSheet) filterSheet.setAttribute("aria-hidden", "false");
        document.body.style.overflow = "hidden";
    }

    function closeFilterSheet() {
        if (filterSheet) filterSheet.classList.remove("is-open");
        if (filterOverlay) {
            filterOverlay.classList.remove("is-open");
            filterOverlay.setAttribute("aria-hidden", "true");
        }
        if (filterSheet) filterSheet.setAttribute("aria-hidden", "true");
        document.body.style.overflow = "";
    }

    if (filterBtn) {
        filterBtn.addEventListener("click", openFilterSheet);
    }

    var closeButtons = document.querySelectorAll(".js-filter-sheet-close");
    closeButtons.forEach(function (btn) {
        btn.addEventListener("click", closeFilterSheet);
    });

    if (filterOverlay) {
        filterOverlay.addEventListener("click", closeFilterSheet);
    }

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && filterSheet && filterSheet.classList.contains("is-open")) {
            closeFilterSheet();
        }
    });
})();
