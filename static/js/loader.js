/**
 * ============================================================================
 * GLOBAL PAGE LOADER - FIXED VERSION
 * ============================================================================
 * 
 * Purpose:
 * - Shows loading overlay during page navigation (link clicks, form submissions)
 * - Properly handles browser history navigation (back/forward buttons)
 * - Handles bfcache page restoration
 * 
 * FIXED ISSUES:
 * ❌ REMOVED: Static setTimeout delays
 * ❌ REMOVED: window.onbeforeunload triggers
 * ❌ REMOVED: Any logic that blocks navigation
 * ✅ ADDED: popstate event handler (back/forward navigation)
 * ✅ ADDED: pageshow event handler (bfcache restoration)
 * ✅ ADDED: DOMContentLoaded event handler (early hide)
 * REMOVED: Failsafe timer (loader must hide only on response/navigation, not on fixed delay)
 * 
 * Usage:
 * - Loader shows automatically on internal link clicks and form submissions
 * - For AJAX calls, use: window.pageLoader.show() / window.pageLoader.hide()
 * 
 * Example AJAX usage:
 * 
 *   window.pageLoader.show();
 *   fetch('/api/endpoint')
 *     .then(response => response.json())
 *     .then(data => {
 *       // handle data
 *     })
 *     .catch(error => {
 *       // handle error
 *     })
 *     .finally(() => {
 *       window.pageLoader.hide();
 *     });
 * 
 * ============================================================================
 */
(function () {
    var loaderElement = null;

    // Helper: Get loader element
    function getLoader() {
        if (!loaderElement) {
            loaderElement = document.getElementById('page-loader');
        }
        return loaderElement;
    }

    // Helper: Show loader (no static delay; hides only on DOMContentLoaded/load of response page)
    function showLoader() {
        var loader = getLoader();
        if (loader) {
            loader.classList.remove('hidden');
        }
    }

    // Helper: Hide loader
    function hideLoader() {
        var loader = getLoader();
        if (loader) {
            loader.classList.add('hidden');
        }
    }

    // ===== STEP 4: Hide loader on DOMContentLoaded =====
    document.addEventListener('DOMContentLoaded', function () {
        hideLoader();
    });

    // ===== STEP 4: Hide loader on window load =====
    window.addEventListener('load', function () {
        hideLoader();
    });

    // ===== STEP 3: Handle back/forward navigation (popstate) =====
    window.addEventListener('popstate', function () {
        hideLoader();
    });

    // ===== STEP 3: Handle page restoration from bfcache (pageshow) =====
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
            // Page was restored from bfcache (back/forward button)
            hideLoader();
        }
    });

    // ===== STEP 2: Show loader on form submission =====
    document.addEventListener('submit', function (e) {
        var form = e.target;
        // Skip AJAX forms or forms with data-no-loader attribute
        if (form.dataset.noLoader) return;
        showLoader();
    });

    // ===== STEP 2: Show loader on internal link navigation =====
    document.addEventListener('click', function (e) {
        var link = e.target.closest('a');
        if (!link) return;
        
        var href = link.getAttribute('href');
        
        // Skip if:
        // - No href
        // - Hash links (same page)
        // - JavaScript links
        // - External links (target="_blank")
        // - Has data-no-loader attribute
        if (!href || 
            href.startsWith('#') || 
            href.startsWith('javascript:') ||
            link.target === '_blank' || 
            link.dataset.noLoader) {
            return;
        }
        
        // Show loader for internal navigation
        showLoader();
    });

    // ===== Expose global functions for AJAX handling =====
    window.pageLoader = {
        show: showLoader,
        hide: hideLoader
    };
})();
