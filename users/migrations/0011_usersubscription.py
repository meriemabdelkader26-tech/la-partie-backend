from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_notification'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plan', models.CharField(choices=[('FREE', 'Free'), ('PLUS', 'Plus'), ('PRO', 'Pro')], default='FREE', max_length=20)),
                ('status', models.CharField(choices=[('INACTIVE', 'Inactive'), ('ACTIVE', 'Active'), ('TRIALING', 'Trialing'), ('PAST_DUE', 'Past due'), ('CANCELED', 'Canceled'), ('UNPAID', 'Unpaid'), ('INCOMPLETE', 'Incomplete')], default='INACTIVE', max_length=20)),
                ('stripe_customer_id', models.CharField(blank=True, db_index=True, max_length=120, null=True)),
                ('stripe_subscription_id', models.CharField(blank=True, db_index=True, max_length=120, null=True)),
                ('stripe_price_id', models.CharField(blank=True, max_length=120, null=True)),
                ('current_period_start', models.DateTimeField(blank=True, null=True)),
                ('current_period_end', models.DateTimeField(blank=True, null=True)),
                ('cancel_at_period_end', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=models.CASCADE, related_name='subscription', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'User Subscription',
                'verbose_name_plural': 'User Subscriptions',
                'db_table': 'user_subscriptions',
            },
        ),
        migrations.AddIndex(
            model_name='usersubscription',
            index=models.Index(fields=['plan', 'status'], name='user_subscr_plan_9152e7_idx'),
        ),
    ]
