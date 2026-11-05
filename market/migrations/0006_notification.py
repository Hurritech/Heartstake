from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('market', '0005_profile_person')]

    operations = [migrations.CreateModel(
        name='Notification',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('message', models.CharField(max_length=240)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('read_at', models.DateTimeField(blank=True, null=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='auth.user')),
        ],
        options={'ordering': ['-created_at']},
    )]
