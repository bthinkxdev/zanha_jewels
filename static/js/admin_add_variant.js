/**
 * Admin product list: Add Variant modal (AJAX).
 * - Load modal content via GET when "Add Variant" is clicked (clothing only).
 * - Duplicate color name check (case-insensitive), disable submit if duplicate.
 * - Max 3 images, at least 1 required; at least 1 size; stock >= 0; no duplicate sizes.
 * - Submit via AJAX (FormData), on success inject new variant or reload.
 */
(function() {
    "use strict";

    var modal = document.getElementById("add-variant-modal");
    var modalBody = document.getElementById("add-variant-modal-body");
    var modalUrlMeta = document.querySelector('meta[name="add-variant-modal-url"]');
    var saveUrlMeta = document.querySelector('meta[name="add-variant-save-url"]');

    function getModalUrl(productId) {
        if (!modalUrlMeta) return null;
        return modalUrlMeta.getAttribute("content").replace(/\/products\/\d+\//, "/products/" + productId + "/");
    }
    function getSaveUrl(productId) {
        if (!saveUrlMeta) return null;
        return saveUrlMeta.getAttribute("content").replace(/\/products\/\d+\//, "/products/" + productId + "/");
    }

    function openModal() {
        if (modal) modal.style.display = "block";
    }
    function closeModal() {
        if (modal) modal.style.display = "none";
        if (modalBody) modalBody.innerHTML = "";
    }

    function getExistingColors(formEl) {
        var raw = formEl ? formEl.getAttribute("data-existing-colors") : "";
        if (!raw) return [];
        return raw.split("||").map(function(s) { return s.trim(); }).filter(Boolean);
    }

    function checkDuplicateColor(enteredName, existingColors) {
        if (!enteredName) return false;
        var lower = enteredName.trim().toLowerCase();
        return existingColors.some(function(c) { return c.toLowerCase() === lower; });
    }

    function bindDuplicateCheck(formEl) {
        var colorInput = formEl.querySelector("#add-variant-color-name");
        var submitBtn = formEl.querySelector("#add-variant-submit");
        var errorEl = formEl.querySelector("#add-variant-color-name-error");
        var existing = getExistingColors(formEl);

        function updateState() {
            var val = (colorInput && colorInput.value) ? colorInput.value.trim() : "";
            var isDup = checkDuplicateColor(val, existing);
            if (errorEl) {
                errorEl.style.display = isDup ? "block" : "none";
                errorEl.textContent = isDup ? "This color already exists for this product." : "";
            }
            if (submitBtn) submitBtn.disabled = isDup;
            if (colorInput) colorInput.classList.toggle("is-invalid", isDup);
        }
        if (colorInput) {
            colorInput.addEventListener("input", updateState);
            colorInput.addEventListener("blur", updateState);
            updateState();
        }
    }

    function bindImagePreviewsAndLimit(formEl) {
        var allowed = 3;
        formEl.querySelectorAll(".add-variant-image-row").forEach(function(row) {
            var input = row.querySelector(".add-variant-file");
            var previewWrap = row.querySelector(".add-variant-image-preview-wrap");
            var previewImg = row.querySelector(".add-variant-image-preview");
            var removeBtn = row.querySelector(".add-variant-image-remove");
            var currentObjectUrl = null;

            function showPreview(src, isObjectUrl) {
                if (currentObjectUrl && window.URL && window.URL.revokeObjectURL) {
                    window.URL.revokeObjectURL(currentObjectUrl);
                    currentObjectUrl = null;
                }
                if (isObjectUrl) currentObjectUrl = src;
                if (previewImg) previewImg.src = src;
                if (previewWrap) previewWrap.style.display = "flex";
                if (input) input.style.display = "none";
            }
            function hidePreview() {
                if (currentObjectUrl && window.URL && window.URL.revokeObjectURL) {
                    window.URL.revokeObjectURL(currentObjectUrl);
                    currentObjectUrl = null;
                }
                if (previewImg) previewImg.src = "";
                if (previewWrap) previewWrap.style.display = "none";
                if (input) {
                    input.value = "";
                    input.style.display = "block";
                }
            }

            if (removeBtn) {
                removeBtn.addEventListener("click", function() {
                    hidePreview();
                    var err = formEl.querySelector("#add-variant-images-error");
                    if (err) err.style.display = "none";
                });
            }

            if (input) {
                input.addEventListener("change", function() {
                    var file = input.files && input.files[0];
                    if (!file) {
                        hidePreview();
                        return;
                    }
                    if (!file.type.match(/^image\//)) {
                        input.value = "";
                        var err = formEl.querySelector("#add-variant-images-error");
                        if (err) {
                            err.style.display = "block";
                            err.textContent = "Please choose an image file (JPG, PNG, GIF, WebP).";
                        }
                        return;
                    }
                    var count = 0;
                    formEl.querySelectorAll(".add-variant-file").forEach(function(inp) {
                        if (inp.files && inp.files.length) count++;
                    });
                    if (count > allowed) {
                        input.value = "";
                        var err = formEl.querySelector("#add-variant-images-error");
                        if (err) {
                            err.style.display = "block";
                            err.textContent = "Maximum " + allowed + " images allowed.";
                        }
                        return;
                    }
                    var err = formEl.querySelector("#add-variant-images-error");
                    if (err) err.style.display = "none";
                    var url = (window.URL && window.URL.createObjectURL) ? window.URL.createObjectURL(file) : null;
                    if (url) {
                        showPreview(url, true);
                    } else {
                        var reader = new FileReader();
                        reader.onload = function(e) { showPreview(e.target.result, false); };
                        reader.readAsDataURL(file);
                    }
                });
            }
        });
    }

    var sizeIndex = 1;
    var standardSizes = ["Free Size", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "6XL", "7XL", "8XL", "9XL", "10XL"];

    function addSizeRow(container) {
        var idx = sizeIndex++;
        var row = document.createElement("div");
        row.className = "add-variant-size-row";
        row.setAttribute("data-index", idx);
        var selectHtml = '<option value="">Select size</option>' +
            standardSizes.map(function(s) { return '<option value="' + s + '">' + s + '</option>'; }).join("");
        row.innerHTML =
            '<select name="size_' + idx + '" class="form-control add-variant-size-select">' + selectHtml + '</select>' +
            '<input type="number" name="stock_' + idx + '" class="form-control add-variant-stock" min="0" placeholder="Stock" value="0">' +
            '<button type="button" class="btn btn-sm btn-outline-danger add-variant-remove-size" title="Remove size" aria-label="Remove size"><i class="fas fa-times"></i></button>';
        container.appendChild(row);
        row.querySelector(".add-variant-remove-size").addEventListener("click", function() {
            row.remove();
        });
    }

    function bindSizes(formEl) {
        var container = formEl.querySelector("#add-variant-sizes-container");
        var addBtn = formEl.querySelector("#add-variant-add-size");
        var submitBtn = formEl.querySelector("#add-variant-submit");
        var sizesErrorEl = formEl.querySelector("#add-variant-sizes-error");

        function updateSizesState() {
            var result = collectSizes(formEl);
            if (result.error) {
                if (sizesErrorEl) {
                    sizesErrorEl.style.display = "block";
                    sizesErrorEl.textContent = result.error;
                }
                if (submitBtn) submitBtn.disabled = true;
            } else {
                if (sizesErrorEl) {
                    sizesErrorEl.style.display = "none";
                    sizesErrorEl.textContent = "";
                }
                // Do not force-enable submit here; let overall validation control it
            }
        }

        if (addBtn && container) {
            addBtn.addEventListener("click", function() {
                addSizeRow(container);
                updateSizesState();
            });
        }
        if (container) {
            container.addEventListener("change", function(e) {
                if (e.target.classList.contains("add-variant-size-select") || e.target.classList.contains("add-variant-stock")) {
                    updateSizesState();
                }
            });
        }
        formEl.querySelectorAll(".add-variant-remove-size").forEach(function(btn) {
            btn.addEventListener("click", function() {
                var row = btn.closest(".add-variant-size-row");
                if (row && container && container.querySelectorAll(".add-variant-size-row").length > 1) {
                    row.remove();
                    updateSizesState();
                }
            });
        });
        updateSizesState();
    }

    function collectSizes(formEl) {
        var rows = formEl.querySelectorAll(".add-variant-size-row");
        var out = [];
        var seen = {};
        for (var i = 0; i < rows.length; i++) {
            var sel = rows[i].querySelector(".add-variant-size-select");
            var stockInput = rows[i].querySelector(".add-variant-stock");
            var size = sel && sel.value ? sel.value.trim() : "";
            if (!size) continue;
            if (seen[size]) return { error: "Duplicate size: " + size };
            seen[size] = true;
            var stock = 0;
            if (stockInput && stockInput.value !== "" && stockInput.value !== null) {
                stock = parseInt(stockInput.value, 10);
                if (isNaN(stock) || stock < 0) return { error: "Stock cannot be negative." };
            }
            out.push({ size: size, stock: stock });
        }
        if (out.length === 0) return { error: "At least one size is required." };
        return { sizes: out };
    }

    function validateForm(formEl) {
        var errors = [];
        var colorName = (formEl.querySelector("#add-variant-color-name") || {}).value;
        if (!(colorName && colorName.trim())) errors.push({ field: "color_name", msg: "Color name is required." });
        if (checkDuplicateColor(colorName, getExistingColors(formEl))) errors.push({ field: "color_name", msg: "This color already exists." });

        var fileCount = 0;
        formEl.querySelectorAll(".add-variant-file").forEach(function(inp) {
            if (inp.files && inp.files.length) fileCount++;
        });
        if (fileCount === 0) errors.push({ field: "images", msg: "At least one image is required." });
        if (fileCount > 3) errors.push({ field: "images", msg: "Maximum 3 images allowed." });

        var sizeResult = collectSizes(formEl);
        var sizesErrorEl = formEl.querySelector("#add-variant-sizes-error");
        if (sizeResult.error) {
            errors.push({ field: "sizes", msg: sizeResult.error });
            if (sizesErrorEl) {
                sizesErrorEl.style.display = "block";
                sizesErrorEl.textContent = sizeResult.error;
            }
        } else if (sizesErrorEl) {
            sizesErrorEl.style.display = "none";
            sizesErrorEl.textContent = "";
        }

        return errors;
    }

    function showFormErrors(formEl, serverErrors) {
        var wrap = formEl.querySelector("#add-variant-form-errors");
        if (!wrap) return;
        var list = [];
        if (serverErrors && typeof serverErrors === "object") {
            Object.keys(serverErrors).forEach(function(k) {
                var arr = serverErrors[k];
                if (Array.isArray(arr)) arr.forEach(function(m) { list.push(m); });
            });
        }
        wrap.innerHTML = list.length ? "<ul class=\"list-unstyled mb-0\">" + list.map(function(m) { return "<li>" + escapeHtml(m) + "</li>"; }).join("") + "</ul>" : "";
        wrap.style.display = list.length ? "block" : "none";
    }
    function escapeHtml(s) {
        var div = document.createElement("div");
        div.textContent = s;
        return div.innerHTML;
    }

    function bindSubmit(formEl, productId) {
        formEl.addEventListener("submit", function(e) {
            e.preventDefault();
            var errs = validateForm(formEl);
            if (errs.length) {
                showFormErrors(formEl, { __all__: errs.map(function(x) { return x.msg; }) });
                return;
            }
            showFormErrors(formEl, null);

            var formData = new FormData(formEl);
            var sizeResult = collectSizes(formEl);
            if (sizeResult.sizes) formData.set("sizes_json", JSON.stringify(sizeResult.sizes));

            var saveUrl = getSaveUrl(productId);
            if (!saveUrl) return;
            var submitBtn = formEl.querySelector("#add-variant-submit");
            if (submitBtn) submitBtn.disabled = true;

            var xhr = new XMLHttpRequest();
            xhr.open("POST", saveUrl);
            xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
            xhr.onload = function() {
                if (submitBtn) submitBtn.disabled = false;
                var json = null;
                try { json = JSON.parse(xhr.responseText); } catch (err) {}
                if (xhr.status >= 200 && xhr.status < 300 && json && json.success) {
                    closeModal();
                    var msg = "Variant added successfully.";
                    if (json.color_name) msg = "Color variant \"" + json.color_name + "\" added successfully.";
                    if (typeof showAdminToast === "function") {
                        showAdminToast(msg, "success");
                    }
                    setTimeout(function() { window.location.reload(); }, 2200);
                } else if (json && json.errors) {
                    showFormErrors(formEl, json.errors);
                    var errMsg = "Could not add variant.";
                    if (json.errors && typeof json.errors === "object") {
                        var first = [];
                        Object.keys(json.errors).forEach(function(k) {
                            if (Array.isArray(json.errors[k])) first = first.concat(json.errors[k]);
                        });
                        if (first.length) errMsg = first[0];
                    }
                    if (typeof showAdminToast === "function") showAdminToast(errMsg, "error");
                } else {
                    var fallback = "Something went wrong. Please try again.";
                    showFormErrors(formEl, { __all__: [fallback] });
                    if (typeof showAdminToast === "function") showAdminToast(fallback, "error");
                }
            };
            xhr.onerror = function() {
                if (submitBtn) submitBtn.disabled = false;
                var fallback = "Network error. Please try again.";
                showFormErrors(formEl, { __all__: [fallback] });
                if (typeof showAdminToast === "function") showAdminToast(fallback, "error");
            };
            xhr.send(formData);
        });
    }

    function bindCancel(formEl) {
        var cancelBtn = formEl.querySelector(".add-variant-cancel");
        if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
    }

    document.querySelectorAll(".add-variant-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
            var productId = btn.getAttribute("data-product-id");
            if (!productId || !modalBody) return;
            var url = getModalUrl(productId);
            if (!url) return;
            modalBody.innerHTML = "<div class=\"add-variant-loading\"><i class=\"fas fa-spinner fa-spin\"></i> Loading...</div>";
            openModal();

            var xhr = new XMLHttpRequest();
            xhr.open("GET", url);
            xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
            xhr.onload = function() {
                if (xhr.status >= 200 && xhr.status < 300) {
                    modalBody.innerHTML = xhr.responseText;
                    var formEl = modalBody.querySelector("#add-variant-form");
                    if (formEl) {
                        sizeIndex = 1;
                        bindDuplicateCheck(formEl);
                        bindImagePreviewsAndLimit(formEl);
                        bindSizes(formEl);
                        bindSubmit(formEl, productId);
                        bindCancel(formEl);
                    }
                } else {
                    modalBody.innerHTML = "<p class=\"text-danger\">Failed to load form.</p>";
                }
            };
            xhr.onerror = function() {
                modalBody.innerHTML = "<p class=\"text-danger\">Network error.</p>";
            };
            xhr.send();
        });
    });

    var backdrop = document.getElementById("add-variant-backdrop");
    if (backdrop) backdrop.addEventListener("click", closeModal);
})();
