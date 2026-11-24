from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Allows reading (GET, HEAD, OPTIONS)
    be any authorized koristuvachevi,
    Also change and delete (PUT, PATCH, DELETE) -
    only to the author of the object.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        # For Post, the username is stored in the
        # author field, for Comment – in the user field.
        owner = getattr(obj, "author", None) or getattr(obj, "user", None)
        return owner == request.user
