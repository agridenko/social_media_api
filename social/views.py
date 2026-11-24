import re

from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from social.models import Comment, Like, Post
from social.permissions import IsOwnerOrReadOnly
from social.serializers import CommentSerializer, PostDetailSerializer, PostSerializer
from social.tasks import publish_scheduled_post


@extend_schema_view(
    list=extend_schema(
        tags=["Posts"],
        summary="Retrieve posts feed",
        description="Returns published posts from the current "
                    "user and users they follow. "
                    "Supports filtering by `#hashtag` or `author` ID.",
        parameters=[
            OpenApiParameter(
                name="hashtag",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter posts containing a specific "
                            "hashtag (with or without `#`, e.g. `python`).",
            ),
            OpenApiParameter(
                name="author",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Filter posts by author ID.",
            ),
        ],
    ),
    create=extend_schema(
        tags=["Posts"],
        summary="Create a new post",
        description="Creates a new post with text content and "
                    "an optional image attachment.",
    ),
    retrieve=extend_schema(
        tags=["Posts"],
        summary="Retrieve post details",
        description="Returns detailed post info including all comments.",
    ),
    update=extend_schema(
        tags=["Posts"],
        summary="Full update of own post",
        description="Updates all fields of a post. "
                    "Allowed only for the post author.",
    ),
    partial_update=extend_schema(
        tags=["Posts"],
        summary="Partial update of own post",
        description="Partially updates a post. "
                    "Allowed only for the post author.",
    ),
    destroy=extend_schema(
        tags=["Posts"],
        summary="Delete own post",
        description="Deletes a post. Allowed only for the post author.",
    ),
)
class PostViewSet(viewsets.ModelViewSet):
    """CRUD для постів, стрічка підписок, фільтрація по хештегам і лайки."""
    permission_classes = (IsAuthenticated, IsOwnerOrReadOnly)

    def get_queryset(self):
        user = self.request.user
        # Показуємо лише опубліковані пости поточного користувача
        # та тих, на кого він підписаний
        following_ids = user.following.values_list("id", flat=True)
        queryset = (
            Post.objects.filter(is_published=True)
            .filter(Q(author=user) | Q(author_id__in=following_ids))
            .select_related("author")
            .prefetch_related("likes", "comments")
        )

        # Фільтрування по хештегу (?hashtag=django)
        hashtag = self.request.query_params.get("hashtag")
        if hashtag:
            clean_tag = hashtag.lstrip("#")
            escaped_tag = re.escape(clean_tag)
            queryset = queryset.filter(content__iregex=rf"#{escaped_tag}\b")

        # Фільтрування за автором (?author=2)
        author_id = self.request.query_params.get("author")
        if author_id:
            queryset = queryset.filter(author_id=author_id)

        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PostDetailSerializer
        return PostSerializer

    def perform_create(self, serializer):
        scheduled_at = serializer.validated_data.get("scheduled_at")
        if scheduled_at:
            post = serializer.save(
                author=self.request.user,
                is_published=False
            )
            publish_scheduled_post.apply_async(
                args=[post.id],
                eta=scheduled_at
            )
        else:
            serializer.save(author=self.request.user, is_published=True)

    @extend_schema(
        tags=["Posts"],
        summary="List own scheduled posts",
        description="Returns posts created by the current user "
                    "that are scheduled for future publication.",
    )
    @action(detail=False, methods=["get"], url_path="scheduled")
    def scheduled(self, request):
        queryset = Post.objects.filter(
            author=request.user,
            is_published=False
        ).select_related("author")
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["Likes & Comments"],
        summary="Like a post",
        description="Adds a like from the current user to the specified post.",
        request=None,
        responses={
            200: OpenApiResponse(description="Post liked successfully."),
            400: OpenApiResponse(
                description="You have already liked this post."
            ),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="like",
        permission_classes=[IsAuthenticated]
    )
    def like(self, request, pk=None):
        post = self.get_object()
        like, created = Like.objects.get_or_create(
            user=request.user,
            post=post
        )
        if not created:
            return Response(
                {"detail": "You have already liked this post."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Post liked."}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Likes & Comments"],
        summary="Unlike a post",
        description="Removes the current user's like from the specified post.",
        request=None,
        responses={
            200: OpenApiResponse(description="Post unliked successfully."),
            400: OpenApiResponse(description="You have not liked this post."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="unlike",
        permission_classes=[IsAuthenticated]
    )
    def unlike(self, request, pk=None):
        post = self.get_object()
        deleted_count, _ = Like.objects.filter(
            user=request.user,
            post=post
        ).delete()
        if deleted_count == 0:
            return Response(
                {"detail": "You have not liked this post."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Post unliked."}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Likes & Comments"],
        summary="List liked posts",
        description="Returns all published posts that the "
                    "currently authenticated user has liked.",
    )
    @action(detail=False, methods=["get"], url_path="liked")
    def liked(self, request):
        queryset = Post.objects.filter(
            likes__user=request.user,
            is_published=True
        ).select_related("author")
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@extend_schema_view(
    get=extend_schema(
        tags=["Likes & Comments"],
        summary="List comments on a post",
        description="Returns all comments belonging to the specified post.",
    ),
    post=extend_schema(
        tags=["Likes & Comments"],
        summary="Add a comment to a post",
        description="Creates a new comment under the specified post.",
    ),
)
class PostCommentListCreateView(generics.ListCreateAPIView):
    """Перегляд та створення коментарів до конкретної посади."""
    serializer_class = CommentSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Comment.objects.filter(
            post_id=self.kwargs["post_id"]
        ).select_related("user")

    def perform_create(self, serializer):
        post = get_object_or_404(
            Post,
            pk=self.kwargs["post_id"],
            is_published=True
        )
        serializer.save(user=self.request.user, post=post)


@extend_schema_view(
    get=extend_schema(
        tags=["Likes & Comments"],
        summary="Retrieve a comment",
    ),
    put=extend_schema(
        tags=["Likes & Comments"],
        summary="Update own comment",
    ),
    partial_update=extend_schema(
        tags=["Likes & Comments"],
        summary="Partial update of own comment",
    ),
    delete=extend_schema(
        tags=["Likes & Comments"],
        summary="Delete own comment",
    ),
)
class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Редагування та видалення конкретного коментаря (тільки автором)."""
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (IsAuthenticated, IsOwnerOrReadOnly)
