from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Дозволяє читання (GET, HEAD, OPTIONS) будь-якому авторизованому користувачеві,
    але зміна та видалення (PUT, PATCH, DELETE) - тільки автору об'єкта.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        # У Post власник зберігається у полі author, у Comment – у полі user
        owner = getattr(obj, "author", None) or getattr(obj, "user", None)
        return owner == request.user
