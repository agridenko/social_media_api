from django.urls import path, include
from rest_framework.routers import DefaultRouter

from user.views import (
    LoginUserView,
    LogoutUserView,
    RegisterUserView,
    ManageUserView,
    UserViewSet
)

app_name = "user"

router = DefaultRouter()
router.register("", UserViewSet, basename="user")

urlpatterns = [
    path("register/", RegisterUserView.as_view(), name="register"),
    path("login/", LoginUserView.as_view(), name="login"),
    path("logout/", LogoutUserView.as_view(), name="logout"),
    path("me/", ManageUserView.as_view(), name="me"),
    path("", include(router.urls))
]
