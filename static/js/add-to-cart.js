/**
 * Add to cart via AJAX — no redirect. Updates cart count and shows toast.
 */
(function() {
    function getCSRF() {
        var input = document.querySelector("[name=csrfmiddlewaretoken]");
        if (input && input.value) return input.value;
        var m = document.cookie.match(/\bcsrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1].trim()) : "";
    }

    function showToast(message, isError) {
        var container = document.getElementById("add-to-cart-toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "add-to-cart-toast-container";
            container.setAttribute("aria-live", "polite");
            container.style.cssText = "position:fixed;top:1rem;left:50%;transform:translateX(-50%);z-index:9999;display:flex;flex-direction:column;gap:0.5rem;pointer-events:none;";
            document.body.appendChild(container);
        }
        var toast = document.createElement("div");
        toast.style.cssText = "padding:0.75rem 1.25rem;border-radius:8px;font-size:0.9rem;font-weight:500;box-shadow:0 4px 12px rgba(0,0,0,0.15);white-space:nowrap;max-width:90vw;"
            + (isError ? "background:#dc3545;color:#fff;" : "background:#000;color:#fff;");
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(function() {
            toast.style.opacity = "0";
            toast.style.transition = "opacity 0.25s ease";
            setTimeout(function() {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 250);
        }, 2500);
    }

    function updateCartCount(count) {
        var n = typeof count === "number" ? count : 0;
        document.querySelectorAll(".js-cart-count").forEach(function(el) {
            el.textContent = n;
            el.style.display = n > 0 ? "" : "none";
        });
    }

    function triggerCartGleam() {
        var cartItem = document.querySelector(".bottom-bar .js-bottom-bar-cart");
        if (!cartItem) return;
        cartItem.classList.remove("cart-gleam");
        cartItem.offsetHeight;
        cartItem.classList.add("cart-gleam");
        setTimeout(function() {
            cartItem.classList.remove("cart-gleam");
        }, 550);
    }

    function replaceWithViewCart(btn, cartUrl) {
        var viewCart = document.createElement("a");
        viewCart.href = cartUrl;
        viewCart.className = (btn.className || "").replace(/\s*js-pdp-add-cart\s*/, " ").trim() + " btn-view-cart";
        viewCart.innerHTML = '<i class="fas fa-shopping-cart me-2"></i> View Cart';
        viewCart.setAttribute("aria-label", "View cart");
        viewCart.addEventListener("click", function(e) {
            if (window.cartDrawer && typeof window.cartDrawer.open === "function") {
                e.preventDefault();
                window.cartDrawer.open();
            }
        });
        if (btn.parentNode) btn.parentNode.replaceChild(viewCart, btn);
    }

    document.addEventListener("DOMContentLoaded", function() {
        document.body.addEventListener("submit", function(e) {
            var form = e.target;
            if (!form || !form.classList.contains("product-add-form")) return;
            e.preventDefault();

            var url = form.getAttribute("action");
            if (!url) return;
            var body = new FormData(form);
            var btn = form.querySelector('button[type="submit"]');
            var origHtml = btn ? btn.innerHTML : "";
            if (btn) {
                btn.disabled = true;
                btn.classList.add("btn-adding");
                btn.innerHTML = '<span class="btn-adding-text"><i class="fas fa-spinner fa-spin me-2"></i> Adding...</span>';
            }

            var headers = { "X-Requested-With": "XMLHttpRequest" };
            var csrf = getCSRF();
            if (csrf) headers["X-CSRFToken"] = csrf;

            fetch(url, {
                method: "POST",
                headers: headers,
                body: body,
                credentials: "same-origin"
            })
                .then(function(r) { return r.json().then(function(data) { return { ok: r.ok, data: data }; }); })
                .then(function(result) {
                    if (result.ok && result.data.success) {
                        if (typeof result.data.cart_count === "number") {
                            updateCartCount(result.data.cart_count);
                            triggerCartGleam();
                        }

                        var productId = body.get('product_id');
                        var variantId = body.get('variant_id');
                        form.setAttribute('data-cart-added', '1'); // mark to skip in listener
                        document.dispatchEvent(new CustomEvent('cart:updated', {
                            detail: Object.assign({}, result.data, {
                                added_product_id: productId,
                                added_variant_id: variantId
                            })
                        }));

                        if (btn) {
                            btn.classList.remove("btn-adding");
                            btn.classList.add("btn-added");
                            btn.innerHTML = '<span class="btn-added-icon"><i class="fas fa-check"></i></span>';
                            var cartUrl = form.getAttribute("data-cart-url") || (document.body && document.body.getAttribute("data-cart-url")) || "/cart/";
                            setTimeout(function() {
                                btn.classList.remove("btn-added");
                                replaceWithViewCart(btn, cartUrl);
                            }, 800);
                        }
                    } else {
                        if (btn) {
                            btn.classList.remove("btn-adding");
                            btn.disabled = false;
                            btn.innerHTML = origHtml;
                        }
                        showToast(result.data.error || "Could not add to cart", true);
                    }
                })
                .catch(function() {
                    if (btn) {
                        btn.classList.remove("btn-adding");
                        btn.disabled = false;
                        btn.innerHTML = origHtml;
                    }
                    showToast("Network error. Try again.", true);
                });
        });

        // ── Sync all other matching cards across sections ────────────
        document.addEventListener('cart:updated', function(e) {
            var detail = (e && e.detail) || {};
            var variantId = detail.added_variant_id ? String(detail.added_variant_id) : null;
            var productId = detail.added_product_id ? String(detail.added_product_id) : null;
            if (!variantId && !productId) return;

            var cartUrl = (document.body && document.body.getAttribute('data-cart-url')) || '/cart/';

            document.querySelectorAll('form.product-add-form').forEach(function(form) {
                // Skip the form that was just submitted (already handled above)
                if (form.getAttribute('data-cart-added') === '1') return;

                var fVariant = (form.querySelector('[name="variant_id"]') || {}).value || null;
                var fProduct = (form.querySelector('[name="product_id"]') || {}).value || null;

                var isMatch = (productId && fProduct && fProduct === productId);

                if (!isMatch) return;

                var btn = form.querySelector('button[type="submit"]');
                if (!btn) return;

                replaceWithViewCart(btn, cartUrl);
            });
        });

    });
})();
