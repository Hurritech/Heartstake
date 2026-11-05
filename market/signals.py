from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ApiToken, LedgerEntry, Profile


@receiver(post_save, sender=User)
def create_user_account(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
        ApiToken.objects.create(user=instance)
        LedgerEntry.objects.create(user=instance, amount=1000, reason='Signup bonus')
