from django.contrib.auth import get_user_model
from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
    extend_schema_view,
    OpenApiParameter
)
from rest_framework import generics, status, viewsets, filters
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from user.models import User
from user.serializers import (
    AuthTokenSerializer,
    UserRegisterSerializer, UserDetailSerializer, UserListSerializer,
)


class RegisterUserView(generics.CreateAPIView):
    serializer_class = UserRegisterSerializer
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["Auth"],
        summary="Register a new user",
        description="Register a new user with email and password.",
        responses={
            201: UserRegisterSerializer,
            400: OpenApiResponse(
                description="Validation error "
                            "(e.g. email already exists or weak password)."
            )
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LoginUserView(ObtainAuthToken):
    serializer_class = AuthTokenSerializer
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES

    @extend_schema(
        tags=["Auth"],
        summary="Obtain authentication token",
        description="Authenticates a user with email and "
                    "password and returns a DRF Token. "
                    "Use this token in the Authorization "
                    "header as: `Token <your_token>`.",
        responses={
            200: OpenApiResponse(
                description="Successful authentication",
                response={
                    "type": "object",
                    "properties": {
                        "token": {
                            "type": "string",
                            "example": "9944b09199c62bc..."
                        },
                        "user_id": {
                            "type": "integer",
                            "example": 1
                        },
                        "email": {
                            "type": "string",
                            "example": "user@example.com"
                        },
                    },
                },
            ),
            400: OpenApiResponse(description="Invalid credentials."),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            "token": token.key,
            "user_id": user.id,
            "email": user.email
        })


class LogoutUserView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Auth"],
        summary="Logout and invalidate token",
        description="Deletes the current user's authentication "
                    "token from the database, logging them out.",
        request=None,
        responses={
            200: OpenApiResponse(
                description="Successfully logged out",
                response={
                    "type": "object",
                    "properties": {
                        "detail": {
                            "type": "string",
                            "example": "Successfully logged out."
                        }
                    },
                },
            ),
            401: OpenApiResponse(
                description="Authentication credentials were not provided."
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        request.user.auth_token.delete()
        return Response(
            {"detail": "Successfully logged out."},
            status=status.HTTP_200_OK
        )


@extend_schema_view(
    get=extend_schema(
        tags=["Users & Profiles"],
        summary="Retrieve own profile",
        description="Returns detailed profile information for "
                    "the currently authenticated user.",
    ),
    put=extend_schema(
        tags=["Users & Profiles"],
        summary="Full update of own profile",
        description="Updates all writable fields of the authenticated "
                    "user's profile (including avatar upload).",
    ),
    patch=extend_schema(
        tags=["Users & Profiles"],
        summary="Partial update of own profile",
        description="Partially updates fields of the authenticated "
                    "user's profile (username, bio, avatar, etc.).",
    ),
    delete=extend_schema(
        tags=["Users & Profiles"],
        summary="Delete own account",
        description="Permanently deletes the authenticated user's account.",
    ),
)
class ManageUserView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserDetailSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user


@extend_schema_view(
    list=extend_schema(
        tags=["Users & Profiles"],
        summary="List and search users",
        description="Returns a list of all users. Supports searching "
                    "by username, email, first_name, or last_name.",
        parameters=[
            OpenApiParameter(
                name="search",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter users by username, "
                            "email, first name, or last name.",
            )
        ],
    ),
    retrieve=extend_schema(
        tags=["Users & Profiles"],
        summary="Retrieve user profile by ID",
        description="Returns detailed public profile of a specific user, "
                    "including follower counts and follow status.",
    ),
)
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = get_user_model().objects.all()
    permission_classes = (IsAuthenticated,)
    filter_backends = [filters.SearchFilter]
    search_fields = ["username", "email", "first_name", "last_name"]

    def get_serializer_class(self):
        if self.action in ("list", "following", "followers"):
            return UserListSerializer
        return UserDetailSerializer

    @extend_schema(
        tags=["Users & Profiles"],
        summary="Follow a user",
        description="Subscribes the authenticated user "
                    "to the user specified by `{id}`.",
        request=None,
        responses={
            200: OpenApiResponse(description="Successfully followed user."),
            400: OpenApiResponse(
                description="Cannot follow yourself or already "
                            "following this user."
            ),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="follow"
    )
    def follow(self, request, pk=None):
        target_user = self.get_object()
        if target_user == request.user:
            return Response(
                {"detail": "You cannot follow yourself."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.user.following.filter(id=target_user.id).exists():
            return Response(
                {"detail": "You are already following this user."},
                status=status.HTTP_400_BAD_REQUEST
            )

        request.user.following.add(target_user)
        return Response(
            {"detail": f"You are now following {target_user.email}."},
            status=status.HTTP_200_OK
        )

    @extend_schema(
        tags=["Users & Profiles"],
        summary="Unfollow a user",
        description="Unsubscribes the authenticated user "
                    "from the user specified by `{id}`.",
        request=None,
        responses={
            200: OpenApiResponse(description="Successfully unfollowed user."),
            400: OpenApiResponse(
                description="You are not following this user."
            ),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="unfollow"
    )
    def unfollow(self, request, pk=None):
        target_user = self.get_object()
        if not request.user.following.filter(id=target_user.id).exists():
            return Response(
                {"detail": "You are not following this user."},
                status=status.HTTP_400_BAD_REQUEST
            )
        request.user.following.remove(target_user)
        return Response(
            {"detail": f"You have unfollowed {target_user.email}."},
            status=status.HTTP_200_OK
        )

    @extend_schema(
        tags=["Users & Profiles"],
        summary="List following users",
        description="Returns the list of users that the currently "
                    "authenticated user is following.",
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="following"
    )
    def following(self, request, pk=None):
        queryset = request.user.following.all()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["Users & Profiles"],
        summary="List followers",
        description="Returns the list of users who follow "
                    "the currently authenticated user.",
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="followers"
    )
    def followers(self, request, pk=None):
        queryset = request.user.followers.all()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
