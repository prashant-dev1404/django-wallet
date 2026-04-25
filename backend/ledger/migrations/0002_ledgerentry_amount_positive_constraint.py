from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ledger', '0001_initial'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='ledgerentry',
            constraint=models.CheckConstraint(
                condition=models.Q(amount_paise__gt=0),
                name='ledgerentry_amount_positive',
            ),
        ),
    ]
