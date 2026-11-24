from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

User = get_user_model()

REGISTER_URL = reverse("user:register")
LOGIN_URL = reverse("user:login")
LOGOUT_URL = reverse("user:logout")
ME_URL = reverse("user:me")
USERS_LIST_URL = reverse("user:user-list")


class AuthTests(APITestCase):
    def setUp(self):
        self.user_data = {
            "email": "alex@example.com",
            "username": "alex",
            "password": "strongpassword123",
        }

    def test_register_user_success(self):
        res = self.client.post(REGISTER_URL, self.user_data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            User.objects.filter(
                email=self.user_data["email"]
            ).exists()
        )
        self.assertNotIn("password", res.data)

        user = User.objects.get(email=self.user_data["email"])
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_register_duplicate_email_fails(self):
        User.objects.create_user(**self.user_data)
        res = self.client.post(REGISTER_URL, self.user_data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_returns_token(self):
        User.objects.create_user(**self.user_data)
        res = self.client.post(
            LOGIN_URL,
            {
                "email": self.user_data["email"],
                "password": self.user_data["password"]
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("token", res.data)

    def test_logout_invalidates_token(self):
        user = User.objects.create_user(**self.user_data)
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        res = self.client.post(LOGOUT_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(user=user).exists())

        # Повторний запит із віддаленим токеном повинен повернути 401
        res_after = self.client.get(ME_URL)
        self.assertEqual(res_after.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileAndFollowTests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email="user1@example.com", username="alice", password="password123"
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com", username="bob", password="password123"
        )
        self.client.force_authenticate(user=self.user1)

    def test_retrieve_and_update_own_profile(self):
        res_get = self.client.get(ME_URL)
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["email"], self.user1.email)

        res_patch = self.client.patch(
            ME_URL,
            {"bio": "Python backend developer"}
        )
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        self.user1.refresh_from_db()
        self.assertEqual(self.user1.bio, "Python backend developer")

    def test_search_users(self):
        res = self.client.get(USERS_LIST_URL, {"search": "bob"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["username"], "bob")

    def test_follow_and_unfollow_user(self):
        follow_url = reverse("user:user-follow", args=[self.user2.id])
        unfollow_url = reverse("user:user-unfollow", args=[self.user2.id])

        # підписка
        res_follow = self.client.post(follow_url)
        self.assertEqual(res_follow.status_code, status.HTTP_200_OK)
        self.assertTrue(
            self.user1.following.filter(id=self.user2.id).exists()
        )

        # Повторна підписка заборонена
        res_duplicate = self.client.post(follow_url)
        self.assertEqual(
            res_duplicate.status_code, status.HTTP_400_BAD_REQUEST
        )

        # Перевірка списків following та followers
        res_following = self.client.get(reverse("user:user-following"))
        self.assertEqual(len(res_following.data), 1)

        # Відписка
        res_unfollow = self.client.post(unfollow_url)
        self.assertEqual(res_unfollow.status_code, status.HTTP_200_OK)
        self.assertFalse(
            self.user1.following.filter(id=self.user2.id).exists()
        )

    def test_cannot_follow_self(self):
        follow_self_url = reverse("user:user-follow", args=[self.user1.id])
        res = self.client.post(follow_self_url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
