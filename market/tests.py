import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import Market, Outcome
from .services import place_bet, resolve_market


class MarketTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('alice', password='longpassword')
        self.b = User.objects.create_user('bob', password='longpassword')
        self.market = Market.objects.create(title='Test', kind='COUPLE', closes_at=timezone.now() + timedelta(days=1))
        self.yes = Outcome.objects.create(market=self.market, label='Yes')
        self.no = Outcome.objects.create(market=self.market, label='No')

    def test_signup_profile_and_token(self):
        self.assertEqual(self.a.profile.balance, Decimal('1000'))
        self.assertTrue(self.a.api_token.key)

    def test_parimutuel_payout(self):
        place_bet(self.a, self.yes, 100)
        place_bet(self.b, self.no, 300)
        resolve_market(self.market, self.yes)
        self.a.profile.refresh_from_db()
        self.b.profile.refresh_from_db()
        self.assertEqual(self.a.profile.balance, Decimal('1300'))
        self.assertEqual(self.b.profile.balance, Decimal('700'))

    def test_against_cannot_resolve_before_timeframe_ends(self):
        self.market.mode = Market.Mode.TIMEFRAME
        self.market.resolves_at = timezone.now() + timedelta(days=90)
        self.market.save(update_fields=['mode', 'resolves_at'])
        self.no.label = 'AGAINST'
        self.no.save(update_fields=['label'])
        with self.assertRaisesMessage(ValueError, 'observation window ends'):
            resolve_market(self.market, self.no)

    def test_api_registration_and_bet(self):
        response = self.client.post('/api/auth/register/', json.dumps({'username': 'charlie', 'password': 'longpassword'}), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        token = response.json()['token']
        response = self.client.post('/api/bets/', json.dumps({'outcome_id': self.yes.id, 'amount': 50}), content_type='application/json', HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['balance'], '950.00')

    def test_login_returns_working_token(self):
        response = self.client.post('/api/auth/login/', json.dumps({
            'username': 'alice', 'password': 'longpassword'
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        token = response.json()['token']
        me = self.client.get('/api/me/', HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()['user']['username'], 'alice')

    def test_market_list_returns_json(self):
        response = self.client.get('/api/markets/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/json')
        self.assertEqual(response.json()['markets'][0]['title'], 'Test')
        self.assertEqual(response.json()['markets'][0]['mode'], 'TIMEFRAME')


class FirstUserAdminTests(TestCase):
    def test_first_registered_user_becomes_admin(self):
        response = self.client.post('/api/auth/register/', json.dumps({
            'username': 'firstuser', 'password': 'longpassword'
        }), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['user']['is_admin'])
        self.assertTrue(User.objects.get(username='firstuser').is_staff)
