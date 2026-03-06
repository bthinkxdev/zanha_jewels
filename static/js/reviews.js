// Product reviews - AJAX submission for verified buyers
(function () {
    "use strict";

    function getCookie(name) {
        // Reuse logic from main.js if available
        if (typeof document === "undefined") return "";
        var cookieValue = "";
        var cookies = document.cookie ? document.cookie.split(";") : [];
        for (var i = 0; i < cookies.length; i++) {
            var c = cookies[i].trim();
            if (c.indexOf(name + "=") === 0) {
                cookieValue = decodeURIComponent(c.substring(name.length + 1));
                break;
            }
        }
        return cookieValue;
    }

    document.addEventListener("DOMContentLoaded", function () {
        var form = document.getElementById("reviewForm");
        if (!form) return;

        var submitBtn = document.getElementById("reviewSubmitBtn");
        var starsContainer = document.getElementById("ratingStars");
        var ratingInput = document.getElementById("ratingValue");

        // Interactive star rating
        if (starsContainer && ratingInput) {
            var starButtons = Array.prototype.slice.call(
                starsContainer.querySelectorAll(".rating-star")
            );

            function setRating(value) {
                ratingInput.value = String(value || "");
                starButtons.forEach(function (btn) {
                    var v = parseInt(btn.getAttribute("data-value"), 10) || 0;
                    var selected = value && v <= value;
                    btn.classList.toggle("selected", selected);
                    btn.setAttribute("aria-checked", selected ? "true" : "false");
                });
            }

            starButtons.forEach(function (btn) {
                btn.addEventListener("click", function () {
                    var value = parseInt(btn.getAttribute("data-value"), 10) || 0;
                    if (!value) return;
                    setRating(value);
                });

                btn.addEventListener("keydown", function (e) {
                    var current = parseInt(ratingInput.value || "0", 10) || 0;
                    if (e.key === "ArrowRight" || e.key === "ArrowUp") {
                        e.preventDefault();
                        setRating(Math.min(5, current + 1 || 1));
                    } else if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
                        e.preventDefault();
                        setRating(Math.max(1, current - 1 || 1));
                    } else if (e.key === " " || e.key === "Enter") {
                        e.preventDefault();
                        var v = parseInt(btn.getAttribute("data-value"), 10) || 0;
                        if (!v) return;
                        setRating(v);
                    }
                });

                btn.addEventListener("mouseover", function () {
                    var hoverVal = parseInt(btn.getAttribute("data-value"), 10) || 0;
                    starButtons.forEach(function (b) {
                        var v = parseInt(b.getAttribute("data-value"), 10) || 0;
                        b.classList.toggle("hovered", v <= hoverVal);
                    });
                });
            });

            starsContainer.addEventListener("mouseleave", function () {
                var current = parseInt(ratingInput.value || "0", 10) || 0;
                starButtons.forEach(function (b) {
                    var v = parseInt(b.getAttribute("data-value"), 10) || 0;
                    b.classList.toggle("hovered", false);
                    var selected = current && v <= current;
                    b.classList.toggle("selected", selected);
                });
            });
        }

        form.addEventListener("submit", function (e) {
            e.preventDefault();

            if (ratingInput && !ratingInput.value) {
                alert("Please select a rating.");
                return;
            }

            var action = form.getAttribute("action");
            if (!action) {
                alert("Cannot submit review: missing endpoint.");
                return;
            }

            var formData = new FormData(form);

            if (submitBtn) {
                submitBtn.disabled = true;
            }

            fetch(action, {
                method: "POST",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: formData,
            })
                .then(function (res) {
                    return res
                        .json()
                        .then(function (data) {
                            return { ok: res.ok, status: res.status, data: data };
                        })
                        .catch(function () {
                            return { ok: res.ok, status: res.status, data: {} };
                        });
                })
                .then(function (result) {
                    if (!result) {
                        throw new Error("No response from server.");
                    }

                    var ok = result.ok;
                    var status = result.status;
                    var data = result.data || {};

                    if (status === 403 && data.login_required && data.login_url) {
                        window.location.href = data.login_url;
                        return;
                    }

                    if (!ok || !data.success) {
                        var msg =
                            data.error ||
                            "Could not submit your review. Please check your details and try again.";
                        alert(msg);
                        return;
                    }

                    // Success: reload page to show updated ratings & list
                    alert(data.message || "Thank you for your review!");
                    window.location.reload();
                })
                .catch(function () {
                    alert("Could not submit your review. Please try again.");
                })
                .finally(function () {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                    }
                });
        });
    });
})();

