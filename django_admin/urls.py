from django.contrib import admin
from django.urls import path

# We mount this at /admin/ in FastAPI
# FastAPI strips the mount prefix, so /admin/ becomes /
# Django sees / and matches path('')
urlpatterns = [
    path('', admin.site.urls),
]
