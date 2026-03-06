/**
 * Admin product list: delete confirmation modal
 */
(function() {
    "use strict";
    var modal = document.getElementById("product-delete-modal");
    var form = document.getElementById("product-delete-form");
    var messageEl = document.getElementById("product-delete-message");
    var cancelBtn = document.getElementById("product-delete-cancel");
    var backdrop = document.getElementById("product-delete-backdrop");
    var defaultName = "this product";

    function openDeleteModal(deleteUrl, productName) {
        if (!form || !messageEl) return;
        form.action = deleteUrl || "";
        var name = productName || defaultName;
        messageEl.textContent = "Are you sure you want to delete \"" + name + "\"? The product will be permanently deleted along with all variants and images if it has no related orders.";
        if (modal) modal.style.display = "block";
    }

    function closeDeleteModal() {
        if (modal) modal.style.display = "none";
    }

    document.querySelectorAll(".delete-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
            var url = btn.getAttribute("data-delete-url");
            var name = btn.getAttribute("data-product-name") || defaultName;
            if (url) openDeleteModal(url, name);
        });
    });

    if (cancelBtn) cancelBtn.addEventListener("click", closeDeleteModal);
    if (backdrop) backdrop.addEventListener("click", closeDeleteModal);
})();
