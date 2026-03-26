from django.db import migrations, models


def seed_hosts_from_config(apps, schema_editor):
    """
    Auto-populate DatabaseHost from config.HOSTS so no existing host is lost.
    'localhost' is skipped for GenericIPAddressField compliance — added as 127.0.0.1.
    """
    import config
    DatabaseHost = apps.get_model('accounts', 'DatabaseHost')
    for label, details in config.HOSTS.items():
        ip = details.get('ip', '127.0.0.1')
        # GenericIPAddressField does not accept 'localhost' — normalise it
        if ip.lower() == 'localhost':
            ip = '127.0.0.1'
        DatabaseHost.objects.get_or_create(
            label=label,
            defaults={
                'ip':       ip,
                'port':     details.get('port', 3306),
                'is_active': True,
                'notes':    'Seeded from config.py during migration',
            }
        )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_add_requester_group_to_operation_request'),
    ]

    operations = [
        migrations.CreateModel(
            name='DatabaseHost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label',     models.CharField(help_text="Short key shown in UI, e.g. 'db_demo'", max_length=100, unique=True)),
                ('ip',        models.GenericIPAddressField(help_text='Server IP address, e.g. 20.40.56.140', protocol='both')),
                ('port',      models.PositiveIntegerField(default=3306, help_text='MySQL port (default 3306)')),
                ('is_active', models.BooleanField(default=True, help_text='Inactive hosts are hidden from the UI dropdown')),
                ('notes',     models.CharField(blank=True, help_text="Optional description", max_length=255)),
            ],
            options={
                'verbose_name': 'Database Host',
                'verbose_name_plural': 'Database Hosts',
                'ordering': ['label'],
            },
        ),
        # Seed existing hosts immediately after table creation
        migrations.RunPython(seed_hosts_from_config, migrations.RunPython.noop),
    ]
