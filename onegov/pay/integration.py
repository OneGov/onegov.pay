from more.webassets import WebassetsApp
from onegov.core.orm import orm_cached
from onegov.core.utils import module_path, render_file
from onegov.pay import log
from onegov.pay import PaymentProvider
from onegov.pay.errors import CARD_ERRORS
from onegov.pay.models.payment import ManualPayment


class PayApp(WebassetsApp):
    """ Provides payment integration for
    :class:`onegov.core.framework.Framework` based applications.

    """

    def configure_payment_providers(self, **cfg):
        """ Configures the preconfigured parameters for payment providers.

        Takes one dictionary for each availble provider. Available providers
        can be found in the models/payment_providers folder. For example::

            payment_provider_defaults:
                stripe_connect:
                    client_id: foo
                    client_secret: bar

        Since multiple payment providers (even of the same type) may exist,
        and because some information stored on the payment providers need
        to be configured differently for each application_id (and possibly
        set up through OAuth) we only provide default parameters.

        When we create a new payment provider, these default values may be
        read by the payment provider.

        """

        self.payment_provider_defaults = cfg.get(
            'payment_provider_defaults', {})

    @orm_cached(policy='on-table-change:payment_providers')
    def default_payment_provider(self):
        return self.session().query(PaymentProvider)\
            .filter_by(default=True).first()


@PayApp.webasset_path()
def get_js_path():
    return 'assets/js'


@PayApp.webasset('pay')
def get_pay_assets():
    yield 'stripe.js'


@PayApp.path(path='/.well-known/apple-developer-merchantid-domain-association')
class ApplePayMerchantIdDomainAssociation(object):
    path = module_path(
        'onegov.pay', 'static/apple-developer-merchantid-domain-association')


@PayApp.view(model=ApplePayMerchantIdDomainAssociation, render=render_file)
def view_apple_pay_merchant_id_domain_association(self, app):
    return self.path


def process_payment(method, price, provider=None, token=None):
    """ Processes a payment using various methods, returning the processed
    payment or None.

    Available methods:

        'free': Payment may be done manually or by credit card
        'cc': Payment must be done by credit card
        'manual': Payment must be done manually

    """

    assert method in ('free', 'cc', 'manual') and price.amount > 0

    if method == 'free':
        method = token and 'cc' or 'manual'

    if method == 'manual':
        return ManualPayment(amount=price.amount, currency=price.currency)

    if method == 'cc' and token:
        try:
            return provider.charge(
                amount=price.amount,
                currency=price.currency,
                token=token
            )
        except CARD_ERRORS:
            log.exception(
                "Processing {} through {} with token {} failed".format(
                    price,
                    provider.title,
                    token
                )
            )

    return None
