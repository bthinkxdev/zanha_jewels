/**
 * Admin Reports: AJAX filtering, column sort, export buttons.
 * Expects window.ReportConfig = { reportType, apiUrl, exportCsvUrl, exportXlsxUrl }.
 */
(function() {
    'use strict';

    var config = window.ReportConfig || {};
    var reportType = config.reportType;
    var apiUrl = config.apiUrl;
    var exportCsvUrl = config.exportCsvUrl;
    var exportXlsxUrl = config.exportXlsxUrl;

    if (!reportType) return;

    var form = document.getElementById('report-filter-form');
    var tableWrap = document.querySelector('.report-table-wrap');
    var tbody = tableWrap && tableWrap.querySelector('table.report-table tbody');
    var paginationEl = document.getElementById('reportPagination');
    var summaryEl = document.getElementById('reportSummary');

    function getFormParams(extra) {
        var params = {};
        if (form) {
            var fd = new FormData(form);
            fd.forEach(function(v, k) { params[k] = v; });
        }
        if (extra) {
            for (var key in extra) params[key] = extra[key];
        }
        return params;
    }

    function paramsToQuery(params) {
        return Object.keys(params).filter(function(k) { return params[k] !== '' && params[k] != null; })
            .map(function(k) { return encodeURIComponent(k) + '=' + encodeURIComponent(params[k]); }).join('&');
    }

    function updateExportLinks() {
        var q = paramsToQuery(getFormParams());
        var suffix = q ? '?' + q : '';
        var csvBtn = document.getElementById('reportExportCsv');
        var xlsxBtn = document.getElementById('reportExportXlsx');
        if (csvBtn && exportCsvUrl) csvBtn.href = exportCsvUrl + (exportCsvUrl.indexOf('?') !== -1 ? '&' : '?') + q;
        if (xlsxBtn && exportXlsxUrl) xlsxBtn.href = exportXlsxUrl + (exportXlsxUrl.indexOf('?') !== -1 ? '&' : '?') + q;
    }

    function setLoading(loading) {
        if (tableWrap) tableWrap.classList.toggle('report-loading', !!loading);
    }

    function updateSummary(data) {
        if (!data || !data.summary || !summaryEl) return;
        var s = data.summary;
        var totalOrders = summaryEl.querySelector('#summaryTotalOrders');
        var totalRevenue = summaryEl.querySelector('#summaryTotalRevenue');
        var avgOrder = summaryEl.querySelector('#summaryAvgOrder');
        var topProduct = summaryEl.querySelector('#summaryTopProduct');
        if (totalOrders) totalOrders.textContent = s.total_orders;
        if (totalRevenue) totalRevenue.textContent = '₹' + (parseFloat(s.total_revenue) || 0).toFixed(0);
        if (avgOrder) avgOrder.textContent = '₹' + (parseFloat(s.avg_order_value) || 0).toFixed(0);
        if (topProduct) topProduct.textContent = s.top_product_name || '—';
    }

    function updatePagination(p) {
        if (!paginationEl || !p) return;
        var html = '';
        if (p.has_previous) {
            var prevParams = getFormParams({ page: 1 });
            var prevPageParams = getFormParams({ page: p.page - 1 });
            html += '<a href="?' + paramsToQuery(prevParams) + '" data-page="1">First</a> ';
            html += '<a href="?' + paramsToQuery(prevPageParams) + '" data-page="' + (p.page - 1) + '">Previous</a> ';
        }
        html += '<span class="current">Page ' + p.page + ' of ' + p.num_pages + '</span>';
        if (p.has_next) {
            var nextParams = getFormParams({ page: p.page + 1 });
            var lastParams = getFormParams({ page: p.num_pages });
            html += ' <a href="?' + paramsToQuery(nextParams) + '" data-page="' + (p.page + 1) + '">Next</a>';
            html += ' <a href="?' + paramsToQuery(lastParams) + '" data-page="' + p.num_pages + '">Last</a>';
        }
        paginationEl.innerHTML = html;
    }

    function fetchReport() {
        if (!apiUrl) return;
        var params = getFormParams();
        var url = apiUrl + (apiUrl.indexOf('?') !== -1 ? '&' : '?') + paramsToQuery(params);
        setLoading(true);
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' } })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                setLoading(false);
                if (data.error) return;
                if (tableWrap && tbody && data.html && typeof data.html === 'string') {
                    var tmp = document.createElement('div');
                    tmp.innerHTML = '<table>' + data.html + '</table>';
                    var newBody = tmp.querySelector('tbody');
                    if (newBody && tbody.parentNode) {
                        var parent = tbody.parentNode;
                        parent.replaceChild(newBody, tbody);
                        tbody = parent.querySelector('tbody');
                    }
                }
                updateSummary(data);
                if (data.pagination) updatePagination(data.pagination);
                updateExportLinks();
            })
            .catch(function() { setLoading(false); });
    }

    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            var sortInput = document.getElementById('reportSortInput');
            if (sortInput) sortInput.value = sortInput.value || '-created_at';
            fetchReport();
        });
    }

    document.getElementById('reportResetFilters') && document.getElementById('reportResetFilters').addEventListener('click', function() {
        if (form) form.reset();
        var sortInput = document.getElementById('reportSortInput');
        if (sortInput) sortInput.value = reportType === 'products' ? '-units_sold' : (reportType === 'customers' ? '-total_spent' : '-created_at');
        window.location.href = window.location.pathname;
    });

    document.querySelectorAll('.report-sort').forEach(function(a) {
        a.addEventListener('click', function(e) {
            e.preventDefault();
            var sort = this.getAttribute('data-sort');
            var sortInput = document.getElementById('reportSortInput');
            if (sortInput) sortInput.value = sort;
            if (apiUrl) fetchReport();
            else if (form) { form.submit(); }
        });
    });

    document.querySelector('#date_preset') && document.querySelector('#date_preset').addEventListener('change', function() {
        var v = this.value;
        var customFrom = document.getElementById('customDates');
        var customTo = document.getElementById('customDatesTo');
        if (customFrom) customFrom.style.display = v === 'custom' ? '' : 'none';
        if (customTo) customTo.style.display = v === 'custom' ? '' : 'none';
    });

    updateExportLinks();
})();
