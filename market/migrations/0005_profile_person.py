from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('market', '0004_market_resolves_at')]

    operations = [migrations.AddField(
        model_name='profile', name='person',
        field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='account', to='market.person'),
    )]
