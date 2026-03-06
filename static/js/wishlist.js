/**
 * Wishlist toggle via AJAX. Redirects guests to login.
 */
(function() {
    function getCSRFToken() {
        var input = document.querySelector("[name=csrfmiddlewaretoken]");
        if (input && input.value) return input.value;
        var match = document.cookie.match(/\bcsrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1].trim()) : "";
    }

    function getConfig() {
        var body = document.body;
        return {
            toggleUrl: body.getAttribute("data-wishlist-toggle-url") || "",
            loginUrl: body.getAttribute("data-login-url") || "/auth/login/",
            isAuthenticated: body.getAttribute("data-user-authenticated") === "true"
        };
    }

    function updateHeaderCount(count) {
        document.querySelectorAll(".js-wishlist-count").forEach(function(badge) {
            if (count > 0) {
                badge.textContent = count;
                badge.style.display = "";
            } else {
                badge.textContent = "";
                badge.style.display = "none";
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function() {
        var config = getConfig();

        document.body.addEventListener("click", function(e) {
            var btn = e.target.closest(".js-wishlist-toggle");
            if (!btn) return;

            e.preventDefault();
            e.stopPropagation();

            var variantId = btn.getAttribute("data-variant-id");
            var productId = btn.getAttribute("data-product-id");
            if (!variantId && !productId) return;

            if (!config.isAuthenticated) {
                var next = encodeURIComponent(window.location.href);
                window.location.href = config.loginUrl + (config.loginUrl.indexOf("?") === -1 ? "?" : "&") + "next=" + next;
                return;
            }

            var toggleUrl = config.toggleUrl;
            if (!toggleUrl) return;

            var csrf = getCSRFToken();
            var headers = {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            };
            if (csrf) headers["X-CSRFToken"] = csrf;

            var body = variantId
                ? { variant_id: parseInt(variantId, 10) }
                : { product_id: parseInt(productId, 10) };
            fetch(toggleUrl, {
                method: "POST",
                headers: headers,
                body: JSON.stringify(body)
            })
                .then(function(res) {
                    if (res.status === 403) {
                        return res.json().then(function(data) {
                            if (data.login_required && data.login_url) {
                                window.location.href = data.login_url;
                                return null;
                            }
                            throw new Error("Forbidden");
                        });
                    }
                    if (!res.ok) throw new Error("Request failed");
                    return res.json();
                })
                .then(function(data) {
                    if (!data) return;
                    if (data.success) {
                        btn.classList.toggle("in-wishlist", data.added);
                        if (typeof data.count === "number") updateHeaderCount(data.count);
                        // If on wishlist page and we removed, remove the row
                        var row = variantId
                            ? document.querySelector(".wishlist-item[data-variant-id=\"" + variantId + "\"]")
                            : document.querySelector(".wishlist-item[data-product-id=\"" + productId + "\"]");
                        if (row && !data.added) row.remove();
                    }
                })
                .catch(function() {
                    // Avoid uncaught errors
                });
        });
    });
})();
