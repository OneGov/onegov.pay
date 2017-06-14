var loadScript = function(url, callback, location) {
    var scriptTag = document.createElement('script');
    scriptTag.onload = callback;
    scriptTag.onreadystatechange = callback;
    scriptTag.src = url;

    (location || document.body).appendChild(scriptTag);
};

var getStripeAttributes = function(button) {
    var attributes = [];

    for (var i = 0; i < button.attributes.length; i++) {
        var attribute = button.attributes[i];

        if (attribute.name.startsWith('data-stripe')) {
            attributes.push(attribute);
        }
    }

    return attributes;
};

var findClosestParent = function(startElement, fn) {
    var parent = startElement.parentElement;
    if (parent) {
        return fn(parent) ? parent : findClosestParent(parent, fn);
    } else {
        return null;
    }
};

var handleSubmit = function(button) {
    var form = findClosestParent(button, function(el) {
        return el.tagName === 'FORM';
    });

    if (form !== null) {
        form.submit();
    }
};

var handleToken = function(token, button) {
    var target = document.getElementById(button.getAttribute('data-target-id'));
    target.setAttribute('value', token.id);

    switch (button.getAttribute('data-action')) {
        case 'submit':
            handleSubmit(button);
            break;
        default:
            break;
    }
};

var useApplePay = function() {
    if (window.location.hash === '#applepay') {
        return true;
    }

    try {
        return ApplePaySession && ApplePaySession.canMakePayments();
    } catch (e) {
        return false;
    }

};

var convertToApplePayButton = function(button) {
    button.innerHTML = '';
    button.className += ' apple-pay-button';
};

var newApplePayHandler = function(config) {
    return function(e) {
        e.preventDefault();

        var payment = {
            countryCode: config.country,
            currencyCode: config.currency,
            total: {
                label: config.description,
                amount: parseFloat(config.amount / 100).toFixed(2)
            }
        };

        Stripe.setPublishableKey(config.key);

        var session = Stripe.applePay.buildSession(payment, function(result, completion) {
            config.token(result.token);

            // XXX
            // we don't know yet if the payment will succeed, therefore we have
            // to do everything on the backend before showing the result
            // -> unfortunately this pretty much goes against the way we use
            // stripe, so for now we can't support apple pay
            completion(ApplePaySession.STATUS_SUCCESS);
        });

        session.begin();
    };
};

var newStripePaymentHandler = function(config) {
    return function(e) {
        e.preventDefault();
        StripeCheckout.configure(config).open();
    };
};

var setupCheckoutButton = function(button) {
    var config = {
        token: function(token) {
            handleToken(token, button);
        }
    };

    var attributes = getStripeAttributes(button);
    for (var i = 0; i < attributes.length; i++) {
        var attribute = attributes[i];
        config[attribute.name.replace('data-stripe-', '')] = attribute.value;
    }

    var onClick = null;

    if (useApplePay()) {
        convertToApplePayButton(button);
        onClick = newApplePayHandler(config);
    } else {
        onClick = newStripePaymentHandler(config);
    }

    button.addEventListener('click', onClick);

    // close checkout on page navigation
    window.addEventListener('popstate', function() {
        handler.close();
    });
};

var setupCheckout = function(buttons) {
    loadScript('https://js.stripe.com/v2/', function() {
        loadScript('https://checkout.stripe.com/checkout.js', function() {
            for (var i = 0; i < buttons.length; i++) {
                setupCheckoutButton(buttons[i]);
            }
        });
    });
};

document.addEventListener("DOMContentLoaded", function() {
    var buttons = document.querySelectorAll('.stripe-connect');

    if (buttons.length !== 0) {
        setupCheckout(buttons);
    }
});
