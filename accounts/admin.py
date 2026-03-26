from django.contrib import admin
from django.contrib import messages
from django import forms
from django.urls import path
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.utils import timezone
from django.shortcuts import render
from django.contrib.admin import helpers
from django.http import HttpResponseRedirect
from .models import Group, UserHierarchy, PendingDeletion, ProductionDatabase, OperationRequest, DatabaseHost
import config
import sys
import os
import mysql.connector

# Ensure we can import config from parent directory if needed, 
# though usually it is in python path if running via manage.py from root.
# Just importing config should work if the app is structure correctly.

# Validates User Hierarchy for permission checks
def is_admin_or_superuser(user):
    try:
        if user.is_superuser: return True
        if hasattr(user, 'hierarchy'):
            return user.hierarchy.is_admin() or user.hierarchy.is_superuser()
        return False
    except:
        return False

def is_superuser_only(user):
    try:
        if user.is_superuser: return True 
        if hasattr(user, 'hierarchy'):
            return user.hierarchy.is_superuser()
        return False
    except:
        return False@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    
    def has_module_permission(self, request):
        return is_admin_or_superuser(request.user)
    
    def has_view_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)
    
    def has_change_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)
        
    def has_add_permission(self, request):
        return is_admin_or_superuser(request.user)
        
    def has_delete_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)


@admin.register(UserHierarchy)
class UserHierarchyAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "group",
        "is_admin",
        "is_superuser",
    )

    list_filter = ("role", "group")
    search_fields = ("user__username",)
    
    def has_module_permission(self, request):
        return is_admin_or_superuser(request.user)
    
    def has_view_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)
    
    def get_form(self, request, obj=None, **kwargs):
        """
        Customize the form based on user role.
        ADMINs cannot select SUPERUSER role.
        """
        form = super().get_form(request, obj, **kwargs)
        
        # Check if the current user is an ADMIN (not SUPERUSER)
        try:
            user_hierarchy = request.user.hierarchy
            if user_hierarchy.is_admin() and not user_hierarchy.is_superuser():
                # Limit role choices to exclude SUPERUSER
                if 'role' in form.base_fields:
                    form.base_fields['role'].choices = [
                        choice for choice in form.base_fields['role'].choices
                        if choice[0] != 'SUPERUSER'
                    ]
        except UserHierarchy.DoesNotExist:
            pass
        
        return form
    
    def save_model(self, request, obj, form, change):
        """
        Prevent ADMINs from creating SUPERUSER records.
        This is a failsafe in case form validation is bypassed.
        """
        try:
            user_hierarchy = request.user.hierarchy
            
            # If current user is ADMIN (not SUPERUSER)
            if user_hierarchy.is_admin() and not user_hierarchy.is_superuser():
                # Block if trying to create/update to SUPERUSER role
                if obj.role == "SUPERUSER":
                    messages.error(
                        request,
                        "ADMINs are not allowed to create or modify SUPERUSER records."
                    )
                    return  # Don't save
        except UserHierarchy.DoesNotExist:
            pass
        
        super().save_model(request, obj, form, change)
    
    def has_delete_permission(self, request, obj=None):
        """
        Prevent ADMINs from deleting SUPERUSERs.
        Only SUPERUSERs can delete other SUPERUSERs.
        """
        # Check if user has basic delete permission
        if not super().has_delete_permission(request, obj):
            return False
        
        # If checking permission for a specific object
        if obj is not None:
            # If trying to delete a SUPERUSER
            if obj.role == "SUPERUSER":
                # Only allow if the requesting user is also a SUPERUSER
                try:
                    user_hierarchy = request.user.hierarchy
                    return user_hierarchy.is_superuser()
                except UserHierarchy.DoesNotExist:
                    return False
        
        return True
    
    def delete_model(self, request, obj):
        """
        Intercept deletion requests.
        If ADMIN tries to delete another ADMIN, create a pending request.
        SUPERUSERs can delete directly.
        """
        try:
            user_hierarchy = request.user.hierarchy
            
            # If SUPERUSER, allow direct deletion
            if user_hierarchy.is_superuser():
                super().delete_model(request, obj)
                return
            
            # If ADMIN trying to delete another ADMIN
            if user_hierarchy.is_admin() and obj.role == "ADMIN":
                # Create pending deletion request
                PendingDeletion.objects.create(
                    user_hierarchy=obj,
                    requested_by=request.user
                )
                messages.warning(
                    request,
                    f"Deletion request for {obj.user.username} has been submitted for SUPERUSER approval."
                )
                return  # Don't actually delete
        except UserHierarchy.DoesNotExist:
            pass
        
        # For all other cases, allow deletion
        super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        """
        Handle bulk deletion attempts.
        Similar logic to delete_model.
        """
        try:
            user_hierarchy = request.user.hierarchy
            
            # If SUPERUSER, allow direct bulk deletion
            if user_hierarchy.is_superuser():
                super().delete_queryset(request, queryset)
                return
            
            # If ADMIN, check if trying to delete any ADMINs
            if user_hierarchy.is_admin():
                admins_to_delete = queryset.filter(role="ADMIN")
                others_to_delete = queryset.exclude(role="ADMIN")
                
                # Create pending requests for ADMINs
                for admin_obj in admins_to_delete:
                    PendingDeletion.objects.create(
                        user_hierarchy=admin_obj,
                        requested_by=request.user
                    )
                
                # Delete others directly
                if others_to_delete.exists():
                    super().delete_queryset(request, others_to_delete)
                
                if admins_to_delete.exists():
                    messages.warning(
                        request,
                        f"{admins_to_delete.count()} ADMIN deletion(s) submitted for SUPERUSER approval."
                    )
                return
        except UserHierarchy.DoesNotExist:
            pass
        
        # Default behavior
        super().delete_queryset(request, queryset)


@admin.register(PendingDeletion)
class PendingDeletionAdmin(admin.ModelAdmin):
    list_display = (
        "get_target_user",
        "get_target_role",
        "get_target_group",
        "requested_by",
        "requested_at",
        "status",
        "reviewed_by",
    )
    
    list_filter = ("status", "requested_at")
    search_fields = ("user_hierarchy__user__username", "requested_by__username")
    readonly_fields = ("user_hierarchy", "requested_by", "requested_at", "reviewed_by", "reviewed_at")
    
    actions = ["approve_deletion", "reject_deletion"]
    
    def get_target_user(self, obj):
        return obj.user_hierarchy.user.username
    get_target_user.short_description = "Target User"
    
    def get_target_role(self, obj):
        return obj.user_hierarchy.role
    get_target_role.short_description = "Role"
    
    def get_target_group(self, obj):
        return obj.user_hierarchy.group.name if obj.user_hierarchy.group else "(Global)"
    get_target_group.short_description = "Group"
    
    
    def has_module_permission(self, request):
        return is_admin_or_superuser(request.user)
        
    def has_view_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)

    def has_add_permission(self, request):
        """Prevent manual creation of pending deletions."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Only SUPERUSERs can change (approve/reject)."""
        return is_superuser_only(request.user)
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of pending requests."""
        return False
    
    def approve_deletion(self, request, queryset):
        """Approve selected deletion requests and execute them."""
        try:
            user_hierarchy = request.user.hierarchy
            if not user_hierarchy.is_superuser():
                messages.error(request, "Only SUPERUSERs can approve deletions.")
                return
            
            approved_count = 0
            for pending in queryset.filter(status="PENDING"):
                # Delete the actual UserHierarchy record
                try:
                    target = pending.user_hierarchy
                    target.delete()
                    
                    # Mark as approved
                    pending.status = "APPROVED"
                    pending.reviewed_by = request.user
                    pending.reviewed_at = timezone.now()
                    pending.save()
                    
                    approved_count += 1
                except Exception as e:
                    messages.error(request, f"Failed to delete {target.user.username}: {str(e)}")
            
            if approved_count:
                messages.success(request, f"{approved_count} deletion(s) approved and executed.")
        except UserHierarchy.DoesNotExist:
            messages.error(request, "You don't have permission to approve deletions.")
    approve_deletion.short_description = "Approve selected deletion requests"
    
    def reject_deletion(self, request, queryset):
        """Reject selected deletion requests."""
        try:
            user_hierarchy = request.user.hierarchy
            if not user_hierarchy.is_superuser():
                messages.error(request, "Only SUPERUSERs can reject deletions.")
                return
            
            rejected_count = queryset.filter(status="PENDING").update(
                status="REJECTED",
                reviewed_by=request.user,
                reviewed_at=timezone.now()
            )
            
            if rejected_count:
                messages.success(request, f"{rejected_count} deletion(s) rejected.")
        except UserHierarchy.DoesNotExist:
            messages.error(request, "You don't have permission to reject deletions.")
    reject_deletion.short_description = "Reject selected deletion requests"


@admin.register(ProductionDatabase)
class ProductionDatabaseAdmin(admin.ModelAdmin):
    list_display = ("host", "port", "is_production")
    list_filter = ("is_production", "host")
    search_fields = ("host",)
    
    def has_module_permission(self, request):
        return is_admin_or_superuser(request.user)
    
    def has_view_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)
    
    def has_change_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)
        
    def has_add_permission(self, request):
        return is_admin_or_superuser(request.user)
        
    def has_delete_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        # Populate host choices from DatabaseHost table (primary)
        # Falls back to config.HOSTS if the table is empty (e.g. fresh install before migration)
        host_choices = [("", "---------")]
        try:
            db_hosts = DatabaseHost.objects.filter(is_active=True).order_by('label')
            if db_hosts.exists():
                for h in db_hosts:
                    host_choices.append((h.ip, f"{h.label} ({h.ip}:{h.port})"))
            else:
                # Fallback to config.HOSTS
                for key, details in config.HOSTS.items():
                    ip = details.get('ip')
                    host_choices.append((ip, f"{key} ({ip})"))
        except Exception:
            pass

        if 'host' in form.base_fields:
            form.base_fields['host'].widget = forms.Select(choices=host_choices)
            form.base_fields['host'].help_text = "Select from Database Hosts (managed in Django admin)"

        return form


@admin.register(OperationRequest)
class OperationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "operation_type",
        "target_db",
        "requested_by",
        "get_requester_group",
        "requested_at",
        "status",
        "admin_approved",
        "superuser_approved",
    )

    def get_requester_group(self, obj):
        return obj.requester_group.name if obj.requester_group else "(No group)"
    get_requester_group.short_description = "Requester Group"
    get_requester_group.admin_order_field = "requester_group__name"
    
    def has_module_permission(self, request):
        return is_admin_or_superuser(request.user)
    
    def has_view_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)
    
    def has_change_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)
        
    def has_add_permission(self, request):
        return False # Requests are created via API
        
    def has_delete_permission(self, request, obj=None):
        return is_superuser_only(request.user)

    list_filter = (
        "status", 
        "operation_type", 
        "admin_approved", 
        "superuser_approved",
        "requester_group",
    )
    
    search_fields = ("target_db", "requested_by__username")
    # Make approval fields READONLY so they cannot be manually toggled in the form
    readonly_fields = ("status", "get_masked_params", "requested_by", "requested_at", "reviewed_by", "reviewed_at", "admin_approved", "superuser_approved", "requester_group")
    
    exclude = ("params",)
    
    actions = ["reject_request", "approve_request_admin"]

    def get_masked_params(self, obj):
         import json
         if not obj.params: return "{}"
         display_params = dict(obj.params) if isinstance(obj.params, dict) else {}
         display_params.pop('password', None)
         display_params.pop('source_password', None)
         display_params.pop('target_password', None)
         return json.dumps(display_params, indent=2)
    get_masked_params.short_description = "Params (Masked)"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:request_id>/approve/',
                self.admin_site.admin_view(self.approve_single_request),
                name='operationrequest-approve',
            ),
            path(
                '<int:request_id>/endorse/',
                self.admin_site.admin_view(self.endorse_single_request),
                name='operationrequest-endorse',
            ),
            path(
                '<int:request_id>/reject/',
                self.admin_site.admin_view(self.reject_single_request),
                name='operationrequest-reject',
            ),
        ]
        return custom_urls + urls

    def approve_single_request(self, request, request_id):
        obj = self.get_object(request, request_id)
        if obj is None:
            messages.error(request, "Request not found.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/accounts/operationrequest/'))
            
        # Re-use the bulk action logic with a single-item queryset
        queryset = OperationRequest.objects.filter(pk=obj.pk)
        
        # We manually call the bulk action, which handles all the Superuser validation, 
        # template rendering for Target Password, and state updating.
        response = self.approve_request(request, queryset)
        
        # If the action returned a response (like our intermediate template), return it
        if response:
             return response
             
        # Force a refresh to ensure the status is saved, then construct a cache-busting redirect
        try:
             obj.refresh_from_db()
        except Exception:
             pass
             
        import time
        return HttpResponseRedirect(f"/admin/accounts/operationrequest/{request_id}/change/?_t={int(time.time())}")

    def endorse_single_request(self, request, request_id):
        obj = self.get_object(request, request_id)
        if obj is None:
            messages.error(request, "Request not found.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/accounts/operationrequest/'))
            
        if obj.status == "EXECUTED":
            messages.warning(request, "Cannot endorse an already executed request.")
        else:
            obj.admin_approved = True
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
            obj.save(update_fields=['admin_approved', 'reviewed_by', 'reviewed_at'])
            self.log_change(request, obj, "Endorsed request (Admin).")
            messages.success(request, "Request ENDORSED by ADMIN. Superuser approval still required.")
             
        import time
        return HttpResponseRedirect(f"/admin/accounts/operationrequest/{request_id}/change/?_t={int(time.time())}")

    def reject_single_request(self, request, request_id):
        obj = self.get_object(request, request_id)
        if obj is None:
            messages.error(request, "Request not found.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/accounts/operationrequest/'))
            
        if obj.status in ["REJECTED", "EXECUTED"]:
            messages.warning(request, f"Request is already {obj.status}.")
        else:
            obj.status = "REJECTED"
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
            obj.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
            self.log_change(request, obj, "Rejected request.")
            messages.success(request, "Request rejected.")
             
        import time
        return HttpResponseRedirect(f"/admin/accounts/operationrequest/{request_id}/change/?_t={int(time.time())}")

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        user = request.user
        is_app_superuser = user.is_superuser or (hasattr(user, 'hierarchy') and user.hierarchy.is_superuser())
        is_app_admin = (user.is_staff and not user.is_superuser) or (hasattr(user, 'hierarchy') and user.hierarchy.is_admin() and not is_app_superuser)
        
        extra_context['is_app_admin'] = is_app_admin
        extra_context['is_app_superuser'] = is_app_superuser
        
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def get_queryset(self, request):
        """
        SUPERUSER sees ALL requests.
        ADMIN only sees requests from users in their own group.
        """
        qs = super().get_queryset(request)
        if is_superuser_only(request.user):
            return qs  # Superuser sees everything
        try:
            admin_group = request.user.hierarchy.group
            if admin_group:
                return qs.filter(requester_group=admin_group)
        except Exception:
            # If they are native is_staff but have no hierarchy/group, let them see everything.
            if request.user.is_staff:
                return qs
            
        return qs.none()  # Safety: show nothing if completely unauthorized
    
    def approve_request(self, request, queryset):
        """
        SUPERUSER approval action.
        Marks request as APPROVED and superuser_approved=True.
        Asks for target_password if there are IMPORT operations.
        Does NOT auto-execute - execution is triggered by user action post-approval.
        """
        try:
            user_hierarchy = request.user.hierarchy
            if not user_hierarchy.is_superuser():
                messages.error(request, "Only SUPERUSERs can approve using this action. Admins should use 'Endorse Request (Admin)'.")
                return
            
            # Check if any IMPORTS are in the selection that are not already EXECUTED
            has_imports = queryset.filter(operation_type='IMPORT').exclude(status="EXECUTED").exists()

            # Check if any EXPORT-only operations involve a production source host.
            # These need the source password collected at approval time too,
            # otherwise mysqldump runs with no credentials and fails at 0%.
            has_prod_exports = False
            for obj in queryset.exclude(status="EXECUTED").filter(operation_type='EXPORT'):
                params = obj.params if isinstance(obj.params, dict) else {}
                source_host = params.get('host')
                if source_host:
                    from accounts.models import ProductionDatabase
                    is_prod = ProductionDatabase.objects.filter(host=source_host, is_production=True).exists()
                    if is_prod:
                        has_prod_exports = True
                        break

            # Show source-password form for IMPORT ops from production hosts
            require_source_password = False
            if has_imports:
                for obj in queryset.exclude(status="EXECUTED").filter(operation_type='IMPORT'):
                    params = obj.params if isinstance(obj.params, dict) else {}
                    source_host = params.get('host')

                    # If there's no password OR it's a known production host, require it
                    if not params.get('password'):
                        require_source_password = True
                        break

                    if source_host:
                        from accounts.models import ProductionDatabase
                        is_prod = ProductionDatabase.objects.filter(host=source_host, is_production=True).exists()
                        if is_prod and not params.get('password'):
                             require_source_password = True
                             break
                        elif is_prod and params.get('password') == '':
                             # empty string was passed by frontend
                             require_source_password = True
                             break

            # Export-only production jobs always need the source password
            if has_prod_exports:
                require_source_password = True

            # needs_password_form = True when at least one job in the selection
            # requires a password to be entered (either import target/source, or
            # export-only source on a production host).
            needs_password_form = has_imports or has_prod_exports

            # Show the intermediate password form if not yet submitted
            if needs_password_form and 'apply' not in request.POST:
                return render(request, "admin/enter_target_password.html", context={
                    'queryset': queryset,
                    'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
                    'action': 'approve_request',
                    'require_source_password': require_source_password,
                    'has_imports': has_imports,
                    'has_prod_exports': has_prod_exports,
                })
            
            target_password = request.POST.get('target_password', '')
            source_password = request.POST.get('source_password', '')
            
            count = 0
            for obj in queryset.exclude(status="EXECUTED"):
                 if obj.operation_type == 'IMPORT':
                      if not target_password:
                           messages.error(request, "Target password is required for Migration requests. Approval step aborted.")
                           return HttpResponseRedirect(request.get_full_path())

                      params = obj.params if isinstance(obj.params, dict) else {}

                      if require_source_password and not source_password:
                           messages.error(request, "Source password is required for Production Database migrations. Approval step aborted.")
                           return HttpResponseRedirect(request.get_full_path())

                      # Validation: Verify the actual connections
                      try:
                          target_conn = mysql.connector.connect(
                              host=params.get('target_host'),
                              port=params.get('target_port', 3306),
                              user=params.get('target_user'),
                              password=target_password,
                              connect_timeout=7
                          )
                          target_conn.close()
                      except mysql.connector.Error as err:
                          # Clean up the error message for users
                          if err.errno == 1045: # ER_ACCESS_DENIED_ERROR
                              messages.error(request, "INCORRECT TARGET PASSWORD: The password entered for the Target Host is incorrect. Please enter the correct password.")
                          else:
                              messages.error(request, f"Target Database connection failed: {err.msg}")
                          return HttpResponseRedirect(request.get_full_path())

                      eff_source_pw = source_password if require_source_password else params.get('password')
                      if eff_source_pw is not None:
                          try:
                              source_conn = mysql.connector.connect(
                                  host=params.get('host'),
                                  port=params.get('port', 3306),
                                  user=params.get('user'),
                                  password=eff_source_pw,
                                  connect_timeout=7
                              )

                              # Verify the database actually exists on the source
                              source_db = params.get('database')
                              if source_db:
                                  cursor = source_conn.cursor()
                                  cursor.execute("SHOW DATABASES")
                                  dbs = [row[0] for row in cursor.fetchall()]
                                  cursor.close()
                                  if source_db not in dbs:
                                      source_conn.close()
                                      messages.error(request, f"Source Database '{source_db}' does not exist on the host {params.get('host')}. Please check your Hardcoded DBs config.")
                                      return HttpResponseRedirect(request.get_full_path())

                              source_conn.close()
                          except mysql.connector.Error as err:
                              if err.errno == 1045:
                                  messages.error(request, "INCORRECT SOURCE PASSWORD: The password entered for the Source Host is incorrect. Please enter the correct password.")
                              else:
                                  messages.error(request, f"Source Database connection failed: {err.msg}.")
                              return HttpResponseRedirect(request.get_full_path())

                      import credential_store
                      credential_store.store_credentials(
                          request_id=obj.id,
                          target_password=target_password,
                          source_password=source_password if require_source_password else None
                      )

                      # Only remove target_password and production source_password from params.
                      # Do NOT remove params['password'] for non-production sources —
                      # that is the original source credential the migration engine needs.
                      if 'target_password' in params:
                           del params['target_password']
                      if require_source_password and 'password' in params:
                           # Production source: password will be reinjected from credential_store at execution time
                           del params['password']
                      if 'source_password' in params:
                           del params['source_password']

                      obj.params = params

                 elif obj.operation_type == 'EXPORT' and has_prod_exports:
                      # Export-only from a production host: collect and store just the source password.
                      # No target password needed (there is no target for a plain export).
                      if require_source_password and not source_password:
                           messages.error(request, "Source password is required for Production Database exports. Approval step aborted.")
                           return HttpResponseRedirect(request.get_full_path())

                      params = obj.params if isinstance(obj.params, dict) else {}

                      # Validate source connection with the entered password
                      try:
                          source_conn = mysql.connector.connect(
                              host=params.get('host'),
                              port=params.get('port', 3306),
                              user=params.get('user'),
                              password=source_password,
                              connect_timeout=7
                          )
                          source_conn.close()
                      except mysql.connector.Error as err:
                          if err.errno == 1045:
                              messages.error(request, "INCORRECT SOURCE PASSWORD: The password entered for the Source Host is incorrect. Please enter the correct password.")
                          else:
                              messages.error(request, f"Source Database connection failed: {err.msg}.")
                          return HttpResponseRedirect(request.get_full_path())

                      import credential_store
                      credential_store.store_credentials(
                          request_id=obj.id,
                          target_password=None,
                          source_password=source_password
                      )

                      # Remove any stored password from params — reinjected at execution time
                      if 'password' in params:
                           del params['password']
                      obj.params = params

                 obj.status = "APPROVED"
                 obj.superuser_approved = True
                 obj.admin_approved = True
                 obj.reviewed_by = request.user
                 obj.reviewed_at = timezone.now()
                 obj.save()
                 self.log_change(request, obj, "Approved request (Superuser).")
                 count += 1
            
            if count:
                messages.success(request, f"{count} request(s) approved by SUPERUSER.")
            else:
                messages.warning(request, "No requests were updated. They might already be EXECUTED.")
                
        except UserHierarchy.DoesNotExist:
             messages.error(request, "Permission denied.")
    approve_request.short_description = "Approve Request (Superuser)"

    def approve_request_admin(self, request, queryset):
        """
        ADMIN endorsement action.
        Sets admin_approved=True. Restricts to OWN GROUP if the Admin is assigned to one.
        Execution still requires SUPERUSER approval.
        """
        is_app_admin = (request.user.is_staff and not request.user.is_superuser) or (hasattr(request.user, 'hierarchy') and request.user.hierarchy.is_admin())
        if not is_app_admin and not is_superuser_only(request.user):
            messages.error(request, "Only ADMINs (or Superusers) can use this action.")
            return

        admin_group = None
        try:
            admin_group = request.user.hierarchy.group
        except Exception:
            pass

        endorsed = 0
        skipped = 0

        for op in queryset.exclude(status="EXECUTED"):
            # Enforce own-group restriction (SUPERUSER or Native Admin without group can endorse any)
            if admin_group and op.requester_group != admin_group and not is_superuser_only(request.user):
                skipped += 1
                continue
            op.admin_approved = True
            op.reviewed_by = request.user
            op.reviewed_at = timezone.now()
            # Status remains PENDING until SUPERUSER also approves
            op.save(update_fields=['admin_approved', 'reviewed_by', 'reviewed_at'])
            self.log_change(request, op, "Endorsed request (Admin).")
            endorsed += 1

        if endorsed:
            messages.success(request, f"{endorsed} request(s) ENDORSED by ADMIN. Superuser approval still required for execution.")
        if skipped:
            messages.warning(request, f"{skipped} request(s) skipped — they belong to a different group.")
    approve_request_admin.short_description = "Endorse Request (Admin — own group only)"

    def reject_request(self, request, queryset):
        """
        Reject request action.
        """
        start_count = queryset.count()
        # Only pending can be rejected? Or approved too? Let's say Pending or Approved can be rejected to cancel.
        rejected_objs = list(queryset.exclude(status__in=["REJECTED", "EXECUTED"]))
        count = queryset.exclude(status__in=["REJECTED", "EXECUTED"]).update(
            status="REJECTED",
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        for obj in rejected_objs:
            self.log_change(request, obj, "Rejected request.")
            
        if count:
            messages.success(request, f"{count} request(s) rejected.")
    reject_request.short_description = "Reject Request"
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        user = request.user

        # Remove reject from the action dropdown for everyone, 
        # as it will now be handled inside the change view via button.
        actions.pop('reject_request', None)

        # Determine the app-level role from hierarchy and Django flags
        is_app_superuser = user.is_superuser or (hasattr(user, 'hierarchy') and user.hierarchy.is_superuser())
        is_app_admin = (user.is_staff and not user.is_superuser) or (hasattr(user, 'hierarchy') and user.hierarchy.is_admin() and not is_app_superuser)

        if is_app_superuser:
            # Superusers do the real approval — hide the admin-endorse action
            actions.pop('approve_request_admin', None)
        elif is_app_admin:
            # Admins can only endorse — hide the superuser-approve action
            actions.pop('approve_request', None)
            # Remove from dropdown because we want them to use the button instead
            actions.pop('approve_request_admin', None)
        else:
            # Regular users / Django-only superusers with no hierarchy: hide both
            actions.pop('approve_request', None)
            actions.pop('approve_request_admin', None)

        return actions


@admin.register(DatabaseHost)
class DatabaseHostAdmin(admin.ModelAdmin):
    """
    Manages the list of MySQL server hosts shown in the UI dropdown.
    SECURITY: Only SUPERUSER can add/edit/delete hosts.
    ADMIN role can only VIEW (read-only).
    No credentials are ever stored here — IP + port only.
    """
    list_display  = ("label", "ip", "port", "is_active", "notes")
    list_filter   = ("is_active",)
    search_fields = ("label", "ip", "notes")
    readonly_fields_for_admin = ("label", "ip", "port", "is_active", "notes")

    def has_module_permission(self, request):
        return is_admin_or_superuser(request.user)

    def has_view_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)

    def has_add_permission(self, request):
        """Only SUPERUSER can add new hosts."""
        return is_superuser_only(request.user)

    def has_change_permission(self, request, obj=None):
        """Only SUPERUSER can edit hosts."""
        return is_superuser_only(request.user)

    def has_delete_permission(self, request, obj=None):
        """Only SUPERUSER can delete hosts."""
        return is_superuser_only(request.user)

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj and obj.ip:
            from accounts.models import ProductionDatabase
            is_prod = ProductionDatabase.objects.filter(host=obj.ip, port=obj.port, is_production=True).exists()
            if is_prod:
                # Only hide the password — username is not sensitive and stays visible
                if 'db_password' in fields:
                    fields.remove('db_password')
        return fields

    def get_readonly_fields(self, request, obj=None):
        """Make all fields read-only for non-Superusers (Admins get view-only)."""
        readonly = list(self.readonly_fields_for_admin) if not is_superuser_only(request.user) else []
        return readonly

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.ip:
            from accounts.models import ProductionDatabase
            is_prod = ProductionDatabase.objects.filter(host=obj.ip, port=obj.port, is_production=True).exists()
            if is_prod:
                # We can add a non-field warning or simply rely on the fields being gone
                pass
        return form
