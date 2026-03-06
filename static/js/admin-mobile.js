/**
 * Admin Mobile - Filter bottom sheet & touch UX
 */
(function() {
    'use strict';

    function initFilterSheet() {
        var trigger = document.getElementById('filterTrigger');
        var overlay = document.getElementById('filterOverlay');
        var sheet = document.getElementById('filtersSheet');
        var closeBtn = document.getElementById('filterSheetClose');
        var clearBtn = document.getElementById('filterClear');

        if (!trigger || !sheet) return;

        function open() {
            sheet.classList.add('active');
            if (overlay) overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
        function close() {
            sheet.classList.remove('active');
            if (overlay) overlay.classList.remove('active');
            document.body.style.overflow = '';
        }

        trigger.addEventListener('click', open);
        if (closeBtn) closeBtn.addEventListener('click', close);
        if (overlay) overlay.addEventListener('click', close);

        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                var form = sheet.querySelector('form');
                if (form) {
                    form.reset();
                    form.submit();
                }
            });
        }
    }

    function initReportFilterSheet() {
        var trigger = document.getElementById('reportFilterTrigger');
        var overlay = document.getElementById('reportFilterOverlay');
        var sheet = document.getElementById('reportFiltersSheet');
        var closeBtn = document.getElementById('reportFilterSheetClose');

        if (!trigger || !sheet) return;

        function open() {
            sheet.classList.add('active');
            if (overlay) overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
        function close() {
            sheet.classList.remove('active');
            if (overlay) overlay.classList.remove('active');
            document.body.style.overflow = '';
        }

        trigger.addEventListener('click', open);
        if (closeBtn) closeBtn.addEventListener('click', close);
        if (overlay) overlay.addEventListener('click', close);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initFilterSheet();
            initReportFilterSheet();
        });
    } else {
        initFilterSheet();
        initReportFilterSheet();
    }
})();
