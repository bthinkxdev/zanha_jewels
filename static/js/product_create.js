/**
 * Admin product create: Step 1 only. Saves basic details then redirects to edit page.
 * Uses event delegation; no duplicate logic.
 */
(function () {
    "use strict";

    var wrapper = document.getElementById("create-wrapper");
    if (!wrapper) return;

    var urlCreateBasic = wrapper.dataset.urlCreateBasic || "";
    var urlEditTpl = wrapper.dataset.urlEdit || "";
    var csrf =
        (document.querySelector("[name=csrfmiddlewaretoken]") &&
            document.querySelector("[name=csrfmiddlewaretoken]").value) ||
        "";

    function toast(message, type) {
        type = type || "success";
        var container = document.getElementById("toast-container");
        if (!container) return;
        var el = document.createElement("div");
        el.className = "toast " + type;
        el.setAttribute("role", "alert");
        el.textContent = message || "Done.";
        container.appendChild(el);
        setTimeout(function () {
            el.style.opacity = "0";
            el.style.transition = "opacity 0.2s";
            setTimeout(function () {
                if (el.parentNode) el.parentNode.removeChild(el);
            }, 200);
        }, 3500);
    }

    var loaderCount = 0;
    function showLoader() {
        loaderCount++;
        var el = document.getElementById("action-loader-create");
        if (el) {
            el.classList.add("is-active");
            el.setAttribute("aria-hidden", "false");
        }
    }
    function hideLoader() {
        loaderCount = Math.max(0, loaderCount - 1);
        if (loaderCount === 0) {
            var el = document.getElementById("action-loader-create");
            if (el) {
                el.classList.remove("is-active");
                el.setAttribute("aria-hidden", "true");
            }
        }
    }

    // Toggle sync: delegate on wrapper
    wrapper.addEventListener("change", function (e) {
        if (!e.target || !e.target.classList.contains("toggle-input")) return;
        var wrap = e.target.closest(".toggle-wrap");
        if (!wrap) return;
        var status = wrap.querySelector(".toggle-status");
        if (status)
            status.textContent = e.target.checked
                ? (status.getAttribute("data-on") || "On")
                : (status.getAttribute("data-off") || "Off");
        wrap.classList.toggle("checked", e.target.checked);
        if (e.target.id === "basic-is_gst_applicable") {
            var gstWrap = document.getElementById("gst-fields-wrap");
            if (gstWrap) gstWrap.style.display = e.target.checked ? "" : "none";
        }
    });

    var createBtn = document.getElementById("btn-create-basic");
    if (!createBtn) return;

    createBtn.addEventListener("click", function () {
        var catSel = wrapper.querySelector('select[name="category"]');
        var isGst = document.getElementById("basic-is_gst_applicable") && document.getElementById("basic-is_gst_applicable").checked;
        var gstPctEl = document.getElementById("basic-gst_percentage");
        var gstPctVal = (gstPctEl && gstPctEl.value.trim() !== "") ? gstPctEl.value.trim() : null;
        if (isGst && gstPctVal != null) {
            var num = parseFloat(gstPctVal);
            if (isNaN(num) || num < 0 || num > 28) gstPctVal = null;
        }
        if (!isGst) gstPctVal = null;
        var hsnEl = document.getElementById("basic-hsn_code");
        var hsnVal = (hsnEl && hsnEl.value.trim() !== "") ? hsnEl.value.trim() : null;
        var featuredEl = document.getElementById("basic-is_featured");
        var bestsellerEl = document.getElementById("basic-is_bestseller");
        var dealEl = document.getElementById("basic-is_deal_of_day");
        var activeEl = document.getElementById("basic-is_active");
        var basePriceEl = document.getElementById("basic-base_price");
        var baseStockEl = document.getElementById("basic-base_stock");

        var payload = {
            name: (document.getElementById("basic-name").value || "").trim(),
            slug: (document.getElementById("basic-slug").value || "").trim() || null,
            description: (document.getElementById("basic-description").value || "").trim(),
            brand: (document.getElementById("basic-brand").value || "").trim() || "",
            is_featured: featuredEl ? featuredEl.checked : false,
            is_bestseller: bestsellerEl ? bestsellerEl.checked : false,
            is_deal_of_day: dealEl ? dealEl.checked : false,
            is_active: activeEl ? activeEl.checked : true,
            category: catSel ? catSel.value : null,
            is_gst_applicable: isGst,
            gst_percentage: gstPctVal,
            hsn_code: hsnVal,
            base_price: basePriceEl && basePriceEl.value.trim() !== "" ? basePriceEl.value.trim() : null,
            base_stock: baseStockEl && baseStockEl.value.trim() !== "" ? parseInt(baseStockEl.value.trim(), 10) || 0 : null,
        };
        if (!payload.name) {
            toast("Name is required.", "error");
            return;
        }
        if (!payload.category) {
            toast("Please select a category.", "error");
            return;
        }
        if (payload.is_gst_applicable && (payload.gst_percentage == null || payload.gst_percentage === "")) {
            toast("GST % must be between 0 and 28 when GST is applicable.", "error");
            return;
        }
        var btn = this;
        var feedback = document.getElementById("basic-feedback");
        btn.disabled = true;
        feedback.textContent = "Creating…";
        feedback.className = "save-feedback";
        showLoader();
        fetch(urlCreateBasic, {
            method: "POST",
            headers: { "X-CSRFToken": csrf, "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            credentials: "same-origin",
        })
            .then(function (r) {
                return r.json();
            })
            .then(function (data) {
                btn.disabled = false;
                if (data.success && data.product_id) {
                    feedback.textContent = "";
                    toast("Product created. Redirecting to edit…");
                    var editUrl = urlEditTpl.replace("/0/", "/" + data.product_id + "/");
                    window.location.href = editUrl;
                } else {
                    var errMsg = "Error creating product.";
                    if (data.errors) {
                        if (data.errors.__all__ && data.errors.__all__[0])
                            errMsg = data.errors.__all__[0];
                        else {
                            for (var key in data.errors) {
                                if (data.errors[key] && data.errors[key][0]) {
                                    errMsg = data.errors[key][0];
                                    break;
                                }
                            }
                        }
                    }
                    feedback.textContent = errMsg;
                    feedback.className = "save-feedback err";
                    toast(errMsg, "error");
                }
            })
            .catch(function () {
                btn.disabled = false;
                feedback.textContent = "Network error.";
                feedback.className = "save-feedback err";
                toast("Network error.", "error");
            })
            .finally(function () {
                hideLoader();
            });
    });
})();
