import secrets
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    person = models.OneToOneField('Person', on_delete=models.SET_NULL, null=True, blank=True, related_name='account')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1000.00'))
    last_monthly_credit = models.DateField(default=timezone.localdate)


class ApiToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='api_token')
    key = models.CharField(max_length=64, unique=True, default=secrets.token_hex)
    created_at = models.DateTimeField(auto_now_add=True)


class Person(models.Model):
    name = models.CharField(max_length=80, unique=True)
    initials = models.CharField(max_length=3)
    color = models.CharField(max_length=7, default='#7c5cff')
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Relationship(models.Model):
    person_a = models.ForeignKey(Person, on_delete=models.PROTECT, related_name='relationships_as_a')
    person_b = models.ForeignKey(Person, on_delete=models.PROTECT, related_name='relationships_as_b')
    active = models.BooleanField(default=True)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.person_a} & {self.person_b}'


class MarketQuerySet(models.QuerySet):
    def annotate_outcome_pools(self):
        return self.prefetch_related(
            models.Prefetch('outcomes', queryset=Outcome.objects.annotate(pool=models.Sum('bets__amount')).prefetch_related('people'))
        )


class Market(models.Model):
    class Mode(models.TextChoices):
        NEXT = 'NEXT_EVENT', 'Next event'
        TIMEFRAME = 'TIMEFRAME', 'Within timeframe'

    class Kind(models.TextChoices):
        NEXT = 'NEXT', 'Next relationship'
        COUPLE = 'COUPLE', 'Specific couple'
        BREAKUP = 'BREAKUP', 'Couple breakup'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        CLOSED = 'CLOSED', 'Closed'
        RESOLVED = 'RESOLVED', 'Resolved'

    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    mode = models.CharField(max_length=12, choices=Mode.choices, default=Mode.TIMEFRAME)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    closes_at = models.DateTimeField()
    resolves_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    winning_outcome = models.ForeignKey('Outcome', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    objects = MarketQuerySet.as_manager()

    def __str__(self):
        return self.title


class Outcome(models.Model):
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='outcomes')
    label = models.CharField(max_length=120)
    people = models.ManyToManyField(Person, blank=True, related_name='outcomes')
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        unique_together = ('market', 'label')

    def __str__(self):
        return self.label


class Bet(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bets')
    outcome = models.ForeignKey(Outcome, on_delete=models.PROTECT, related_name='bets')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payout = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class LedgerEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ledger')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
