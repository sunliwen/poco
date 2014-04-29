from common.mongo_client import getMongoClient
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework import permissions
from rest_framework import exceptions

class PocoTokenAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        mongo_client = getMongoClient()
        authorization_line = request.META.get('Authorization')
        splitted_line = authorization_line.split()
        if not (len(splitted_line) == 2 and splitted_line[0] == "Token"):
            return None

        token = splitted_line[1]
        site = mongo_client.getSiteFromToken(site_token=token)
        if site is None:
            raise exceptions.AuthenticationFailed('No such user')
        
        return (site, None)


class TokenMatchAPIKeyPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        site = request.user
        if isinstance(site, AnonymousUser):
            return False
        else:
            if site["api_key"] == request.DATA["api_key"]:
                return True
            else:
                return False

