/**
 * Checkout Page JavaScript
 * - Address selection, payment method, form interactions
 * - Dynamic button text: "Place Order" (COD) / "Pay & Place Order" (Razorpay)
 * - Razorpay inline: create order -> open popup -> verify -> redirect success
 */

document.addEventListener('DOMContentLoaded', function() {
    initAddressSelection();
    initPaymentSelection();
    initPaymentButtonText();
    initAddressToggle();
    initCheckoutRemoveItems();
    initCheckoutSubmit();
});

function initCheckoutSubmit() {
    var form = document.getElementById('checkoutForm');
    var placeOrderBtn = document.getElementById('placeOrderBtn');
    if (!form || !placeOrderBtn) return;

    form.addEventListener('submit', function(e) {
        syncAddressToHidden();
        syncPaymentToHidden();

        var payment = getSelectedPaymentMethod();
        if (payment === 'razorpay') {
            e.preventDefault();
            handleRazorpaySubmit();
            return;
        }
        // COD: allow default form submit; disable button to prevent double submit
        placeOrderBtn.disabled = true;
        var btnText = document.getElementById('placeOrderBtnText');
        if (btnText) btnText.textContent = 'Placing Order…';
    });
}

function getSelectedPaymentMethod() {
    var radio = document.querySelector('input[name="payment_method"]:checked');
    return radio ? radio.value : 'cod';
}

function syncPaymentToHidden() {
    var payment = getSelectedPaymentMethod();
    var hidden = document.getElementById('id_payment');
    if (hidden) hidden.value = payment;
}

function syncAddressToHidden() {
    var form = document.getElementById('checkoutForm');
    if (!form) return;
    var addr = form.querySelector('input[name="address_selection"]:checked');
    var sel = form.querySelector('input[name="selected_address"]');
    var useNew = form.querySelector('input[name="use_new_address"]');
    if (addr && sel) {
        sel.value = addr.value;
        if (useNew) useNew.value = '';
    } else if (useNew) {
        useNew.value = 'true';
    }
}

function handleRazorpaySubmit() {
    var form = document.getElementById('checkoutForm');
    var btn = document.getElementById('placeOrderBtn');
    var btnText = document.getElementById('placeOrderBtnText');
    var errDiv = document.getElementById('checkoutErrorMessage');
    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!form || !btn || !csrfToken) return;

    syncAddressToHidden();
    syncPaymentToHidden();

    btn.disabled = true;
    if (btnText) btnText.textContent = 'Loading…';
    if (errDiv) {
        errDiv.style.display = 'none';
        errDiv.textContent = '';
    }

    var formData = new FormData(form);
    formData.set('payment', 'razorpay');

    fetch(form.getAttribute('data-razorpay-create-url') || '/checkout/create-razorpay-order/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken.value,
            'Accept': 'application/json',
        },
        body: formData,
    })
    .then(function(res) { return res.json().then(function(data) { return { ok: res.ok, data: data }; }); })
    .then(function(result) {
        if (result.ok && result.data.status === 'success') {
            openRazorpayPopup(result.data);
        } else {
            showCheckoutError(result.data.message || 'Could not create order. Please try again.');
            reenablePlaceOrderButton();
        }
    })
    .catch(function() {
        showCheckoutError('Network error. Please try again.');
        reenablePlaceOrderButton();
    });
}

function showCheckoutError(message) {
    var errDiv = document.getElementById('checkoutErrorMessage');
    if (errDiv) {
        errDiv.textContent = message;
        errDiv.style.display = 'block';
        errDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function reenablePlaceOrderButton() {
    var btn = document.getElementById('placeOrderBtn');
    var btnText = document.getElementById('placeOrderBtnText');
    if (btn) btn.disabled = false;
    if (btnText) btnText.textContent = getSelectedPaymentMethod() === 'razorpay' ? 'Pay & Place Order' : 'Place Order';
}

function openRazorpayPopup(data) {
    var btn = document.getElementById('placeOrderBtn');
    var btnText = document.getElementById('placeOrderBtnText');
    if (btnText) btnText.textContent = 'Pay & Place Order';

    if (typeof Razorpay === 'undefined') {
        showCheckoutError('Payment script failed to load. Please refresh and try again.');
        reenablePlaceOrderButton();
        return;
    }

    var verifyUrl = (typeof window.STORE_RAZORPAY_VERIFY_URL !== 'undefined')
        ? window.STORE_RAZORPAY_VERIFY_URL
        : '/payment/razorpay/verify/';
    var cancelUrl = (typeof window.STORE_RAZORPAY_CANCEL_URL !== 'undefined')
        ? window.STORE_RAZORPAY_CANCEL_URL
        : '/payment/razorpay/cancel/';
    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    var csrf = csrfToken ? csrfToken.value : '';

    var options = {
        key: data.razorpay_key_id,
        amount: data.amount,
        currency: 'INR',
        order_id: data.razorpay_order_id,
        name: 'Hello Gads',
        description: 'Order #' + data.order_number,
        prefill: {
            name: data.customer_name || '',
            email: data.customer_email || '',
            contact: data.customer_phone || '',
        },
        handler: function(response) {
            verifyPayment(response, data.razorpay_order_id, verifyUrl, csrf, data.success_url);
        },
        modal: {
            ondismiss: function() {
                cancelPayment(data.order_number, cancelUrl, csrf);
                reenablePlaceOrderButton();
            },
        },
    };

    var rzp = new Razorpay(options);
    rzp.open();
    reenablePlaceOrderButton();
}

function verifyPayment(response, razorpayOrderId, verifyUrl, csrf, successUrl) {
    var btn = document.getElementById('placeOrderBtn');
    var btnText = document.getElementById('placeOrderBtnText');
    if (btn) btn.disabled = true;
    if (btnText) btnText.textContent = 'Verifying…';

    fetch(verifyUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf,
            'Accept': 'application/json',
        },
        body: JSON.stringify({
            razorpay_order_id: razorpayOrderId,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature,
        }),
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
        if (data.status === 'success' && (data.redirect || data.order_number)) {
            window.location.href = data.redirect || ('/orders/' + data.order_number + '/');
        } else {
            showCheckoutError(data.message || 'Payment verification failed.');
            reenablePlaceOrderButton();
        }
    })
    .catch(function() {
        showCheckoutError('Verification failed. Please contact support if amount was deducted.');
        reenablePlaceOrderButton();
    });
}

function cancelPayment(orderNumber, cancelUrl, csrf) {
    fetch(cancelUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf,
        },
        body: JSON.stringify({ order_number: orderNumber }),
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
        if (data.redirect) {
            window.location.href = data.redirect;
        }
    })
    .catch(function() {
        window.location.href = '/cart/';
    });
}

// Order summary: remove item (x) button – confirm before submit
function initCheckoutRemoveItems() {
    document.querySelectorAll('.checkout-remove-form').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            var msg = form.getAttribute('data-confirm');
            if (msg && !window.confirm(msg)) {
                e.preventDefault();
            }
        });
    });
}

// Address Selection
function initAddressSelection() {
    const addressRadios = document.querySelectorAll('input[name="address_selection"]');
    const selectedAddressInput = document.getElementById('id_selected_address');
    const useNewAddressInput = document.getElementById('id_use_new_address');

    if (!addressRadios.length) return;

    addressRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            document.querySelectorAll('.address-card.selectable').forEach(card => {
                card.classList.remove('selected');
            });
            this.closest('.address-card').classList.add('selected');
            if (selectedAddressInput) selectedAddressInput.value = this.value;
            if (useNewAddressInput) useNewAddressInput.value = 'false';
        });
    });
}

// Payment Method Selection + dynamic button text
function initPaymentSelection() {
    var paymentRadios = document.querySelectorAll('input[name="payment_method"]');
    var paymentHidden = document.getElementById('id_payment');

    paymentRadios.forEach(function(radio) {
        if (radio.checked && paymentHidden) paymentHidden.value = radio.value;
        radio.addEventListener('change', function() {
            document.querySelectorAll('.payment-option').forEach(function(opt) {
                opt.classList.remove('selected');
            });
            this.closest('.payment-option').classList.add('selected');
            if (paymentHidden) paymentHidden.value = this.value;
            updatePlaceOrderButtonText();
        });
    });

    var checked = document.querySelector('input[name="payment_method"]:checked');
    if (!checked && paymentRadios.length) {
        paymentRadios[0].checked = true;
        paymentRadios[0].closest('.payment-option').classList.add('selected');
        if (paymentHidden) paymentHidden.value = 'cod';
    }
    updatePlaceOrderButtonText();
}

function initPaymentButtonText() {
    updatePlaceOrderButtonText();
}

function updatePlaceOrderButtonText() {
    var btnText = document.getElementById('placeOrderBtnText');
    if (!btnText) return;
    var payment = getSelectedPaymentMethod();
    btnText.textContent = payment === 'razorpay' ? 'Pay & Place Order' : 'Place Order';
}

// Toggle between saved addresses and new address form
function initAddressToggle() {
    const addNewBtn = document.getElementById('addNewAddressBtn');
    const cancelNewBtn = document.getElementById('cancelNewAddressBtn');
    const savedAddressesSection = document.getElementById('savedAddresses');
    const newAddressSection = document.getElementById('newAddressSection');
    const selectedAddressInput = document.getElementById('id_selected_address');
    const useNewAddressInput = document.getElementById('id_use_new_address');

    if (addNewBtn) {
        addNewBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (savedAddressesSection) savedAddressesSection.style.display = 'none';
            if (newAddressSection) newAddressSection.style.display = 'block';
            if (selectedAddressInput) selectedAddressInput.value = '';
            if (useNewAddressInput) useNewAddressInput.value = 'true';
            document.querySelectorAll('input[name="address_selection"]').forEach(r => { r.checked = false; });
            document.querySelectorAll('.address-card.selectable').forEach(c => c.classList.remove('selected'));
            if (newAddressSection) newAddressSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }

    if (cancelNewBtn) {
        cancelNewBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (savedAddressesSection) savedAddressesSection.style.display = 'grid';
            if (newAddressSection) newAddressSection.style.display = 'none';
            var defaultRadio = document.querySelector('input[name="address_selection"]:checked') ||
                document.querySelector('input[name="address_selection"]');
            if (defaultRadio) {
                defaultRadio.checked = true;
                defaultRadio.closest('.address-card').classList.add('selected');
                if (selectedAddressInput) selectedAddressInput.value = defaultRadio.value;
            }
            if (useNewAddressInput) useNewAddressInput.value = 'false';
            clearNewAddressForm();
            if (savedAddressesSection) savedAddressesSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }
}

function clearNewAddressForm() {
    var form = document.getElementById('checkoutForm');
    if (!form) return;
    ['full_name', 'phone', 'address_line', 'city', 'state', 'pincode', 'email'].forEach(function(name) {
        var field = form.querySelector('[name="' + name + '"]');
        if (field) field.value = '';
    });
    form.querySelectorAll('.form-error').forEach(function(el) { el.textContent = ''; });
}
