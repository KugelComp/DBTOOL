from django.contrib import admin
from .models import UserHierarchy

@admin.register(UserHierarchy)
class UserHierarchyAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "group_id",
        "is_admin",
        "is_superuser",
    )

    list_filter = ("role", "is_admin", "is_superuser")
    search_fields = ("user__username",)
