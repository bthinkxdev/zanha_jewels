/**
 * Admin product edit: basic details, attributes, attribute values, variants, variant images.
 * Single module, event delegation, no duplicate logic.
 */
(function () {
    "use strict";

    var app = document.getElementById("product-edit-app");
    if (!app) return;

    var productId = app.dataset.productId;
    var csrf =
        (document.querySelector("[name=csrfmiddlewaretoken]") &&
            document.querySelector("[name=csrfmiddlewaretoken]").value) ||
        "";

    function url(idUrl, id) {
        return (idUrl || "").replace("/0/", "/" + id + "/");
    }

    var urls = {
        updateBasic: app.dataset.urlUpdateBasic,
        attributes: app.dataset.urlAttributes,
        attributeAdd: app.dataset.urlAttributeAdd,
        attributesReorder: app.dataset.urlAttributesReorder,
        attributeUpdate: app.dataset.urlAttributeUpdate,
        attributeDelete: app.dataset.urlAttributeDelete,
        attributeValueAdd: app.dataset.urlAttributeValueAdd,
        attributeValuesReorder: app.dataset.urlAttributeValuesReorder,
        attributeValueUpdate: app.dataset.urlAttributeValueUpdate,
        attributeValueDelete: app.dataset.urlAttributeValueDelete,
        variants: app.dataset.urlVariants,
        variantAdd: app.dataset.urlVariantAdd,
        variantUpdate: app.dataset.urlVariantUpdate,
        variantDelete: app.dataset.urlVariantDelete,
        variantUploadImage: app.dataset.urlVariantUploadImage,
        variantImageDelete: app.dataset.urlVariantImageDelete,
        variantImageSetPrimary: app.dataset.urlVariantImageSetPrimary,
        variantImageReorder: app.dataset.urlVariantImageReorder,
    };

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
        var el = document.getElementById("action-loader-edit");
        if (el) {
            el.classList.add("is-active");
            el.setAttribute("aria-hidden", "false");
        }
    }
    function hideLoader() {
        loaderCount = Math.max(0, loaderCount - 1);
        if (loaderCount === 0) {
            var el = document.getElementById("action-loader-edit");
            if (el) {
                el.classList.remove("is-active");
                el.setAttribute("aria-hidden", "true");
            }
        }
    }

    function headers(json) {
        var h = { "X-CSRFToken": csrf };
        if (json) h["Content-Type"] = "application/json";
        return h;
    }

    function escapeHtml(s) {
        if (s == null) return "";
        var div = document.createElement("div");
        div.textContent = s;
        return div.innerHTML;
    }

    // --- Toggle sync (event delegation) ---
    app.addEventListener("change", function (e) {
        if (!e.target || !e.target.classList.contains("toggle-input")) return;
        var wrap = e.target.closest(".toggle-wrap");
        if (!wrap) return;
        var status = wrap.querySelector(".toggle-status");
        if (status)
            status.textContent = e.target.checked
                ? (status.getAttribute("data-on") || "On")
                : (status.getAttribute("data-off") || "Off");
        wrap.classList.toggle("checked", e.target.checked);
        // GST fields visibility
        if (e.target.id === "basic-is_gst_applicable") {
            var gstWrap = document.getElementById("gst-fields-wrap");
            if (gstWrap) gstWrap.style.display = e.target.checked ? "" : "none";
        }
    });

    // --- Section 1: Basic ---
    var basicForm = document.getElementById("basic-edit-form");
    var basicSaveBtn = document.getElementById("basic-save-btn");
    var basicFeedback = document.getElementById("basic-save-feedback");
    var basicInitial = {};

    function getBasicValues() {
        var catSel = basicForm ? basicForm.querySelector('select[name="category"]') : null;
        var isGst = document.getElementById("basic-is_gst_applicable") ? document.getElementById("basic-is_gst_applicable").checked : false;
        var gstPctEl = document.getElementById("basic-gst_percentage");
        var hsnEl = document.getElementById("basic-hsn_code");
        var basePriceEl = document.getElementById("basic-base_price");
        var baseStockEl = document.getElementById("basic-base_stock");
        var gstPct = (gstPctEl && gstPctEl.value.trim() !== "") ? gstPctEl.value : null;
        if (gstPct !== null) {
            var num = parseFloat(gstPct);
            if (isNaN(num) || num < 0 || num > 28) gstPct = null;
        }
        var hsn = (hsnEl && hsnEl.value.trim() !== "") ? hsnEl.value.trim() : null;
        if (!isGst) {
            gstPct = null;
        }
        return {
            name: (document.getElementById("basic-name") && document.getElementById("basic-name").value) || "",
            slug: (document.getElementById("basic-slug") && document.getElementById("basic-slug").value) || "",
            description: (document.getElementById("basic-description") && document.getElementById("basic-description").value) || "",
            brand: (document.getElementById("basic-brand") && document.getElementById("basic-brand").value) || "",
            base_price: basePriceEl && basePriceEl.value.trim() !== "" ? basePriceEl.value.trim() : null,
            base_stock: baseStockEl && baseStockEl.value.trim() !== "" ? parseInt(baseStockEl.value.trim(), 10) || 0 : null,
            is_featured: document.getElementById("basic-is_featured") ? document.getElementById("basic-is_featured").checked : false,
            is_bestseller: document.getElementById("basic-is_bestseller") ? document.getElementById("basic-is_bestseller").checked : false,
            is_deal_of_day: document.getElementById("basic-is_deal_of_day") ? document.getElementById("basic-is_deal_of_day").checked : false,
            is_active: document.getElementById("basic-is_active") ? document.getElementById("basic-is_active").checked : true,
            category: catSel ? catSel.value : null,
            is_gst_applicable: isGst,
            gst_percentage: gstPct,
            hsn_code: hsn,
        };
    }

    function setBasicInitial() {
        basicInitial = getBasicValues();
    }
    function isBasicDirty() {
        var cur = getBasicValues();
        return (
            cur.name !== basicInitial.name ||
            cur.slug !== basicInitial.slug ||
            cur.description !== basicInitial.description ||
            (cur.brand || "") !== (basicInitial.brand || "") ||
            (cur.base_price || "") !== (basicInitial.base_price || "") ||
            (cur.base_stock || 0) !== (basicInitial.base_stock || 0) ||
            cur.is_featured !== basicInitial.is_featured ||
            cur.is_bestseller !== basicInitial.is_bestseller ||
            cur.is_deal_of_day !== basicInitial.is_deal_of_day ||
            cur.is_active !== basicInitial.is_active ||
            cur.category !== basicInitial.category ||
            cur.is_gst_applicable !== basicInitial.is_gst_applicable ||
            (cur.gst_percentage || "") !== (basicInitial.gst_percentage || "") ||
            (cur.hsn_code || "") !== (basicInitial.hsn_code || "")
        );
    }
    function updateBasicSaveButton() {
        if (basicSaveBtn) basicSaveBtn.disabled = !isBasicDirty();
    }
    if (basicForm) {
        setBasicInitial();
        basicForm.addEventListener("input", updateBasicSaveButton);
        basicForm.addEventListener("change", updateBasicSaveButton);
    }

    if (basicSaveBtn) {
        basicSaveBtn.addEventListener("click", function () {
            if (basicSaveBtn.disabled) return;
            var payload = getBasicValues();
            if (!payload.name) {
                toast("Name is required.", "error");
                return;
            }
            if (!payload.category) {
                toast("Category is required.", "error");
                return;
            }
            if (payload.is_gst_applicable) {
                var pct = payload.gst_percentage != null ? parseFloat(payload.gst_percentage) : NaN;
                if (isNaN(pct) || pct < 0 || pct > 28) {
                    toast("GST % must be between 0 and 28 when GST is applicable.", "error");
                    return;
                }
            }
            basicSaveBtn.disabled = true;
            basicFeedback.textContent = "Saving…";
            basicFeedback.className = "save-feedback";
            showLoader();
            fetch(urls.updateBasic, {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify(payload),
                credentials: "same-origin",
            })
                .then(function (r) {
                    return r.json().then(function (data) {
                        return { ok: r.ok, data: data };
                    });
                })
                .then(function (res) {
                    if (res.ok && res.data.success) {
                        setBasicInitial();
                        updateBasicSaveButton();
                        basicFeedback.textContent = "Saved.";
                        basicFeedback.className = "save-feedback";
                        toast("Basic details saved.");
                    } else {
                        var err =
                            (res.data.errors && (res.data.errors.__all__ && res.data.errors.__all__[0])) ||
                            (res.data.errors && res.data.errors.name && res.data.errors.name[0]) ||
                            "Error saving.";
                        basicFeedback.textContent = err;
                        basicFeedback.className = "save-feedback err";
                        toast(err, "error");
                    }
                })
                .catch(function () {
                    basicFeedback.textContent = "Network error.";
                    basicFeedback.className = "save-feedback err";
                    toast("Network error.", "error");
                })
                .finally(function () {
                    basicSaveBtn.disabled = !isBasicDirty();
                    hideLoader();
                });
        });
    }

    // --- Section 2: Attributes ---
    var attributesList = document.getElementById("attributes-list");
    var attributesLoading = document.getElementById("attributes-loading");
    var attrNewName = document.getElementById("attr-new-name");
    var attrAddBtn = document.getElementById("attr-add-btn");
    var attributesData = [];

    function loadAttributes() {
        if (!attributesList) return;
        if (attributesLoading) attributesLoading.style.display = "block";
        attributesList.innerHTML = "";
        fetch(urls.attributes, { method: "GET", credentials: "same-origin" })
            .then(function (r) {
                return r.json();
            })
            .then(function (data) {
                if (attributesLoading) attributesLoading.style.display = "none";
                attributesData = data.attributes || [];
                attributesData.forEach(function (attr) {
                    var row = document.createElement("div");
                    row.className = "attribute-row";
                    row.setAttribute("data-attribute-id", attr.id);
                    var valuesHtml = (attr.values || [])
                        .map(
                            function (v) {
                                return (
                                    '<li class="attribute-value-row" data-value-id="' +
                                    v.id +
                                    '">' +
                                    '<input type="text" class="form-control value-edit-inp" value="' +
                                    escapeHtml(v.value) +
                                    '" data-initial="' +
                                    escapeHtml(v.value) +
                                    '" placeholder="Value">' +
                                    '<button type="button" class="btn btn-sm btn-outline value-save" disabled data-value-id="' +
                                    v.id +
                                    '">Save</button>' +
                                    '<button type="button" class="btn btn-sm btn-danger value-delete" data-value-id="' +
                                    v.id +
                                    '" title="Delete value"><i class="fas fa-trash"></i></button>' +
                                    "</li>"
                                );
                            }
                        )
                        .join("");
                    row.innerHTML =
                        '<div class="attribute-row-main">' +
                        '<input type="text" class="form-control attribute-name" value="' +
                        escapeHtml(attr.name) +
                        '" placeholder="Name" data-initial="' +
                        escapeHtml(attr.name) +
                        '">' +
                        '<input type="number" class="form-control attribute-order" min="0" value="' +
                        (attr.display_order || 0) +
                        '" data-initial="' +
                        (attr.display_order || 0) +
                        '">' +
                        '<button type="button" class="btn btn-sm btn-outline attribute-save" disabled>Save</button>' +
                        '<button type="button" class="btn btn-sm btn-danger attribute-delete" data-attr-id="' +
                        attr.id +
                        '"><i class="fas fa-trash"></i></button>' +
                        "</div>" +
                        '<div class="attribute-values-wrap">' +
                        '<div class="nested-title">Values</div>' +
                        '<ul class="attribute-values-list">' +
                        valuesHtml +
                        "</ul>" +
                        '<div class="attribute-value-add">' +
                        '<input type="text" class="form-control value-input" placeholder="New value">' +
                        '<button type="button" class="btn btn-sm btn-primary value-add-btn" data-attr-id="' +
                        attr.id +
                        '">Add</button>' +
                        "</div>" +
                        "</div>";
                    attributesList.appendChild(row);
                });
            })
            .catch(function () {
                if (attributesLoading) attributesLoading.style.display = "none";
                attributesList.innerHTML = '<p class="save-feedback err">Failed to load attributes.</p>';
            });
    }

    app.addEventListener("click", function (e) {
        var target = e.target.closest ? e.target.closest("button") : null;
        if (!target) return;
        if (target.classList.contains("value-save")) {
            var li = target.closest("li.attribute-value-row");
            if (!li) return;
            var valueId = target.getAttribute("data-value-id");
            var inp = li.querySelector(".value-edit-inp");
            var newVal = inp && inp.value.trim();
            if (!newVal) {
                toast("Value is required.", "error");
                return;
            }
            var initial = inp ? inp.getAttribute("data-initial") : "";
            if (newVal === initial) return;
            showLoader();
            fetch(url(urls.attributeValueUpdate, valueId), {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify({ value: newVal }),
                credentials: "same-origin",
            })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    if (res.success) {
                        toast("Value updated.");
                        if (inp) inp.setAttribute("data-initial", newVal);
                        target.disabled = true;
                    } else {
                        toast((res.errors && res.errors.value && res.errors.value[0]) || "Value already exists.", "error");
                    }
                })
                .catch(function () {
                    toast("Network error.", "error");
                })
                .finally(hideLoader);
            return;
        }
        if (target.id === "attr-add-btn") {
            var name = (attrNewName && attrNewName.value || "").trim();
            if (!name) {
                toast("Enter attribute name.", "error");
                return;
            }
            showLoader();
            fetch(urls.attributeAdd, {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify({ name: name }),
                credentials: "same-origin",
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (res) {
                    if (res.success) {
                        toast("Attribute added.");
                        if (attrNewName) attrNewName.value = "";
                        loadAttributes();
                    } else {
                        toast((res.errors && res.errors.name && res.errors.name[0]) || "Error", "error");
                    }
                })
                .catch(function () {
                    toast("Network error.", "error");
                })
                .finally(hideLoader);
            return;
        }
        if (target.classList.contains("attribute-save")) {
            var row = target.closest(".attribute-row");
            var attrId = row && row.getAttribute("data-attribute-id");
            if (!attrId) return;
            var nameInp = row.querySelector(".attribute-name");
            var orderInp = row.querySelector(".attribute-order");
            var name = (nameInp && nameInp.value || "").trim();
            if (!name) {
                toast("Attribute name is required.", "error");
                return;
            }
            var order = orderInp ? parseInt(orderInp.value, 10) : 0;
            if (isNaN(order)) order = 0;
            showLoader();
            fetch(url(urls.attributeUpdate, attrId), {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify({ name: name, display_order: order }),
                credentials: "same-origin",
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (res) {
                    if (res.success) {
                        toast("Attribute updated.");
                        if (nameInp) nameInp.setAttribute("data-initial", name);
                        if (orderInp) orderInp.setAttribute("data-initial", String(order));
                        target.disabled = true;
                    } else {
                        toast((res.errors && res.errors.name && res.errors.name[0]) || "Error", "error");
                    }
                })
                .catch(function () {
                    toast("Network error.", "error");
                })
                .finally(hideLoader);
            return;
        }
        if (target.classList.contains("attribute-delete")) {
            var attrId = target.getAttribute("data-attr-id");
            if (!attrId || !confirm("Delete this attribute and its values?")) return;
            showLoader();
            fetch(url(urls.attributeDelete, attrId), {
                method: "POST",
                headers: headers(false),
                credentials: "same-origin",
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (res) {
                    if (res.success) {
                        toast("Attribute deleted.");
                        loadAttributes();
                        loadVariants();
                    } else {
                        toast("Could not delete.", "error");
                    }
                })
                .catch(function () {
                    toast("Network error.", "error");
                })
                .finally(hideLoader);
            return;
        }
        if (target.classList.contains("value-add-btn")) {
            var attrId = target.getAttribute("data-attr-id");
            var row = target.closest(".attribute-row");
            var valueInp = row && row.querySelector(".value-input");
            var value = (valueInp && valueInp.value || "").trim();
            if (!value) {
                toast("Enter a value.", "error");
                return;
            }
            showLoader();
            fetch(url(urls.attributeValueAdd, attrId), {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify({ value: value }),
                credentials: "same-origin",
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (res) {
                    if (res.success) {
                        toast("Value added.");
                        if (valueInp) valueInp.value = "";
                        loadAttributes();
                    } else {
                        toast((res.errors && res.errors.value && res.errors.value[0]) || "Error", "error");
                    }
                })
                .catch(function () {
                    toast("Network error.", "error");
                })
                .finally(hideLoader);
            return;
        }
        if (target.classList.contains("value-delete")) {
            var valueId = target.getAttribute("data-value-id");
            if (!valueId || !confirm("Delete this value?")) return;
            showLoader();
            fetch(url(urls.attributeValueDelete, valueId), {
                method: "POST",
                headers: headers(false),
                credentials: "same-origin",
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (res) {
                    if (res.success) {
                        toast("Value deleted.");
                        loadAttributes();
                        loadVariants();
                    } else {
                        toast("Could not delete.", "error");
                    }
                })
                .catch(function () {
                    toast("Network error.", "error");
                })
                .finally(hideLoader);
            return;
        }
    });

    app.addEventListener("input", function (e) {
        var row = e.target.closest(".attribute-row");
        if (row) {
            var nameInp = row.querySelector(".attribute-name");
            var orderInp = row.querySelector(".attribute-order");
            var saveBtn = row.querySelector(".attribute-save");
            if (saveBtn) {
                var initialName = nameInp ? nameInp.getAttribute("data-initial") : "";
                var initialOrder = orderInp ? orderInp.getAttribute("data-initial") : "0";
                var curName = nameInp ? nameInp.value.trim() : "";
                var curOrder = orderInp ? orderInp.value : "0";
                saveBtn.disabled = curName === initialName && curOrder === initialOrder;
            }
        }
        var valueInp = e.target.closest && e.target.classList && e.target.classList.contains("value-edit-inp") ? e.target : null;
        if (valueInp) {
            var li = valueInp.closest("li.attribute-value-row");
            var saveBtnVal = li && li.querySelector(".value-save");
            if (saveBtnVal) {
                var initial = valueInp.getAttribute("data-initial") || "";
                saveBtnVal.disabled = valueInp.value.trim() === initial;
            }
        }
    });

    // --- Section 3: Variants ---
    var variantsList = document.getElementById("variants-list");
    var variantsLoading = document.getElementById("variants-loading");
    var variantAddBtn = document.getElementById("variant-add-btn");
    var addVariantModal = document.getElementById("add-variant-modal");
    var addVariantAttributeValues = document.getElementById("add-variant-attribute-values");
    var addVariantPrice = document.getElementById("add-variant-price");
    var addVariantStock = document.getElementById("add-variant-stock");
    var addVariantSku = document.getElementById("add-variant-sku");
    var addVariantSubmit = document.getElementById("add-variant-submit");
    var addVariantCancel = document.getElementById("add-variant-cancel");
    var addVariantImage = document.getElementById("add-variant-image");

    function loadVariants(expandVariantId) {
        if (!variantsList) return;
        if (variantsLoading) variantsLoading.style.display = "block";
        variantsList.innerHTML = "";
        fetch(urls.variants, { method: "GET", credentials: "same-origin" })
            .then(function (r) {
                return r.json();
            })
            .then(function (data) {
                if (variantsLoading) variantsLoading.style.display = "none";
                var list = data.variants || [];
                if (list.length === 0) {
                    variantsList.innerHTML = '<p class="section-hint">No variants yet. Add attributes and values first, then add a variant.</p>';
                    return;
                }
                list.forEach(function (v) {
                    var combo =
                        (v.attribute_values || [])
                            .map(function (av) {
                                return av.value;
                            })
                            .join(" / ") || "—";
                    var card = document.createElement("div");
                    card.className = "variant-card";
                    card.setAttribute("data-variant-id", v.id);
                    var imgsHtml = (v.images || [])
                        .map(
                            function (img) {
                                return (
                                    '<div class="image-item" data-image-id="' +
                                    img.id +
                                    '">' +
                                    (img.url
                                        ? '<img class="image-thumb" src="' + escapeHtml(img.url) + '" alt="">'
                                        : '<span class="image-thumb" style="width:72px;height:72px;background:#eee;border-radius:6px;display:block;"></span>') +
                                    (img.is_primary ? '<span class="image-primary-badge">Primary</span>' : '') +
                                    '<div class="image-actions">' +
                                    (!img.is_primary
                                        ? '<button type="button" class="btn btn-sm btn-outline image-set-primary" data-image-id="' +
                                          img.id +
                                          '">Primary</button>'
                                        : "") +
                                    '<button type="button" class="btn btn-sm btn-danger image-delete" data-image-id="' +
                                    img.id +
                                    '"><i class="fas fa-times"></i></button>' +
                                    "</div></div>"
                                );
                            }
                        )
                        .join("");
                    card.innerHTML =
                        '<div class="variant-card-header" role="button" tabindex="0" aria-expanded="false">' +
                        '<span class="variant-combo">' +
                        escapeHtml(combo) +
                        "</span>" +
                        '<span class="variant-price">₹' +
                        escapeHtml(v.price) +
                        "</span>" +
                        '<span class="variant-stock">' +
                        (v.stock_quantity || 0) +
                        " in stock</span>" +
                        '<label class="toggle-wrap variant-active-wrap' +
                        (v.is_active ? " checked" : "") +
                        '">' +
                        '<input type="checkbox" class="toggle-input variant-is-active" ' +
                        (v.is_active ? "checked" : "") +
                        ' data-variant-id="' +
                        v.id +
                        '">' +
                        '<span class="toggle-track"><span class="toggle-knob"></span></span>' +
                        '<span class="toggle-status" data-on="On" data-off="Off">' +
                        (v.is_active ? "On" : "Off") +
                        "</span></label>" +
                        '<button type="button" class="btn btn-sm btn-danger variant-delete" data-variant-id="' +
                        v.id +
                        '"><i class="fas fa-trash"></i></button>' +
                        '<span class="variant-chevron"><i class="fas fa-chevron-down"></i></span>' +
                        "</div>" +
                        '<div class="variant-card-body">' +
                        '<div class="variant-card-body-inner">' +
                        '<div class="variant-fields-row">' +
                        '<div class="variant-field"><label class="variant-field-label">Price (₹)</label><input type="number" class="form-control variant-price-inp" step="0.01" min="0" value="' +
                        escapeHtml(v.price) +
                        '" data-variant-id="' +
                        v.id +
                        '"></div>' +
                        '<div class="variant-field"><label class="variant-field-label">Stock</label><input type="number" class="form-control variant-stock-inp" min="0" value="' +
                        (v.stock_quantity || 0) +
                        '" data-variant-id="' +
                        v.id +
                        '"></div>' +
                        '<div class="variant-field"><label class="variant-field-label">SKU</label><input type="text" class="form-control variant-sku-inp" value="' +
                        escapeHtml(v.sku || "") +
                        '" placeholder="Optional" data-variant-id="' +
                        v.id +
                        '"></div>' +
                        '<div class="variant-field"><label class="variant-field-label">Order</label><input type="number" class="form-control variant-order-inp" min="0" value="' +
                        (v.display_order || 0) +
                        '" data-variant-id="' +
                        v.id +
                        '"></div>' +
                        '<button type="button" class="btn btn-primary btn-sm variant-save-btn" data-variant-id="' +
                        v.id +
                        '">Save</button>' +
                        "</div>" +
                        '<div class="variant-fields-row variant-shipping-row">' +
                        '<div class="variant-field"><label class="variant-field-label">Weight (kg)</label><input type="number" class="form-control variant-weight-inp" step="0.001" min="0" value="' +
                        (v.weight != null && v.weight !== "" ? v.weight : "0") +
                        '" placeholder="0" data-variant-id="' + v.id + '"></div>' +
                        '<div class="variant-field"><label class="variant-field-label">Length (cm)</label><input type="number" class="form-control variant-length-inp" step="0.01" min="0" value="' +
                        (v.length != null && v.length !== "" ? v.length : "0") +
                        '" placeholder="0" data-variant-id="' + v.id + '"></div>' +
                        '<div class="variant-field"><label class="variant-field-label">Breadth (cm)</label><input type="number" class="form-control variant-breadth-inp" step="0.01" min="0" value="' +
                        (v.breadth != null && v.breadth !== "" ? v.breadth : "0") +
                        '" placeholder="0" data-variant-id="' + v.id + '"></div>' +
                        '<div class="variant-field"><label class="variant-field-label">Height (cm)</label><input type="number" class="form-control variant-height-inp" step="0.01" min="0" value="' +
                        (v.height != null && v.height !== "" ? v.height : "0") +
                        '" placeholder="0" data-variant-id="' + v.id + '"></div>' +
                        "</div>" +
                        '<div class="nested-block variant-images-block">' +
                        '<div class="nested-title">Images</div>' +
                        '<div class="variant-images-list">' +
                        imgsHtml +
                        "</div>" +
                        '<button type="button" class="btn btn-sm btn-secondary variant-add-image" data-variant-id="' +
                        v.id +
                        '">Add image</button>' +
                        "</div>" +
                        "</div></div>";
                    variantsList.appendChild(card);
                });
                // Expand/collapse
                variantsList.querySelectorAll(".variant-card-header").forEach(function (h) {
                    h.addEventListener("click", function (ev) {
                        if (ev.target.closest("button") || ev.target.closest("label")) return;
                        var card = h.closest(".variant-card");
                        card.classList.toggle("expanded");
                        h.setAttribute("aria-expanded", card.classList.contains("expanded"));
                    });
                });
                // Expand the newly added variant so Images section is visible
                if (expandVariantId) {
                    var cardToExpand = variantsList.querySelector('.variant-card[data-variant-id="' + expandVariantId + '"]');
                    if (cardToExpand) {
                        cardToExpand.classList.add("expanded");
                        var header = cardToExpand.querySelector(".variant-card-header");
                        if (header) header.setAttribute("aria-expanded", "true");
                    }
                }
            })
            .catch(function () {
                if (variantsLoading) variantsLoading.style.display = "none";
                variantsList.innerHTML = '<p class="save-feedback err">Failed to load variants.</p>';
            });
    }

    // --- Simple product base images (ProductImage) ---
    (function setupSimpleProductImages() {
        var section = document.getElementById("simple-product-settings");
        if (!section) return;
        var hasVariants = section.getAttribute("data-has-variants") === "true";
        var maxImages = parseInt(section.querySelector("#simple-product-images").getAttribute("data-max-images") || "3", 10) || 3;
        var productId = section.getAttribute("data-product-id");
        var urlUpload = section.getAttribute("data-url-upload-base-image");
        var urlDeleteTpl = section.getAttribute("data-url-delete-base-image");
        var urlSetPrimaryTpl = section.getAttribute("data-url-set-primary-base-image");
        var urlReorder = section.getAttribute("data-url-reorder-base-image");
        var listEl = document.getElementById("simple-product-images-list");
        var addBtn = document.getElementById("base-image-add-btn");

        if (!productId || !urlUpload || !listEl || !addBtn) return;

        function syncVisibility() {
            if (hasVariants) {
                section.classList.add("simple-product-disabled");
                addBtn.disabled = true;
            } else {
                section.classList.remove("simple-product-disabled");
                addBtn.disabled = listEl.querySelectorAll(".image-item").length >= maxImages;
            }
        }

        syncVisibility();

        // Upload handler
        addBtn.addEventListener("click", function () {
            if (addBtn.disabled) return;
            var input = document.createElement("input");
            input.type = "file";
            input.accept = "image/*";
            input.onchange = function () {
                if (!input.files || !input.files[0]) return;
                var fd = new FormData();
                fd.append("image", input.files[0]);
                fd.append("csrfmiddlewaretoken", csrf);
                showLoader();
                fetch(urlUpload, {
                    method: "POST",
                    body: fd,
                    credentials: "same-origin",
                })
                    .then(function (r) {
                        return r.json();
                    })
                    .then(function (res) {
                        if (res.success && res.image) {
                            var img = res.image;
                            var div = document.createElement("div");
                            div.className = "image-item";
                            div.setAttribute("data-image-id", img.id);
                            div.innerHTML =
                                (img.url
                                    ? '<img class="image-thumb" src="' + escapeHtml(img.url) + '" alt="">'
                                    : '<span class="image-thumb" style="width:72px;height:72px;background:#eee;border-radius:6px;display:block;"></span>') +
                                (img.is_primary ? '<span class="image-primary-badge">Primary</span>' : "") +
                                '<div class="image-actions">' +
                                (img.is_primary
                                    ? ""
                                    : '<button type="button" class="btn btn-sm btn-outline base-image-set-primary" data-image-id="' +
                                      img.id +
                                      '">Primary</button>') +
                                '<button type="button" class="btn btn-sm btn-danger base-image-delete" data-image-id="' +
                                img.id +
                                '"><i class="fas fa-times"></i></button>' +
                                "</div>";
                            listEl.appendChild(div);
                            syncVisibility();
                        } else {
                            toast(
                                (res.errors &&
                                    ((res.errors.image && res.errors.image[0]) ||
                                        (res.errors.__all__ && res.errors.__all__[0]))) ||
                                    "Error uploading image.",
                                "error"
                            );
                        }
                    })
                    .catch(function () {
                        toast("Network error.", "error");
                    })
                    .finally(hideLoader);
            };
            input.click();
        });

        // Delete / set-primary handlers
        app.addEventListener("click", function (e) {
            var btn = e.target.closest("button");
            if (!btn) return;

            if (btn.classList.contains("base-image-delete")) {
                var imageId = btn.getAttribute("data-image-id");
                if (!imageId || !confirm("Remove this image?")) return;
                var url = (urlDeleteTpl || "").replace("/0/", "/" + imageId + "/");
                showLoader();
                fetch(url, {
                    method: "POST",
                    headers: headers(false),
                    credentials: "same-origin",
                })
                    .then(function (r) {
                        return r.json();
                    })
                    .then(function (res) {
                        if (res.success) {
                            var item = listEl.querySelector('.image-item[data-image-id="' + imageId + '"]');
                            if (item && item.parentNode) item.parentNode.removeChild(item);
                            syncVisibility();
                        } else {
                            toast("Could not remove image.", "error");
                        }
                    })
                    .catch(function () {
                        toast("Network error.", "error");
                    })
                    .finally(hideLoader);
                return;
            }

            if (btn.classList.contains("base-image-set-primary")) {
                var imageId2 = btn.getAttribute("data-image-id");
                if (!imageId2) return;
                var url2 = (urlSetPrimaryTpl || "").replace("/0/", "/" + imageId2 + "/");
                showLoader();
                fetch(url2, {
                    method: "POST",
                    headers: headers(false),
                    credentials: "same-origin",
                })
                    .then(function (r) {
                        return r.json();
                    })
                    .then(function (res) {
                        if (res.success) {
                            listEl.querySelectorAll(".image-item").forEach(function (el) {
                                el.querySelectorAll(".image-primary-badge").forEach(function (b) {
                                    b.parentNode.removeChild(b);
                                });
                                el.querySelectorAll(".base-image-set-primary").forEach(function (b) {
                                    b.style.display = "";
                                });
                            });
                            var item2 = listEl.querySelector('.image-item[data-image-id="' + imageId2 + '"]');
                            if (item2) {
                                var badge = document.createElement("span");
                                badge.className = "image-primary-badge";
                                badge.textContent = "Primary";
                                item2.insertBefore(badge, item2.firstChild.nextSibling);
                                var btnPrimary = item2.querySelector(".base-image-set-primary");
                                if (btnPrimary) btnPrimary.style.display = "none";
                            }
                        } else {
                            toast("Could not set primary image.", "error");
                        }
                    })
                    .catch(function () {
                        toast("Network error.", "error");
                    })
                    .finally(hideLoader);
                return;
            }
        });

        // Optional: simple drag-based reorder can be added later; for now we expose API but not UI.
    })();

    app.addEventListener("click", function (e) {
        var target = e.target.closest ? e.target.closest("button") : null;
        if (!target) return;
        if (target.id === "variant-add-btn") {
            fetch(urls.attributes, { method: "GET", credentials: "same-origin" })
                .then(function (r) {
                    return r.json();
                })
                .then(function (data) {
                    var attrs = data.attributes || [];
                    if (attrs.length === 0) {
                        toast("Add at least one attribute with values first.", "error");
                        return;
                    }
                    addVariantAttributeValues.innerHTML = attrs
                        .map(
                            function (attr) {
                                var opts = (attr.values || [])
                                    .map(
                                        function (v) {
                                            return '<option value="' + v.id + '">' + escapeHtml(v.value) + "</option>";
                                        }
                                    )
                                    .join("");
                                return (
                                    '<div class="form-group">' +
                                    '<label class="form-label">' +
                                    escapeHtml(attr.name) +
                                    '</label>' +
                                    '<select class="form-control add-variant-attr-select" data-attr-id="' +
                                    attr.id +
                                    '">' +
                                    '<option value="">—</option>' +
                                    opts +
                                    "</select>" +
                                    "</div>"
                                );
                            }
                        )
                        .join("");
                    addVariantPrice.value = "";
                    addVariantStock.value = "0";
                    if (addVariantSku) addVariantSku.value = "";
                    if (addVariantImage) addVariantImage.value = "";

                    var activeToggle = document.getElementById("add-variant-is_active");
                    var activeWrap = activeToggle && activeToggle.closest(".toggle-wrap");
                    if (activeToggle) activeToggle.checked = true;
                    if (activeWrap) {
                        activeWrap.classList.add("checked");
                        var status = activeWrap.querySelector(".toggle-status");
                        if (status) status.textContent = "On";
                    }

                    addVariantModal.classList.add("is-open");
                    addVariantModal.setAttribute("aria-hidden", "false");
                });
            return;
        }
        if (target.id === "add-variant-cancel") {
            addVariantModal.classList.remove("is-open");
            addVariantModal.setAttribute("aria-hidden", "true");
            return;
        }
        if (target.id === "add-variant-submit") {
            var selects = addVariantModal.querySelectorAll(".add-variant-attr-select");
            var attribute_value_ids = [];
            selects.forEach(function (sel) {
                var val = sel.value;
                if (val) attribute_value_ids.push(parseInt(val, 10));
            });
            if (attribute_value_ids.length === 0) {
                toast("Select at least one attribute value.", "error");
                return;
            }
            var priceVal = addVariantPrice && addVariantPrice.value;
            if (!priceVal || parseFloat(priceVal) < 0) {
                toast("Enter a valid price.", "error");
                return;
            }
            var weightInp = document.getElementById("add-variant-weight");
            var lengthInp = document.getElementById("add-variant-length");
            var breadthInp = document.getElementById("add-variant-breadth");
            var heightInp = document.getElementById("add-variant-height");
            var payload = {
                attribute_value_ids: attribute_value_ids,
                price: priceVal,
                stock_quantity: parseInt((addVariantStock && addVariantStock.value) || 0, 10) || 0,
                sku: (addVariantSku && addVariantSku.value || "").trim() || null,
                is_active: document.getElementById("add-variant-is_active") ? document.getElementById("add-variant-is_active").checked : true,
            };
            if (weightInp) payload.weight = parseFloat(weightInp.value) || 0;
            if (lengthInp) payload.length = parseFloat(lengthInp.value) || 0;
            if (breadthInp) payload.breadth = parseFloat(breadthInp.value) || 0;
            if (heightInp) payload.height = parseFloat(heightInp.value) || 0;
            addVariantSubmit.disabled = true;
            showLoader();
            fetch(urls.variantAdd, {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify(payload),
                credentials: "same-origin",
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (res) {
                    addVariantSubmit.disabled = false;
                    if (res.success) {
                        var newVariantId = res.variant && res.variant.id;
                        addVariantModal.classList.remove("is-open");
                        addVariantModal.setAttribute("aria-hidden", "true");
                        toast("Variant added.");
                        var fileToUpload = addVariantImage && addVariantImage.files && addVariantImage.files[0];
                        if (fileToUpload && newVariantId) {
                            var fd = new FormData();
                            fd.append("image", fileToUpload);
                            fd.append("csrfmiddlewaretoken", csrf);
                            fetch(url(urls.variantUploadImage, newVariantId), {
                                method: "POST",
                                body: fd,
                                credentials: "same-origin",
                            })
                                .then(function (r) { return r.json(); })
                                .then(function (imgRes) {
                                    if (imgRes.success) toast("Image added.");
                                    loadVariants(newVariantId);
                                })
                                .catch(function () {
                                    loadVariants(newVariantId);
                                })
                                .finally(function () {
                                    if (addVariantImage) addVariantImage.value = "";
                                });
                        } else {
                            loadVariants(newVariantId);
                        }
                    } else {
                        var err =
                            (res.errors && res.errors.attribute_value_ids && res.errors.attribute_value_ids[0]) ||
                            (res.errors && res.errors.price && res.errors.price[0]) ||
                            (res.errors && res.errors.sku && res.errors.sku[0]) ||
                            "Error adding variant.";
                        toast(err, "error");
                    }
                })
                .catch(function () {
                    addVariantSubmit.disabled = false;
                    toast("Network error.", "error");
                })
                .finally(hideLoader);
            return;
        }
        if (target.classList.contains("variant-save-btn")) {
            var vid = target.getAttribute("data-variant-id");
            if (!vid) return;
            var card = target.closest(".variant-card");
            var priceInp = card.querySelector(".variant-price-inp");
            var stockInp = card.querySelector(".variant-stock-inp");
            var skuInp = card.querySelector(".variant-sku-inp");
            var orderInp = card.querySelector(".variant-order-inp");
            var activeCb = card.querySelector(".variant-is-active");
            var weightInp = card.querySelector(".variant-weight-inp");
            var lengthInp = card.querySelector(".variant-length-inp");
            var breadthInp = card.querySelector(".variant-breadth-inp");
            var heightInp = card.querySelector(".variant-height-inp");
            var payload = {};
            if (priceInp) payload.price = priceInp.value;
            if (stockInp) payload.stock_quantity = parseInt(stockInp.value, 10) || 0;
            if (skuInp) payload.sku = (skuInp.value || "").trim() || null;
            if (orderInp) payload.display_order = parseInt(orderInp.value, 10) || 0;
            if (activeCb) payload.is_active = activeCb.checked;
            if (weightInp) payload.weight = parseFloat(weightInp.value) || 0;
            if (lengthInp) payload.length = parseFloat(lengthInp.value) || 0;
            if (breadthInp) payload.breadth = parseFloat(breadthInp.value) || 0;
            if (heightInp) payload.height = parseFloat(heightInp.value) || 0;
            showLoader();
            fetch(url(urls.variantUpdate, vid), {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify(payload),
                credentials: "same-origin",
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (res) {
                    if (res.success) {
                        toast("Variant updated.");
                        loadVariants();
                    } else {
                        toast((res.errors && (res.errors.price && res.errors.price[0]) || (res.errors.sku && res.errors.sku[0])) || "Error", "error");
                    }
                })
                .catch(function () {
                    toast("Network error.", "error");
                })
                .finally(hideLoader);
            return;
        }
        if (target.classList.contains("variant-delete")) {
            var vid = target.getAttribute("data-variant-id");
            if (!vid || !confirm("Delete this variant?")) return;
            showLoader();
            fetch(url(urls.variantDelete, vid), {
                method: "POST",
                headers: headers(false),
                credentials: "same-origin",
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (res) {
                    if (res.success) {
                        toast("Variant deleted.");
                        loadVariants();
                    } else {
                        toast("Could not delete.", "error");
                    }
                })
                .catch(function () {
                    toast("Network error.", "error");
                })
                .finally(hideLoader);
            return;
        }
        if (target.classList.contains("variant-add-image")) {
            var vid = target.getAttribute("data-variant-id");
            if (!vid) return;
            var input = document.createElement("input");
            input.type = "file";
            input.accept = "image/*";
            input.onchange = function () {
                if (!input.files || !input.files[0]) return;
                var fd = new FormData();
                fd.append("image", input.files[0]);
                fd.append("csrfmiddlewaretoken", csrf);
                showLoader();
                fetch(url(urls.variantUploadImage, vid), {
                    method: "POST",
                    body: fd,
                    credentials: "same-origin",
                })
                    .then(function (r) {
                        return r.json();
                    })
                    .then(function (res) {
                        if (res.success) {
                            toast("Image added.");
                            loadVariants();
                        } else {
                            toast((res.errors && res.errors.image && res.errors.image[0]) || "Error", "error");
                        }
                    })
                    .catch(function () {
                        toast("Network error.", "error");
                    })
                    .finally(hideLoader);
            };
            input.click();
            return;
        }
        if (target.classList.contains("image-delete")) {
            var imageId = target.getAttribute("data-image-id");
            if (!imageId || !confirm("Remove this image?")) return;
            showLoader();
            fetch(url(urls.variantImageDelete, imageId), {
                method: "POST",
                headers: headers(false),
                credentials: "same-origin",
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (res) {
                    if (res.success) {
                        toast("Image removed.");
                        loadVariants();
                    } else {
                        toast("Could not remove.", "error");
                    }
                })
                .catch(function () {
                    toast("Network error.", "error");
                })
                .finally(hideLoader);
            return;
        }
        if (target.classList.contains("image-set-primary")) {
            var imageId = target.getAttribute("data-image-id");
            if (!imageId) return;
            showLoader();
            fetch(url(urls.variantImageSetPrimary, imageId), {
                method: "POST",
                headers: headers(false),
                credentials: "same-origin",
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (res) {
                    if (res.success) {
                        toast("Primary image set.");
                        loadVariants();
                    } else {
                        toast("Error.", "error");
                    }
                })
                .catch(function () {
                    toast("Network error.", "error");
                })
                .finally(hideLoader);
            return;
        }
    });

    // Variant active toggle: sync to server on change
    app.addEventListener("change", function (e) {
        if (!e.target || !e.target.classList.contains("variant-is-active")) return;
        var vid = e.target.getAttribute("data-variant-id");
        if (!vid) return;
        var isActive = e.target.checked;
        fetch(url(urls.variantUpdate, vid), {
            method: "POST",
            headers: headers(true),
            body: JSON.stringify({ is_active: isActive }),
            credentials: "same-origin",
        })
            .then(function (r) {
                return r.json();
            })
            .then(function (res) {
                    if (!res.success) {
                        e.target.checked = !isActive;
                        var wrap = e.target.closest(".toggle-wrap");
                        if (wrap) wrap.classList.toggle("checked", !isActive);
                        toast((res.errors && res.errors.is_active && res.errors.is_active[0]) || "Error", "error");
                    } else {
                        var wrap = e.target.closest(".toggle-wrap");
                        if (wrap) wrap.classList.toggle("checked", isActive);
                        toast(isActive ? "Variant active." : "Variant inactive.");
                    }
                })
            .catch(function () {
                e.target.checked = !isActive;
                toast("Network error.", "error");
            });
    });

    loadAttributes();
    loadVariants();
})();
