import re
from rest_framework import serializers
from social.models import Comment, Post
from django.utils import timezone


class CommentSerializer(serializers.ModelSerializer):
    author_email = serializers.ReadOnlyField(source="user.email")
    author_username = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = Comment
        fields = ("id", "post", "user", "author_email", "author_username", "content", "created_at", "updated_at")
        read_only_fields = ("id", "post", "user", "created_at", "updated_at")


class PostSerializer(serializers.ModelSerializer):
    author_email = serializers.ReadOnlyField(source="author.email")
    author_username = serializers.ReadOnlyField(source="author.username")
    likes_count = serializers.IntegerField(source="likes.count", read_only=True)
    comments_count = serializers.IntegerField(source="comments.count", read_only=True)
    is_liked = serializers.SerializerMethodField()
    hashtags = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "author",
            "author_email",
            "author_username",
            "content",
            "image",
            "hashtags",
            "likes_count",
            "comments_count",
            "is_liked",
            "is_published",
            "scheduled_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "author", "is_published", "created_at", "updated_at")

    def validate_scheduled_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError("Scheduled time must be in the future.")
        return value


    def get_is_liked(self, obj) -> bool:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def get_hashtags(self, obj) -> list[str]:
        return re.findall(r"#(\w+)", obj.content)


class PostDetailSerializer(PostSerializer):
    """Детальний перегляд посту відразу зі списком коментарів."""
    comments = CommentSerializer(many=True, read_only=True)

    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + ("comments",)
