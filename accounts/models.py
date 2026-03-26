from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Group(models.Model):
    """
    Logical grouping (DB team, Ops team, etc.)
    """
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class UserHierarchy(models.Model):

    ROLE_CHOICES = [
        ("USER", "User"),
        ("ADMIN", "Admin"),
        ("SUPERUSER", "Superuser"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="hierarchy"
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES
    )

    group = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True
    )

    def clean(self):
        """
        Validation rules:
        - SUPERUSER: group must be None (global access)
        - ADMIN/USER: group is required
        - Only ONE ADMIN per group
        """
        if self.role == "SUPERUSER":
            if self.group is not None:
                raise ValidationError(
                    "SUPERUSER cannot be assigned to a group (has global access)."
                )
        else:
            # USER or ADMIN must have a group
            if self.group is None:
                raise ValidationError(
                    f"{self.role} must be assigned to a group."
                )
            
            # Enforce only ONE ADMIN per group
            if self.role == "ADMIN":
                qs = UserHierarchy.objects.filter(
                    role="ADMIN",
                    group=self.group
                )
                # exclude self during update
                if self.pk:
                    qs = qs.exclude(pk=self.pk)
                
                if qs.exists():
                    raise ValidationError(
                        f"Group '{self.group.name}' already has an ADMIN."
                    )

    def save(self, *args, **kwargs):
        self.full_clean()   # IMPORTANT
        super().save(*args, **kwargs)

    def is_admin(self):
        return self.role in ["ADMIN", "SUPERUSER"]

    def is_superuser(self):
        return self.role == "SUPERUSER"

    def __str__(self):
        group_name = self.group.name if self.group else "(Global)"
        return f"{self.user.username} | {self.role} | {group_name}"


class PendingDeletion(models.Model):
    """
    Tracks deletion requests that require SUPERUSER approval.
    Created when an ADMIN tries to delete another ADMIN.
    """
    
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]
    
    user_hierarchy = models.ForeignKey(
        UserHierarchy,
        on_delete=models.CASCADE,
        related_name="pending_deletions",
        help_text="The UserHierarchy record to be deleted"
    )
    
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="deletion_requests",
        help_text="Admin who requested the deletion"
    )
    
    requested_at = models.DateTimeField(auto_now_add=True)
    
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="PENDING"
    )
    
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_deletions",
        help_text="Superuser who approved/rejected"
    )
    
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ["-requested_at"]
        verbose_name = "Pending Deletion"
        verbose_name_plural = "Pending Deletions"
    
    def __str__(self):
        target = self.user_hierarchy
        requester = self.requested_by.username if self.requested_by else "Unknown"
        return f"Delete {target.user.username} ({target.role}) - requested by {requester} - {self.status}"


class ProductionDatabase(models.Model):
    """
    Represents a HOST/SERVER configuration that is flagged as PRODUCTION.
    Exports from ANY database on these hosts require approval.
    """
    host = models.CharField(max_length=255)
    port = models.IntegerField(default=3306)
    # Name field removed - protection is now host-wide
    is_production = models.BooleanField(default=False)
    hardcoded_dbs = models.TextField(
        blank=True, 
        null=True, 
        help_text="Comma-separated list of database names to show in the migration dropdown."
    )
    
    class Meta:
        unique_together = ('host', 'port')
        verbose_name = "Production Host"
        verbose_name_plural = "Production Hosts"
        
    def __str__(self):
        return f"{self.host}:{self.port} [{'PROD' if self.is_production else 'NON-PROD'}]"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_production:
            from django.apps import apps
            DatabaseHost = apps.get_model('accounts', 'DatabaseHost')
            # Wipe only the PASSWORD from any matching DatabaseHost - username is not sensitive
            hosts = DatabaseHost.objects.filter(ip=self.host, port=self.port)
            for host in hosts:
                if host.db_password:
                    host.db_password = ""
                    host.save(update_fields=['db_password'])


class OperationRequest(models.Model):
    """
    Tracks requests for database operations (Import/Export).
    """
    OP_TYPES = [
        ('EXPORT', 'Export'),
        ('IMPORT', 'Import/Migrate'),
    ]
    
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("EXECUTED", "Executed"),
    ]
    
    operation_type = models.CharField(max_length=20, choices=OP_TYPES)
    target_db = models.CharField(max_length=255, help_text="Database involved")
    description = models.TextField(blank=True, null=True)
    
    # Store complete job parameters as JSON
    params = models.JSONField(help_text="Job parameters needed for execution")
    
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL, null=True,
        related_name="operation_requests"
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="PENDING"
    )
    

    # Maker-Checker Fields
    admin_approved = models.BooleanField(default=False)
    superuser_approved = models.BooleanField(default=False)

    # Group of the requesting user — used to route approval to the correct group Admin
    requester_group = models.ForeignKey(
        'Group',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operation_requests',
        help_text="Group of the user who made this request (for admin-level filtering)"
    )

    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_operations",
        help_text="User who made the final approval decision"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ["-requested_at"]
    
    def __str__(self):
        return f"{self.operation_type} - {self.target_db} - {self.status}"


class DatabaseHost(models.Model):
    """
    Stores the list of database server hosts shown in the UI dropdown.
    Only the IP and port are stored — NO credentials ever.
    Managed by Superusers via Django admin.
    """
    label = models.CharField(
        max_length=100,
        unique=True,
        help_text="Short key shown in UI, e.g. 'db_demo' or 'db_production'"
    )
    ip = models.GenericIPAddressField(
        protocol='both',
        help_text="Server IP address, e.g. 20.40.56.140"
    )
    port = models.PositiveIntegerField(
        default=3306,
        help_text="MySQL port (default 3306)"
    )
    db_username = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Pre-fill database username for this host"
    )
    db_password = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Pre-fill database password for this host"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive hosts are hidden from the UI dropdown"
    )
    notes = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional description, e.g. 'Demo server - Singapore'"
    )

    class Meta:
        verbose_name = "Database Host"
        verbose_name_plural = "Database Hosts"
        ordering = ["label"]

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.label} ({self.ip}:{self.port}) [{status}]"

    def save(self, *args, **kwargs):
        from django.apps import apps
        ProductionDatabase = apps.get_model('accounts', 'ProductionDatabase')
        # If this IP and Port are marked as production, wipe ONLY the password - username is kept
        is_prod = ProductionDatabase.objects.filter(host=self.ip, port=self.port, is_production=True).exists()
        if is_prod:
            self.db_password = ""
            
        super().save(*args, **kwargs)
