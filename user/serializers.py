from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"}
    )

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "email",
            "username",
            "password"
        )

    def create(self, validated_data):
        return get_user_model().objects.create_user(**validated_data)


class AuthTokenSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        style={"input_type": "password"},
        trim_whitespace=False,
        write_only=True
    )

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password
        )
        if not user:
            raise serializers.ValidationError(
                "Unable to authenticate with provided credentials",
                code="authentication"
            )

        attrs["user"] = user
        return attrs


class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "email",
            "username",
            "avatar"
        )


class UserDetailSerializer(serializers.ModelSerializer):
    followers_count = serializers.IntegerField(
        read_only=True,
        source="followers.count"
    )
    following_count = serializers.IntegerField(
        read_only=True,
        source="following.count"
    )
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "email",
            "username",
            "avatar",
            "bio",
            "followers_count",
            "following_count",
            "is_following"
        )
        read_only_fields = ("id", "email")

    def get_is_following(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return request.user.following.filter(id=obj.id).exists()
        return False
