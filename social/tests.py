from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from social.models import Comment, Post
from social.tasks import publish_scheduled_post

User = get_user_model()

POSTS_URL = reverse("social:post-list")


class PostAndFeedTests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email="u1@example.com",
            password="password123"
        )
        self.user2 = User.objects.create_user(
            email="u2@example.com",
            password="password123"
        )
        self.user3 = User.objects.create_user(
            email="u3@example.com",
            password="password123"
        )

        # user1 підписано тільки на user2
        self.user1.following.add(self.user2)
        self.client.force_authenticate(user=self.user1)

    def test_create_post_extracts_hashtags(self):
        payload = {"content": "Building API with #Django and #DRF!"}
        res = self.client.post(POSTS_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["hashtags"], ["Django", "DRF"])
        self.assertTrue(res.data["is_published"])

    def test_feed_shows_own_and_following_posts_only(self):
        post1 = Post.objects.create(author=self.user1, content="My post")
        post2 = Post.objects.create(author=self.user2, content="Friend post")
        post3 = Post.objects.create(author=self.user3, content="Stranger post")

        res = self.client.get(POSTS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        post_ids = [item["id"] for item in res.data]

        self.assertIn(post1.id, post_ids)
        self.assertIn(post2.id, post_ids)
        self.assertNotIn(post3.id, post_ids)

    def test_filter_posts_by_hashtag(self):
        Post.objects.create(
            author=self.user1,
            content="Learning #python today"
        )
        Post.objects.create(
            author=self.user1,
            content="Learning #docker today"
        )

        res = self.client.get(POSTS_URL, {"hashtag": "python"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertIn("#python", res.data[0]["content"])

    def test_owner_can_update_and_delete_own_post_but_not_others(self):
        own_post = Post.objects.create(
            author=self.user1,
            content="Own post"
        )
        other_post = Post.objects.create(
            author=self.user2,
            content="Other post"
        )

        # Чужий пост не можна оновити або видалити (403 Forbidden)
        other_url = reverse("social:post-detail", args=[other_post.id])
        self.assertEqual(
            self.client.patch(other_url, {"content": "Hacked"}).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.delete(other_url).status_code,
            status.HTTP_403_FORBIDDEN
        )

        # Свій пост можна оновити та видалити
        own_url = reverse("social:post-detail", args=[own_post.id])
        self.assertEqual(
            self.client.patch(own_url, {"content": "Updated"}).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.delete(own_url).status_code,
            status.HTTP_204_NO_CONTENT
        )


class LikesAndCommentsTests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email="u1@example.com",
            password="password123"
        )
        self.user2 = User.objects.create_user(
            email="u2@example.com",
            password="password123"
        )
        self.user1.following.add(self.user2)
        self.post = Post.objects.create(
            author=self.user2,
            content="Post to interact with"
        )
        self.client.force_authenticate(user=self.user1)

    def test_like_unlike_and_liked_list(self):
        like_url = reverse("social:post-like", args=[self.post.id])
        unlike_url = reverse("social:post-unlike", args=[self.post.id])
        liked_list_url = reverse("social:post-liked")

        # Лайк
        res_like = self.client.post(like_url)
        self.assertEqual(res_like.status_code, status.HTTP_200_OK)

        # Повторний лайк -> 400
        self.assertEqual(
            self.client.post(like_url).status_code,
            status.HTTP_400_BAD_REQUEST
        )

        # Список лайкнутих постів
        res_liked = self.client.get(liked_list_url)
        self.assertEqual(len(res_liked.data), 1)
        self.assertEqual(res_liked.data[0]["id"], self.post.id)

        # Анлайк
        res_unlike = self.client.post(unlike_url)
        self.assertEqual(res_unlike.status_code, status.HTTP_200_OK)

    def test_comments_crud_and_permissions(self):
        comments_url = reverse("social:post-comments", args=[self.post.id])

        # Створення коментаря
        res_create = self.client.post(comments_url, {"content": "Nice post!"})
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        comment_id = res_create.data["id"]

        # Коментар від іншого користувача
        other_comment = Comment.objects.create(
            user=self.user2, post=self.post, content="Author comment"
        )
        other_comment_url = reverse(
            "social:comment-detail",
            args=[other_comment.id]
        )
        self.assertEqual(
            self.client.delete(other_comment_url).status_code,
            status.HTTP_403_FORBIDDEN,
        )

        # Видалення свого коментаря
        own_comment_url = reverse("social:comment-detail", args=[comment_id])
        self.assertEqual(
            self.client.delete(own_comment_url).status_code,
            status.HTTP_204_NO_CONTENT
        )


class ScheduledPostTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="u1@example.com",
            password="password123"
        )
        self.client.force_authenticate(user=self.user)

    @patch("social.views.publish_scheduled_post.apply_async")
    def test_schedule_post_creation_and_task_execution(self, mock_apply_async):
        future_time = timezone.now() + timedelta(hours=1)
        res = self.client.post(
            POSTS_URL,
            {
                "content": "Future post",
                "scheduled_at": future_time.isoformat()
            },
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertFalse(res.data["is_published"])
        mock_apply_async.assert_called_once()

        post_id = res.data["id"]

        # Пост видно в /scheduled/, але не в загальній стрічці
        self.assertEqual(len(self.client.get(POSTS_URL).data), 0)
        self.assertEqual(
            len(self.client.get(
                reverse("social:post-scheduled")
            ).data), 1)

        # Викликаємо Celery-завдання безпосередньо та перевіряємо публікацію
        result_msg = publish_scheduled_post(post_id)
        self.assertIn("successfully published", result_msg)
        self.assertEqual(len(self.client.get(POSTS_URL).data), 1)

    def test_schedule_post_in_past_fails(self):
        past_time = timezone.now() - timedelta(minutes=10)
        res = self.client.post(
            POSTS_URL,
            {"content": "Past post", "scheduled_at": past_time.isoformat()},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
