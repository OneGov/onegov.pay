import json
import pycurl
import stripe

from contextlib import contextmanager
from io import BytesIO
from onegov.pay.models.payment_provider import PaymentProvider
from onegov.core.orm.mixins import meta_property


@contextmanager
def stripe_api_key(key):
    old_key = stripe.api_key
    stripe.api_key = key
    yield
    stripe.api_key = old_key


class StripeConnect(PaymentProvider):

    __mapper_args__ = {'polymorphic_identity': 'stripe_connect'}

    #: The Stripe Connect client id
    client_id = meta_property('client_id')

    #: The API key of the connect user
    client_secret = meta_property('client_secret')

    #: The oauth_redirect gateway in use (see seantis/oauth_redirect on github)
    oauth_gateway = meta_property('oauth_gateway')

    #: The auth code required by oauth_redirect
    oauth_gateway_auth = meta_property('oauth_gateway_auth')

    #: The oauth_redirect secret that should be used
    oauth_gateway_secret = meta_property('oauth_gateway_secret')

    #: The authorization code provided by OAuth
    authorization_code = meta_property('authorization_code')

    #: The public stripe key
    publishable_key = meta_property('publishable_key')

    #: The stripe user id as confirmed by OAuth
    user_id = meta_property('user_id')

    #: The refresh token provided by OAuth
    refresh_token = meta_property('refresh_token')

    #: The access token provieded by OAuth
    access_token = meta_property('access_token')

    @property
    def title(self):
        return 'Stripe Connect'

    @property
    def identity(self):
        return self.user_id

    def params(self, **p):
        assert self.client_id and self.client_secret

        p.setdefault('client_id', self.client_id)
        p.setdefault('client_secret', self.access_token or self.client_secret)

        return p

    def oauth_url(self, redirect_uri, state=None, user_fields=None):
        """ Generates an oauth url to be shown in the browser. """

        return stripe.OAuth.authorize_url(
            **self.params(
                scope='read_write',
                redirect_uri=redirect_uri,
                stripe_user=user_fields,
                state=state
            )
        )

    def prepare_oauth_request(self, redirect_uri, success_url, error_url,
                              user_fields=None):
        """ Registers the oauth request with the oauth_gateway and returns
        an url that is ready to be used for the complete oauth request.

        """
        register = '{}/register/{}'.format(
            self.oauth_gateway,
            self.oauth_gateway_auth)

        payload = {
            'url': redirect_uri,
            'secret': self.oauth_gateway_secret,
            'method': 'GET',
            'success_url': success_url,
            'error_url': error_url
        }

        body = BytesIO()

        c = pycurl.Curl()
        c.setopt(c.URL, register)
        c.setopt(c.POST, 1)
        c.setopt(pycurl.POSTFIELDS, json.dumps(payload))
        c.setopt(pycurl.WRITEFUNCTION, body.write)
        c.perform()

        status_code = c.getinfo(pycurl.RESPONSE_CODE)
        c.close()

        assert status_code == 200

        body.seek(0)
        token = json.loads(body.read().decode('utf-8'))['token']

        return self.oauth_url(
            redirect_uri='{}/redirect'.format(self.oauth_gateway),
            state=token,
            user_fields=user_fields
        )

    def process_oauth_response(self, request_params):
        """ Takes the parameters of an incoming oauth request and stores
        them on the payment provider if successful.

        """

        if 'error' in request_params:
            raise RuntimeError("Stripe OAuth request failed ({}: {})".format(
                request_params['error'], request_params['error_description']
            ))

        assert request_params['oauth_redirect_secret'] \
            == self.oauth_gateway_secret

        self.authorization_code = request_params['code']

        # this is one of the many places where we cannot provide the api
        # key per request, and have to do it globally instead
        with stripe_api_key(self.client_secret):
            token = stripe.OAuth.token(
                **self.params(
                    grant_type='authorization_code',
                    code=self.authorization_code,
                )
            )

        assert token['scope'] == 'read_write'

        self.publishable_key = token['stripe_publishable_key']
        self.user_id = token['stripe_user_id']
        self.refresh_token = token['refresh_token']
        self.access_token = token['access_token']