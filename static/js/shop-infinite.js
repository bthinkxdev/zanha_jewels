/* Shop infinite scroll — loads 15 products per page via IntersectionObserver */
(function () {
  'use strict';

  var grid     = document.getElementById('shopProductGrid');
  var sentinel = document.getElementById('shopScrollSentinel');
  var spinner  = document.getElementById('shopLoadingSpinner');
  var endMsg   = document.getElementById('shopEndMessage');

  if (!grid || !sentinel) return;

  var isLoading = false;
  var hasNext   = sentinel.dataset.hasNext === 'true';
  var nextPage  = parseInt(sentinel.dataset.nextPage, 10) || null;
  var apiUrl    = sentinel.dataset.apiUrl;

  /* Nothing more to load on this page — hide sentinel immediately */
  if (!hasNext) {
    sentinel.hidden = true;
    return;
  }

  function getCsrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  function buildUrl(page) {
    /* Inherit current filter/sort params from the URL, override page number */
    var params = new URLSearchParams(window.location.search);
    params.set('page', page);
    return apiUrl + '?' + params.toString();
  }

  function loadMore() {
    if (isLoading || !hasNext || !nextPage) return;
    isLoading = true;
    if (spinner) spinner.hidden = false;

    fetch(buildUrl(nextPage), {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCsrf(),
      },
    })
      .then(function (res) {
        if (!res.ok) throw new Error('Network response: ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (data.html) {
          var tmp = document.createElement('div');
          tmp.innerHTML = data.html;
          /* Insert new cards before the sentinel so it stays at the bottom */
          while (tmp.firstChild) {
            grid.insertBefore(tmp.firstChild, sentinel);
          }
        }

        hasNext  = !!data.has_next;
        nextPage = data.next_page || null;

        if (!hasNext) {
          sentinel.hidden = true;
          if (endMsg) endMsg.hidden = false;
        }
      })
      .catch(function (err) {
        console.error('[shop-infinite] fetch error:', err);
      })
      .finally(function () {
        isLoading = false;
        if (spinner) spinner.hidden = true;
      });
  }

  /* Trigger fetch 300 px before the sentinel enters the viewport */
  var observer = new IntersectionObserver(
    function (entries) {
      if (entries[0].isIntersecting) {
        loadMore();
      }
    },
    { rootMargin: '0px 0px 300px 0px' }
  );

  observer.observe(sentinel);
})();
