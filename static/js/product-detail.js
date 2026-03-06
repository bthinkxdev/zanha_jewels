// Queen Orange - Product Detail Page

const sizeColorStock = window.sizeColorStock || {};
const useColorVariants = window.useColorVariants || false;
const colorSizesStock = window.colorSizesStock || {};
const productId = window.productId || null;
const colorImagesFallback = window.colorImagesFallback || [];
const allColorImages = window.allColorImages || {};

function updateColorOptions() {
    if (useColorVariants) return;
    var selectedSizeEl = document.getElementById('selectedSize');
    if (!selectedSizeEl) return;
    var selectedSize = selectedSizeEl.value;
    var colorOptions = document.querySelectorAll('#colorOptions .color-option');
    const colorMessage = document.getElementById('colorMessage');
    const colorOptionsContainer = document.getElementById('colorOptions');
    if (!colorOptionsContainer) return;
    var sizeColorData = (sizeColorStock && sizeColorStock[selectedSize]) || {};
    const hasNoColorVariant = sizeColorData['no_color'] === true;
    const availableColors = Object.keys(sizeColorData).filter(function(key) {
        return key !== 'no_color' && sizeColorData[key] === true;
    });

    if (availableColors.length === 0 && !hasNoColorVariant) {
        if (colorMessage) {
            colorMessage.style.display = 'block';
            colorMessage.textContent = 'Size: N/A';
        }
        colorOptionsContainer.style.display = 'none';
        var selColor = document.getElementById('selectedColor');
        if (selColor) selColor.value = '';
    } else if (availableColors.length === 0 && hasNoColorVariant) {
        if (colorMessage) {
            colorMessage.style.display = 'block';
            colorMessage.textContent = 'Color: N/A';
        }
        colorOptionsContainer.style.display = 'none';
        var selColor = document.getElementById('selectedColor');
        if (selColor) selColor.value = '';
    } else {
        if (colorMessage) colorMessage.style.display = 'none';
        colorOptionsContainer.style.display = 'flex';
        colorOptions.forEach(function(option) {
            var color = option.dataset.color;
            var isInStock = sizeColorData[color] === true;
            option.style.opacity = isInStock ? '1' : '0.4';
            option.style.cursor = isInStock ? 'pointer' : 'not-allowed';
            option.classList.toggle('disabled', !isInStock);
            option.dataset.available = isInStock ? 'true' : 'false';
        });
        var firstAvailable = Array.from(colorOptions).find(function(opt) { return opt.dataset.available === 'true'; });
        if (firstAvailable) {
            colorOptions.forEach(function(opt) { opt.classList.remove('selected'); });
            firstAvailable.classList.add('selected');
            var selColor = document.getElementById('selectedColor');
            if (selColor) selColor.value = firstAvailable.dataset.color;
        }
    }
}

function renderSizeOptionsForColor(colorName) {
    var container = document.getElementById('sizeOptionsContainer');
    var sizeMessage = document.getElementById('sizeMessage');
    var selectedSizeVariantIdEl = document.getElementById('selectedSizeVariantId');
    if (!container) return;
    var sizesData = colorSizesStock[colorName];
    container.innerHTML = '';
    if (selectedSizeVariantIdEl) selectedSizeVariantIdEl.value = '';
    if (sizeMessage) sizeMessage.style.display = 'none';

    if (!sizesData || typeof sizesData !== 'object') {
        if (sizeMessage) {
            sizeMessage.textContent = 'No sizes for this color';
            sizeMessage.style.display = 'block';
        }
        return;
    }
    var sizes = Object.keys(sizesData);
    if (sizes.length === 0) {
        if (sizeMessage) {
            sizeMessage.textContent = 'Out of stock';
            sizeMessage.style.display = 'block';
        }
        return;
    }
    var firstInStock = null;
    sizes.forEach(function(size) {
        var info = sizesData[size];
        var inStock = info && info.in_stock;
        var sizeVariantId = info && info.size_variant_id;
        var div = document.createElement('div');
        div.className = 'size-option' + (inStock && !firstInStock ? ' selected' : '') + (inStock ? '' : ' disabled');
        div.dataset.size = size;
        div.dataset.sizeVariantId = sizeVariantId || '';
        div.dataset.available = inStock ? 'true' : 'false';
        div.textContent = size;
        if (!inStock) {
            div.style.opacity = '0.4';
            div.style.cursor = 'not-allowed';
        }
        container.appendChild(div);
        if (inStock && !firstInStock) {
            firstInStock = sizeVariantId;
            if (selectedSizeVariantIdEl) selectedSizeVariantIdEl.value = sizeVariantId || '';
        }
    });
}

function updateGallery(images) {
    var mainImg = document.getElementById('mainImage');
    var thumbContainer = document.getElementById('imageThumbnails');
    if (!mainImg) return;
    var list = images && images.length ? images : (colorImagesFallback && colorImagesFallback.length ? colorImagesFallback : []);
    if (list.length === 0) {
        var placeholder = document.querySelector('img[src*="banner.png"]') ? document.querySelector('img[src*="banner.png"]').src : '/static/images/banner.png';
        mainImg.src = placeholder;
        mainImg.alt = 'No image for this color';
        if (thumbContainer) {
            thumbContainer.innerHTML = '';
            var div = document.createElement('div');
            div.className = 'image-thumbnail active';
            div.dataset.src = placeholder;
            var im = document.createElement('img');
            im.src = placeholder;
            im.alt = 'Placeholder';
            div.appendChild(im);
            thumbContainer.appendChild(div);
        }
        return;
    }
    var primary = list.find(function(i) { return i.is_primary; }) || list[0];
    var url = primary.url || primary;
    if (typeof url !== 'string') url = primary.url;
    mainImg.src = url;
    if (thumbContainer) {
        thumbContainer.innerHTML = '';
        var primaryUrl = primary.url || primary;
        if (typeof primaryUrl !== 'string') primaryUrl = primary.url;
        list.forEach(function(img, idx) {
            var u = img.url || img;
            if (typeof u !== 'string') u = img.url;
            var isActive = (primaryUrl && u === primaryUrl) || (idx === 0);
            var div = document.createElement('div');
            div.className = 'image-thumbnail' + (isActive ? ' active' : '');
            div.dataset.src = u;
            var im = document.createElement('img');
            im.src = u;
            im.alt = 'Product image';
            div.appendChild(im);
            div.addEventListener('click', function() {
                mainImg.src = div.dataset.src;
                thumbContainer.querySelectorAll('.image-thumbnail').forEach(function(t) { t.classList.remove('active'); });
                div.classList.add('active');
                scrollThumbIntoView(div);
            });
            thumbContainer.appendChild(div);
        });
        scrollThumbIntoView(thumbContainer.querySelector('.image-thumbnail.active'));
        if (typeof window.productGalleryRestartAutoSlide === 'function') window.productGalleryRestartAutoSlide();
    }
}

function scrollThumbIntoView(thumb) {
    if (!thumb || !thumb.parentElement) return;
    var container = thumb.parentElement;
    container.scrollTo({
        left: thumb.offsetLeft - (container.offsetWidth / 2) + (thumb.offsetWidth / 2),
        behavior: 'smooth'
    });
}

function fetchColorImages(colorVariantId) {
    var baseUrl = window.productColorImagesUrl || '/products/color-images/';
    var sep = baseUrl.indexOf('?') >= 0 ? '&' : '?';
    var url = baseUrl + sep + 'color_variant_id=' + encodeURIComponent(colorVariantId);
    if (productId) url += '&product_id=' + encodeURIComponent(productId);
    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var images = (data && data.images) ? data.images : [];
            updateGallery(images);
        })
        .catch(function() {
            updateGallery([]);
        });
}

// --- Product image viewer modal (zoom, pan, pinch) ---
(function productImageViewer() {
    var modal = document.getElementById('productImageModal');
    var backdrop = document.getElementById('productImageModalBackdrop');
    var closeBtn = document.getElementById('productImageModalClose');
    var viewport = document.getElementById('productImageModalViewport');
    var imgWrap = document.getElementById('productImageModalImgWrap');
    var imgEl = document.getElementById('productImageModalImg');
    var errorEl = document.getElementById('productImageModalError');
    var navEl = document.getElementById('productImageModalNav');
    var prevBtn = document.getElementById('productImageModalPrev');
    var nextBtn = document.getElementById('productImageModalNext');

    if (!modal || !imgEl || !viewport || !imgWrap) return;

    var state = {
        scale: 1,
        translateX: 0,
        translateY: 0,
        isPanning: false,
        startX: 0,
        startY: 0,
        startTx: 0,
        startTy: 0,
        lastTapTime: 0,
        doubleTapZoom: 1,
        pinchStartScale: 1,
        pinchStartDist: 0,
        imageUrls: [],
        currentIndex: 0,
        transition: true
    };

    var MIN_SCALE = 0.5;
    var MAX_SCALE = 5;
    var DOUBLE_TAP_MS = 300;
    var WHEEL_ZOOM_STEP = 0.12;

    function getImageUrls() {
        var main = document.getElementById('mainImage');
        var thumbs = document.querySelectorAll('#imageThumbnails .image-thumbnail[data-src]');
        var urls = [];
        var seen = {};
        if (main && main.src) {
            var u = main.src;
            if (u && !seen[u]) { seen[u] = 1; urls.push(u); }
        }
        for (var i = 0; i < thumbs.length; i++) {
            var s = thumbs[i].dataset.src;
            if (s && !seen[s]) { seen[s] = 1; urls.push(s); }
        }
        return urls;
    }

    function applyTransform() {
        var s = state.scale;
        var tx = state.translateX;
        var ty = state.translateY;
        imgWrap.style.transform = 'translate(' + tx + 'px, ' + ty + 'px) scale(' + s + ')';
    }

    function setTransition(on) {
        state.transition = on;
        imgWrap.classList.toggle('no-transition', !on);
    }

    function resetZoomPan() {
        state.scale = 1;
        state.translateX = 0;
        state.translateY = 0;
        setTransition(true);
        applyTransform();
    }

    function openModal(url, index) {
        if (!url) return;
        state.imageUrls = getImageUrls();
        state.currentIndex = state.imageUrls.indexOf(url);
        if (state.currentIndex < 0) state.currentIndex = 0;
        var actualUrl = state.imageUrls[state.currentIndex] || url;

        errorEl.setAttribute('hidden', '');
        imgEl.removeAttribute('hidden');
        imgEl.alt = 'Product image';
        imgEl.src = actualUrl;
        resetZoomPan();

        if (state.imageUrls.length > 1) {
            navEl.removeAttribute('hidden');
            prevBtn.disabled = state.currentIndex <= 0;
            nextBtn.disabled = state.currentIndex >= state.imageUrls.length - 1;
        } else {
            navEl.setAttribute('hidden', '');
        }

        modal.removeAttribute('hidden');
        modal.classList.add('is-open');
        document.body.style.overflow = 'hidden';

        if (prevBtn) prevBtn.addEventListener('click', onPrevClick);
        if (nextBtn) nextBtn.addEventListener('click', onNextClick);
        backdrop.addEventListener('click', closeModal);
        closeBtn.addEventListener('click', closeModal);
        viewport.addEventListener('wheel', onWheel, { passive: false });
        viewport.addEventListener('mousedown', onPointerDown);
        window.addEventListener('mousemove', onPointerMove);
        window.addEventListener('mouseup', onPointerUp);
        viewport.addEventListener('touchstart', onTouchStart, { passive: false });
        viewport.addEventListener('touchmove', onTouchMove, { passive: false });
        viewport.addEventListener('touchend', onTouchEnd, { passive: true });
        viewport.addEventListener('touchcancel', onTouchEnd, { passive: true });
        window.addEventListener('resize', onResize);
        window.addEventListener('orientationchange', onResize);
        document.addEventListener('keydown', onKeyDown);
    }

    function closeModal() {
        modal.classList.remove('is-open');
        modal.setAttribute('hidden', '');
        document.body.style.overflow = '';

        backdrop.removeEventListener('click', closeModal);
        closeBtn.removeEventListener('click', closeModal);
        viewport.removeEventListener('wheel', onWheel);
        viewport.removeEventListener('mousedown', onPointerDown);
        window.removeEventListener('mousemove', onPointerMove);
        window.removeEventListener('mouseup', onPointerUp);
        viewport.removeEventListener('touchstart', onTouchStart);
        viewport.removeEventListener('touchmove', onTouchMove);
        viewport.removeEventListener('touchend', onTouchEnd);
        viewport.removeEventListener('touchcancel', onTouchEnd);
        window.removeEventListener('resize', onResize);
        window.removeEventListener('orientationchange', onResize);
        document.removeEventListener('keydown', onKeyDown);
        if (prevBtn) prevBtn.removeEventListener('click', onPrevClick);
        if (nextBtn) nextBtn.removeEventListener('click', onNextClick);
    }

    function onPrevClick(e) {
        e.stopPropagation();
        if (state.currentIndex <= 0) return;
        state.currentIndex--;
        setImageByIndex();
        prevBtn.disabled = state.currentIndex <= 0;
        nextBtn.disabled = state.currentIndex >= state.imageUrls.length - 1;
    }

    function onNextClick(e) {
        e.stopPropagation();
        if (state.currentIndex >= state.imageUrls.length - 1) return;
        state.currentIndex++;
        setImageByIndex();
        prevBtn.disabled = state.currentIndex <= 0;
        nextBtn.disabled = state.currentIndex >= state.imageUrls.length - 1;
    }

    function setImageByIndex() {
        var url = state.imageUrls[state.currentIndex];
        if (!url) return;
        errorEl.setAttribute('hidden', '');
        imgEl.removeAttribute('hidden');
        imgEl.src = url;
        resetZoomPan();
    }

    function onWheel(e) {
        if (!modal.classList.contains('is-open')) return;
        e.preventDefault();
        var delta = e.deltaY > 0 ? -WHEEL_ZOOM_STEP : WHEEL_ZOOM_STEP;
        var rect = viewport.getBoundingClientRect();
        var cx = e.clientX - rect.left - rect.width / 2;
        var cy = e.clientY - rect.top - rect.height / 2;
        var newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, state.scale + delta));
        var ratio = newScale / state.scale;
        state.translateX = cx - (cx - state.translateX) * ratio;
        state.translateY = cy - (cy - state.translateY) * ratio;
        state.scale = newScale;
        setTransition(true);
        applyTransform();
    }

    function onPointerDown(e) {
        if (e.button !== 0) return;
        state.isPanning = true;
        state.startX = e.clientX;
        state.startY = e.clientY;
        state.startTx = state.translateX;
        state.startTy = state.translateY;
        viewport.classList.add('is-panning');
    }

    function onPointerMove(e) {
        if (!state.isPanning) return;
        state.translateX = state.startTx + (e.clientX - state.startX);
        state.translateY = state.startTy + (e.clientY - state.startY);
        setTransition(false);
        applyTransform();
    }

    function onPointerUp() {
        state.isPanning = false;
        viewport.classList.remove('is-panning');
    }

    function getTouchDistance(touches) {
        if (touches.length < 2) return 0;
        var a = touches[0];
        var b = touches[1];
        return Math.hypot(b.clientX - a.clientX, b.clientY - a.clientY);
    }

    function getTouchCenter(touches) {
        if (touches.length === 0) return { x: 0, y: 0 };
        if (touches.length === 1) return { x: touches[0].clientX, y: touches[0].clientY };
        return {
            x: (touches[0].clientX + touches[1].clientX) / 2,
            y: (touches[0].clientY + touches[1].clientY) / 2
        };
    }

    function onTouchStart(e) {
        if (e.touches.length === 2) {
            e.preventDefault();
            state.pinchStartDist = getTouchDistance(e.touches);
            state.pinchStartScale = state.scale;
        } else if (e.touches.length === 1) {
            var now = Date.now();
            if (now - state.lastTapTime <= DOUBLE_TAP_MS) {
                e.preventDefault();
                state.doubleTapZoom = state.scale > 1 ? 1 : 2;
                state.scale = state.doubleTapZoom;
                state.translateX = 0;
                state.translateY = 0;
                setTransition(true);
                applyTransform();
                state.lastTapTime = 0;
                return;
            }
            state.lastTapTime = now;
            state.touchStartX = e.touches[0].clientX;
            state.touchStartY = e.touches[0].clientY;
            state.touchStartTx = state.translateX;
            state.touchStartTy = state.translateY;
        }
    }

    function onTouchMove(e) {
        if (e.touches.length === 2) {
            e.preventDefault();
            var dist = getTouchDistance(e.touches);
            if (state.pinchStartDist > 0) {
                var ratio = dist / state.pinchStartDist;
                var newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, state.pinchStartScale * ratio));
                var rect = viewport.getBoundingClientRect();
                var center = getTouchCenter(e.touches);
                var cx = center.x - rect.left - rect.width / 2;
                var cy = center.y - rect.top - rect.height / 2;
                var scaleRatio = newScale / state.scale;
                state.translateX = cx - (cx - state.translateX) * scaleRatio;
                state.translateY = cy - (cy - state.translateY) * scaleRatio;
                state.scale = newScale;
                setTransition(false);
                applyTransform();
            }
            state.pinchStartDist = dist;
        } else if (e.touches.length === 1 && state.scale > 1) {
            state.translateX = state.touchStartTx + (e.touches[0].clientX - state.touchStartX);
            state.translateY = state.touchStartTy + (e.touches[0].clientY - state.touchStartY);
            setTransition(false);
            applyTransform();
        }
    }

    function onTouchEnd(e) {
        if (e.touches.length < 2) state.pinchStartDist = 0;
    }

    function onResize() {
        if (modal.classList.contains('is-open')) resetZoomPan();
    }

    function onKeyDown(e) {
        if (e.key === 'Escape' && modal.classList.contains('is-open')) {
            closeModal();
        }
    }

    imgEl.onerror = function() {
        errorEl.removeAttribute('hidden');
        imgEl.setAttribute('hidden', '');
    };

    window.productImageViewerOpen = function(url) {
        openModal(url || (document.getElementById('mainImage') && document.getElementById('mainImage').src));
    };
})();

document.addEventListener('DOMContentLoaded', function() {
    var thumbContainer = document.getElementById('imageThumbnails');
    var mainImageEl = document.getElementById('mainImage');
    var mainImageWrap = document.querySelector('.main-image-wrap');
    var thumbs = function() { return thumbContainer ? thumbContainer.querySelectorAll('.image-thumbnail[data-src]') : []; };
    var autoSlideIntervalId = null;
    var AUTO_SLIDE_MS = 4500;

    function setMainImageFromThumb(thumb) {
        if (!thumb || !thumb.dataset.src || !mainImageEl) return;
        mainImageEl.src = thumb.dataset.src;
        thumbContainer.querySelectorAll('.image-thumbnail').forEach(function(t) { t.classList.remove('active'); });
        thumb.classList.add('active');
        scrollThumbIntoView(thumb);
    }

    function goToIndex(index) {
        var list = thumbs();
        if (list.length === 0) return;
        index = ((index % list.length) + list.length) % list.length;
        setMainImageFromThumb(list[index]);
        resetAutoSlide();
    }

    function nextImage() {
        var list = thumbs();
        if (list.length <= 1) return;
        var active = thumbContainer.querySelector('.image-thumbnail.active');
        var idx = Array.prototype.indexOf.call(list, active);
        goToIndex(idx + 1);
    }

    function prevImage() {
        var list = thumbs();
        if (list.length <= 1) return;
        var active = thumbContainer.querySelector('.image-thumbnail.active');
        var idx = Array.prototype.indexOf.call(list, active);
        goToIndex(idx - 1);
    }

    function startAutoSlide() {
        stopAutoSlide();
        var list = thumbs();
        if (mainImageWrap) {
            var prevBtn = mainImageWrap.querySelector('.gallery-prev');
            var nextBtn = mainImageWrap.querySelector('.gallery-next');
            if (prevBtn) prevBtn.style.display = list.length <= 1 ? 'none' : '';
            if (nextBtn) nextBtn.style.display = list.length <= 1 ? 'none' : '';
        }
        if (list.length <= 1) return;
        autoSlideIntervalId = setInterval(nextImage, AUTO_SLIDE_MS);
    }

    function stopAutoSlide() {
        if (autoSlideIntervalId) {
            clearInterval(autoSlideIntervalId);
            autoSlideIntervalId = null;
        }
    }

    function resetAutoSlide() {
        startAutoSlide();
    }

    // Thumbnail click: show image in main box only (do not open modal)
    if (thumbContainer) {
        thumbContainer.addEventListener('click', function(e) {
            var thumb = e.target.closest('.image-thumbnail');
            if (!thumb || !thumb.dataset.src) return;
            e.preventDefault();
            setMainImageFromThumb(thumb);
            startAutoSlide();
        });
    }

    // Manual prev/next buttons
    if (mainImageWrap) {
        var prevBtn = mainImageWrap.querySelector('.gallery-prev');
        var nextBtn = mainImageWrap.querySelector('.gallery-next');
        if (prevBtn) prevBtn.addEventListener('click', function(e) { e.preventDefault(); prevImage(); });
        if (nextBtn) nextBtn.addEventListener('click', function(e) { e.preventDefault(); nextImage(); });
    }

    // Auto-slide when gallery has multiple images
    startAutoSlide();

    // Pause auto-slide when hovering over gallery
    if (mainImageWrap) {
        mainImageWrap.addEventListener('mouseenter', stopAutoSlide);
        mainImageWrap.addEventListener('mouseleave', function() {
            if (thumbs().length > 1) startAutoSlide();
        });
    }

    window.productGalleryRestartAutoSlide = startAutoSlide;

    // Main image click opens zoom modal
    var mainImageTrigger = document.querySelector('.js-product-image-open-modal');
    if (mainImageTrigger) {
        mainImageTrigger.addEventListener('click', function() {
            var mainImage = document.getElementById('mainImage');
            if (mainImage && mainImage.src && window.productImageViewerOpen) window.productImageViewerOpen(mainImage.src);
        });
        mainImageTrigger.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                var mainImage = document.getElementById('mainImage');
                if (mainImage && mainImage.src && window.productImageViewerOpen) window.productImageViewerOpen(mainImage.src);
            }
        });
    }

    if (useColorVariants) {
        var colorOptions = document.querySelectorAll('#colorOptions .color-option[data-color-variant-id]');
        var firstColor = colorOptions[0];
        if (firstColor) {
            var firstColorName = firstColor.dataset.color;
            var firstCvId = firstColor.dataset.colorVariantId;
            var selColorEl = document.getElementById('selectedColor');
            if (selColorEl) selColorEl.value = firstColorName || '';
            renderSizeOptionsForColor(firstColorName);
            if (firstCvId) {
                var preloaded = allColorImages[firstCvId];
                if (preloaded && preloaded.length) {
                    updateGallery(preloaded);
                } else {
                    fetchColorImages(firstCvId);
                }
            }
        }
        colorOptions.forEach(function(option) {
            option.addEventListener('click', function() {
                if (option.classList.contains('disabled')) return;
                colorOptions.forEach(function(o) { o.classList.remove('selected'); });
                option.classList.add('selected');
                var colorName = option.dataset.color;
                var cvId = option.dataset.colorVariantId;
                var selColorEl = document.getElementById('selectedColor');
                if (selColorEl) selColorEl.value = colorName || '';
                renderSizeOptionsForColor(colorName);
                if (cvId) {
                    var preloaded = allColorImages[cvId];
                    if (preloaded && preloaded.length) {
                        updateGallery(preloaded);
                    } else {
                        fetchColorImages(cvId);
                    }
                }
            });
        });
        var sizeContainer = document.getElementById('sizeOptionsContainer');
        if (sizeContainer) {
            sizeContainer.addEventListener('click', function(e) {
                var sizeOpt = e.target.closest('.size-option');
                if (!sizeOpt || sizeOpt.dataset.available !== 'true') return;
                sizeContainer.querySelectorAll('.size-option').forEach(function(o) { o.classList.remove('selected'); });
                sizeOpt.classList.add('selected');
                var sid = document.getElementById('selectedSizeVariantId');
                if (sid) sid.value = sizeOpt.dataset.sizeVariantId || '';
                var selSize = document.getElementById('selectedSize');
                if (selSize) selSize.value = sizeOpt.dataset.size || '';
            });
        }
    } else {
        var sizeOptions = document.querySelectorAll('.size-options .size-option');
        sizeOptions.forEach(function(option) {
            option.addEventListener('click', function() {
                document.querySelectorAll('.size-options .size-option').forEach(function(o) { o.classList.remove('selected'); });
                option.classList.add('selected');
                var selSize = document.getElementById('selectedSize');
                if (selSize) selSize.value = option.dataset.size || '';
                updateColorOptions();
            });
        });
        var colorOpts = document.querySelectorAll('#colorOptions .color-option');
        colorOpts.forEach(function(option) {
            option.addEventListener('click', function() {
                if (option.dataset.available === 'true') {
                    colorOpts.forEach(function(o) { o.classList.remove('selected'); });
                    option.classList.add('selected');
                    var selColor = document.getElementById('selectedColor');
                    if (selColor) selColor.value = option.dataset.color || '';
                }
            });
        });
        updateColorOptions();
    }

    var cartForm = document.querySelector('form[action*="cart_add"]');
    if (cartForm) {
        cartForm.addEventListener('submit', function(e) {
            if (window.isJewellery) {
                return true;
            }
            if (useColorVariants) {
                var sizeVariantIdEl = document.getElementById('selectedSizeVariantId');
                var val = sizeVariantIdEl ? sizeVariantIdEl.value : '';
                if (!val || val === '') {
                    e.preventDefault();
                    alert('Please select a size');
                    return false;
                }
                return true;
            }
            var selectedSizeEl = document.getElementById('selectedSize');
            var selectedColorEl = document.getElementById('selectedColor');
            var selectedSize = selectedSizeEl ? selectedSizeEl.value : '';
            var selectedColor = selectedColorEl ? selectedColorEl.value : '';
            if (!selectedSize) {
                e.preventDefault();
                alert('Please select a size');
                return false;
            }
            var sizeData = (sizeColorStock && sizeColorStock[selectedSize]) || {};
            var colorKey = selectedColor || 'no_color';
            if (sizeData[colorKey] !== true) {
                e.preventDefault();
                alert('Selected variant is out of stock');
                return false;
            }
            return true;
        });
    }
});
