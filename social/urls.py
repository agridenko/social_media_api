from django.urls import include, path
from rest_framework.routers import DefaultRouter

from social.views import (
    CommentDetailView,
    PostCommentListCreateView,
    PostViewSet
)

app_name = "social"

router = DefaultRouter()
router.register("posts", PostViewSet, basename="post")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "posts/<int:post_id>/comments/",
        PostCommentListCreateView.as_view(),
        name="post-comments"
    ),
    path(
        "comments/<int:pk>/",
        CommentDetailView.as_view(),
        name="comment-detail"
    ),
]
