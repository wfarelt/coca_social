from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


DEFAULT_USERS = [
    {
        "username": "admin",
        "email": "admin@coca-social.local",
        "password": "Admin123!",
        "first_name": "Admin",
        "last_name": "Sistema",
        "is_staff": True,
        "is_superuser": True,
        "groups": ["Administradores"],
        "permissions": [],
    },
    {
        "username": "gerente",
        "email": "gerente@coca-social.local",
        "password": "Gerente123!",
        "first_name": "Gerente",
        "last_name": "General",
        "is_staff": True,
        "is_superuser": False,
        "groups": ["Gerencia"],
        "permissions": [],
    },
    {
        "username": "caja",
        "email": "caja@coca-social.local",
        "password": "Caja123!",
        "first_name": "Caja",
        "last_name": "Operativa",
        "is_staff": True,
        "is_superuser": False,
        "groups": ["Caja"],
        "permissions": [],
    },
    {
        "username": "ventas",
        "email": "ventas@coca-social.local",
        "password": "Ventas123!",
        "first_name": "Ventas",
        "last_name": "Operativas",
        "is_staff": True,
        "is_superuser": False,
        "groups": ["Ventas"],
        "permissions": [],
    },
]


GROUP_PERMISSION_MAP = {
    "Administradores": [
        ("core", "view_branch"),
        ("core", "add_branch"),
        ("core", "change_branch"),
        ("core", "view_category"),
        ("core", "add_category"),
        ("core", "change_category"),
        ("core", "view_brand"),
        ("core", "add_brand"),
        ("core", "change_brand"),
        ("core", "view_supplier"),
        ("core", "add_supplier"),
        ("core", "change_supplier"),
        ("core", "view_product"),
        ("core", "add_product"),
        ("core", "change_product"),
        ("core", "view_customer"),
        ("core", "add_customer"),
        ("core", "change_customer"),
        ("core", "view_purchase"),
        ("core", "add_purchase"),
        ("core", "change_purchase"),
        ("core", "view_sale"),
        ("core", "add_sale"),
        ("core", "change_sale"),
        ("core", "view_salereturn"),
        ("core", "add_salereturn"),
        ("core", "change_salereturn"),
        ("core", "view_inventoryadjustment"),
        ("core", "add_inventoryadjustment"),
        ("core", "change_inventoryadjustment"),
        ("core", "view_cashshift"),
        ("core", "add_cashshift"),
        ("core", "change_cashshift"),
        ("core", "view_cashmovement"),
        ("core", "add_cashmovement"),
        ("core", "change_cashmovement"),
        ("core", "view_payment"),
        ("core", "add_payment"),
        ("core", "change_payment"),
        ("core", "view_creditaccount"),
        ("core", "change_creditaccount"),
        ("core", "view_transfer"),
        ("core", "add_transfer"),
        ("core", "change_transfer"),
    ],
    "Gerencia": [
        ("core", "view_branch"),
        ("core", "view_category"),
        ("core", "view_brand"),
        ("core", "view_supplier"),
        ("core", "view_product"),
        ("core", "view_customer"),
        ("core", "view_purchase"),
        ("core", "add_purchase"),
        ("core", "change_purchase"),
        ("core", "view_sale"),
        ("core", "add_sale"),
        ("core", "change_sale"),
        ("core", "view_salereturn"),
        ("core", "add_salereturn"),
        ("core", "change_salereturn"),
        ("core", "view_inventoryadjustment"),
        ("core", "add_inventoryadjustment"),
        ("core", "change_inventoryadjustment"),
        ("core", "view_cashshift"),
        ("core", "add_cashshift"),
        ("core", "change_cashshift"),
        ("core", "view_cashmovement"),
        ("core", "add_cashmovement"),
        ("core", "change_cashmovement"),
        ("core", "view_payment"),
        ("core", "add_payment"),
        ("core", "view_creditaccount"),
        ("core", "change_creditaccount"),
        ("core", "view_transfer"),
    ],
    "Caja": [
        ("core", "view_customer"),
        ("core", "add_customer"),
        ("core", "change_customer"),
        ("core", "view_product"),
        ("core", "view_sale"),
        ("core", "add_sale"),
        ("core", "change_sale"),
        ("core", "view_salereturn"),
        ("core", "add_salereturn"),
        ("core", "view_cashshift"),
        ("core", "add_cashshift"),
        ("core", "change_cashshift"),
        ("core", "view_cashmovement"),
        ("core", "add_cashmovement"),
        ("core", "change_cashmovement"),
        ("core", "view_payment"),
        ("core", "add_payment"),
        ("core", "view_creditaccount"),
        ("core", "change_creditaccount"),
    ],
    "Ventas": [
        ("core", "view_customer"),
        ("core", "add_customer"),
        ("core", "change_customer"),
        ("core", "view_product"),
        ("core", "view_sale"),
        ("core", "add_sale"),
        ("core", "change_sale"),
        ("core", "view_salereturn"),
        ("core", "add_salereturn"),
        ("core", "view_transfer"),
    ],
}


class Command(BaseCommand):
    help = "Create the default application users and groups."

    def handle(self, *args, **options):
        user_model = get_user_model()
        created_users = []

        for group_name, permission_pairs in GROUP_PERMISSION_MAP.items():
            group, _ = Group.objects.get_or_create(name=group_name)
            permissions = Permission.objects.filter(content_type__app_label__in={app_label for app_label, _ in permission_pairs}, codename__in=[codename for _, codename in permission_pairs])
            group.permissions.set(permissions)

        for user_data in DEFAULT_USERS:
            user_defaults = {key: value for key, value in user_data.items() if key not in {"groups", "password", "permissions"}}
            groups = user_data["groups"]
            password = user_data["password"]
            user, created = user_model.objects.get_or_create(username=user_defaults["username"], defaults=user_defaults)
            if not created:
                for field, value in user_defaults.items():
                    setattr(user, field, value)
            user.set_password(password)
            user.save()
            user.groups.set(Group.objects.filter(name__in=groups))
            created_users.append((user.username, password, created))

        for username, password, created in created_users:
            status = "created" if created else "updated"
            self.stdout.write(self.style.SUCCESS(f"{username} {status} | password: {password}"))
