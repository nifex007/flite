from rest_framework import permissions, status, exceptions
from rest_framework.response import Response
from flite.users.models import Balance


class IsUserOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):

        if request.method in permissions.SAFE_METHODS:
            return True

        return obj == request.user


class IsOwnAccount(permissions.BasePermission):

    def has_permission(self, request, view):
        url_values = view.kwargs
        account_id = url_values.get('pk', None)
        sender_account_id = url_values.get('sender_account_id', None)

        if account_id:
            request_account_id = account_id
        else:
            request_account_id = sender_account_id

        try:
            account = Balance.objects.get(id=request_account_id)
        except Balance.DoesNotExist:
            raise exceptions.PermissionDenied(detail='Invalid Account')

        return request.user == account.owner
