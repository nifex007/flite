from flite.users.utils import p2p_transfer
from os import stat
from django.urls import reverse
from django.forms.models import model_to_dict
from django.contrib.auth.hashers import check_password
from nose.tools import ok_, eq_
from rest_framework.test import APITestCase
from rest_framework import status
from faker import Faker
from ..models import User,UserProfile,Referral,Balance, Transaction
from .factories import UserFactory
from django.db.models import F

fake = Faker()


class TestUserListTestCase(APITestCase):
    """
    Tests /users list operations.
    """

    def setUp(self):
        self.url = reverse('signup-list')
        self.user_data = model_to_dict(UserFactory.build())

    def test_post_request_with_no_data_fails(self):
        response = self.client.post(self.url, {})
        eq_(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_request_with_valid_data_succeeds(self):
        response = self.client.post(self.url, self.user_data)
        eq_(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(pk=response.data.get('id'))
        eq_(user.username, self.user_data.get('username'))
        ok_(check_password(self.user_data.get('password'), user.password))

    def test_post_request_with_valid_data_succeeds_and_profile_is_created(self):
        response = self.client.post(self.url, self.user_data)
        eq_(response.status_code, status.HTTP_201_CREATED)

        eq_(UserProfile.objects.filter(user__username=self.user_data['username']).exists(),True)

    def test_post_request_with_valid_data_succeeds_referral_is_created_if_code_is_valid(self):
        
        referring_user = UserFactory()
        self.user_data.update({"referral_code":referring_user.userprofile.referral_code})
        response = self.client.post(self.url, self.user_data)
        eq_(response.status_code, status.HTTP_201_CREATED)

        eq_(Referral.objects.filter(referred__username=self.user_data['username'],owner__username=referring_user.username).exists(),True)


    def test_post_request_with_valid_data_succeeds_referral_is_not_created_if_code_is_invalid(self):
        
        self.user_data.update({"referral_code":"FAKECODE"})
        response = self.client.post(self.url, self.user_data)
        eq_(response.status_code, status.HTTP_400_BAD_REQUEST)
        
class TestUserDetailTestCase(APITestCase):
    """
    Tests /users detail operations.
    """

    def setUp(self):
        self.user = UserFactory()
        self.url = reverse('users-detail', kwargs={'pk': self.user.pk})
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token}')

    def test_get_request_returns_a_given_user(self):
        response = self.client.get(self.url)
        eq_(response.status_code, status.HTTP_200_OK)

    def test_put_request_updates_a_user(self):
        new_first_name = fake.first_name()
        payload = {'first_name': new_first_name}
        response = self.client.put(self.url, payload)
        eq_(response.status_code, status.HTTP_200_OK)

        user = User.objects.get(pk=self.user.id)
        eq_(user.first_name, new_first_name)

class TestTransactions(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token}')
    
    def tearDown(self):
        User.objects.all().delete()
        Transaction.objects.all().delete()
        Balance.objects.all().delete()

    def test_user_can_make_a_deposit(self):
        url = reverse('users-deposits', kwargs={'pk': self.user.pk})
        payload = {'amount': 3000.00}
        response = self.client.post(url, payload)
        b  = Balance.objects.filter(owner=self.user).first()
        eq_(b.book_balance, 3000.0)
        eq_(response.status_code, status.HTTP_200_OK)


    def test_user_can_make_a_withdrawal(self):
        # deposit 
        deposit_url = reverse('users-deposits', kwargs={'pk': self.user.pk})
        deposit_payload = {'amount': 6000}
        self.client.post(deposit_url, deposit_payload)
        
        balance_before = Balance.objects.get(owner=self.user)

        # withdrawal
        withdrawal_url = reverse('users-withdrawals', kwargs={'pk': self.user.pk})
        withdrawal_payload = {"amount": 700.00}

        response = self.client.post(withdrawal_url, withdrawal_payload)

        balance_after = Balance.objects.get(owner=self.user)

        eq_(response.status_code, status.HTTP_200_OK)
        eq_(response.json()['message'], 'Withdrawal Successful')
        not eq_(balance_before.book_balance, balance_before.book_balance)
        self.assertLess(balance_after.available_balance, balance_before.available_balance, )

    def test_user_with_insufficient_can_not_make_a_withdrawal(self):
        # deposit 
        deposit_url = reverse('users-deposits', kwargs={'pk': self.user.pk})
        deposit_payload = {'amount': 600}
        self.client.post(deposit_url, deposit_payload)
        
        balance_before = Balance.objects.get(owner=self.user)

        # withdrawal
        withdrawal_url = reverse('users-withdrawals', kwargs={'pk': self.user.pk})
        withdrawal_payload = {"amount": 700.00}

        response = self.client.post(withdrawal_url, withdrawal_payload)

        balance_after = Balance.objects.get(owner=self.user)

        eq_(response.status_code, status.HTTP_403_FORBIDDEN)
        eq_(response.json()['message'], 'Insufficient funds')
        eq_(balance_before.book_balance, balance_after.book_balance)

       
    def test_user_can_make_a_p2p_transfer(self):
        recipient_user = UserFactory()

        # fund account
        deposit_url = reverse('users-deposits', kwargs={'pk': self.user.pk})
        deposit_payload = {'amount': 600}
        self.client.post(deposit_url, deposit_payload)
        # account status before transfer
        sender = Balance.objects.get(owner=self.user)
        recipient = Balance.objects.get(owner=recipient_user)

        url = reverse('p2p_transfer', kwargs={'sender_account_id': sender.pk, 'recipient_account_id': recipient.pk})
        payload = {
            "amount" : 500.00
        }
        # accounts status after transfer 
        response = self.client.post(url, payload)
        response_message = response.json()['message']

        recipient_balance_after_transfer = Balance.objects.get(owner=recipient_user)
        eq_(response.status_code, status.HTTP_200_OK)
        eq_(response_message, 'Transfer successful')
        eq_(recipient_balance_after_transfer.book_balance, 500.00)

    def test_prevent_p2p_transfer_from_account_by_non_owner_of_account(self):

        recipient_user = UserFactory()

        # fund account
        deposit_url = reverse('users-deposits', kwargs={'pk': self.user.pk})
        deposit_payload = {'amount': 600}
        self.client.post(deposit_url, deposit_payload)
        # account status before transfer
        sender = Balance.objects.get(owner=self.user)
        recipient = Balance.objects.get(owner=recipient_user)

        # swapped sender with recipient to reproduce the case for sending from account that is not the user's

        url = reverse('p2p_transfer', kwargs={'sender_account_id': recipient.pk, 'recipient_account_id': sender.pk})
        payload = {
            "amount" : 500.00
        }
        # accounts status after transfer 
        response = self.client.post(url, payload)
        response_message = response.json()['detail']

        recipient_balance_after_transfer = Balance.objects.get(owner=recipient_user)
        eq_(response.status_code, status.HTTP_403_FORBIDDEN)
        eq_(response_message, 'You do not have permission to perform this action.')
        eq_(recipient_balance_after_transfer.book_balance, 0.00)


    def test_invalid_account_p2p_transfer(self):

        recipient_user = UserFactory()

        # fund account
        deposit_url = reverse('users-deposits', kwargs={'pk': self.user.pk})
        deposit_payload = {'amount': 600}
        self.client.post(deposit_url, deposit_payload)
        # account status before transfer
        sender = Balance.objects.get(owner=self.user)
        recipient = Balance.objects.get(owner=recipient_user)

        url = reverse('p2p_transfer', kwargs={'sender_account_id': self.user.pk, 'recipient_account_id': recipient.pk})
        payload = {
            "amount" : 500.00
        }
        # accounts status after transfer 
        response = self.client.post(url, payload)
        response_message = response.json()['detail']
        recipient_balance_after_transfer = Balance.objects.get(owner=recipient_user)
        eq_(response.status_code, status.HTTP_403_FORBIDDEN)
        eq_(response_message, 'Invalid Account')
        eq_(recipient_balance_after_transfer.book_balance, 0.00)


    def test_user_can_not_make_a_p2p_transfer_to_self(self):
        # get user's account
        b = Balance.objects.get(owner=self.user)
        url = reverse('p2p_transfer', kwargs={'sender_account_id': b.pk, 'recipient_account_id': b.pk})
        payload = {
            "amount" : 500.00
        }
        response = self.client.post(url, payload)
        eq_(response.status_code, status.HTTP_403_FORBIDDEN)
        eq_(response.json()['message'], 'You can not transfer to the same account')


    def test_user_can_fetch_all_transactions(self):
        user = self.user
        account = Balance.objects.get(owner=user)
        url = reverse('accounts-transactions', kwargs={'pk': account.pk})

        response = self.client.get(url)
        eq_(response.status_code, status.HTTP_200_OK)
        eq_(response.json()['message'], 'success')
        eq_(len(response.json()['results']), 0)

    def test_user_can_fetch_a_single_transaction(self):
       
        user = self.user
        recipient_user= UserFactory()
      
        # do transaction p2p transaction
        
        # fund account
        deposit_url = reverse('users-deposits', kwargs={'pk': user.pk})
        deposit_payload = {'amount': 600}
        self.client.post(deposit_url, deposit_payload)

        # account status before transfer
        sender_account= Balance.objects.get(owner=self.user)
        recipient_account = Balance.objects.get(owner=recipient_user)

        p2p_url = reverse('p2p_transfer', kwargs={'sender_account_id': sender_account.pk, 'recipient_account_id': recipient_account.pk})
        p2p_payload = {
            "amount" : 500.00
        }
        self.client.post(p2p_url, p2p_payload)


        transaction = Transaction.objects.get(owner=recipient_user)

        url = reverse('account_transaction', kwargs={'account_id': recipient_account.pk, 'transaction_id': transaction.reference})

        response = self.client.get(url)
        
        eq_(response.status_code, status.HTTP_200_OK)
        eq_(response.json()['message'], 'success')

