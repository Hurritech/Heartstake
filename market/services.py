from datetime import timedelta
from decimal import Decimal, ROUND_DOWN
from itertools import combinations

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Bet, LedgerEntry, Market, Notification, Person, Profile, Relationship, Outcome


@transaction.atomic
def place_bet(user, outcome, amount):
    amount = Decimal(str(amount)).quantize(Decimal('0.01'))
    if amount < Decimal('1.00'):
        raise ValueError('Minimum bet is 1 credit.')
    market = outcome.market
    if market.status != Market.Status.OPEN or market.closes_at <= timezone.now():
        raise ValueError('This market is closed.')
    profile = Profile.objects.select_for_update().get(user=user)
    if profile.person_id and outcome.people.filter(pk=profile.person_id).exists():
        raise ValueError('You cannot bet on yourself.')
    if profile.balance < amount:
        raise ValueError('Not enough credits.')
    profile.balance -= amount
    profile.save(update_fields=['balance'])
    bet = Bet.objects.create(user=user, outcome=outcome, amount=amount)
    LedgerEntry.objects.create(user=user, amount=-amount, reason=f'Bet: {market.title}')
    return bet


@transaction.atomic
def resolve_market(market, winning_outcome):
    market = Market.objects.select_for_update().get(pk=market.pk)
    if market.status == Market.Status.RESOLVED:
        raise ValueError('Market is already resolved.')
    if winning_outcome.market_id != market.id:
        raise ValueError('Outcome does not belong to this market.')
    if (market.mode == Market.Mode.TIMEFRAME and winning_outcome.label == 'AGAINST'
            and (not market.resolves_at or timezone.now() < market.resolves_at)):
        raise ValueError('AGAINST cannot resolve before the observation window ends.')
    total_pool = Bet.objects.filter(outcome__market=market).aggregate(v=Sum('amount'))['v'] or Decimal('0')
    winning_pool = Bet.objects.filter(outcome=winning_outcome).aggregate(v=Sum('amount'))['v'] or Decimal('0')
    market.status = Market.Status.RESOLVED
    market.winning_outcome = winning_outcome
    market.resolved_at = timezone.now()
    market.save(update_fields=['status', 'winning_outcome', 'resolved_at'])
    notifications = []
    if not winning_pool:
        for bet in Bet.objects.filter(outcome__market=market).select_related('outcome'):
            notifications.append(Notification(
                user_id=bet.user_id,
                message=f'{market.title}: {bet.outcome.label} lost — payout 0.00 CR.',
            ))
        Notification.objects.bulk_create(notifications)
        return
    for bet in Bet.objects.select_related('user').filter(outcome=winning_outcome):
        payout = (total_pool * bet.amount / winning_pool).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        bet.payout = payout
        bet.save(update_fields=['payout'])
        profile = Profile.objects.select_for_update().get(user=bet.user)
        profile.balance += payout
        profile.save(update_fields=['balance'])
        LedgerEntry.objects.create(user=bet.user, amount=payout, reason=f'Payout: {market.title}')
    for bet in Bet.objects.select_related('outcome').filter(outcome__market=market):
        if bet.outcome_id == winning_outcome.id:
            message = f'{market.title}: {bet.outcome.label} won — payout {bet.payout:.2f} CR.'
        else:
            message = f'{market.title}: {bet.outcome.label} lost — payout 0.00 CR.'
        notifications.append(Notification(user_id=bet.user_id, message=message))
    Notification.objects.bulk_create(notifications)


def resolve_relationship_markets(people, kind):
    """Resolve markets whose outcome represents this exact relationship pair."""
    people = set(people)
    markets = Market.objects.filter(kind=kind, status=Market.Status.OPEN).prefetch_related('outcomes__people')
    for market in markets:
        winner = next((outcome for outcome in market.outcomes.all()
                       if set(outcome.people.all()) == people), None)
        if winner:
            resolve_market(market, winner)
            if market.mode == Market.Mode.NEXT:
                remaining = [outcome for outcome in market.outcomes.all()
                             if not set(outcome.people.all()).intersection(people)]
                if remaining:
                    replacement = Market.objects.create(
                        title=market.title, description=market.description, kind=market.kind,
                        mode=market.mode, closes_at=timezone.now() + timedelta(days=3650),
                    )
                    for order, outcome in enumerate(remaining):
                        replacement_outcome = Outcome.objects.create(
                            market=replacement, label=outcome.label, order=order,
                        )
                        replacement_outcome.people.set(outcome.people.all())


def sync_next_event_markets():
    """Make open next-event markets reflect the current relationship roster."""
    people = list(Person.objects.filter(active=True).order_by('name'))
    relationships = list(Relationship.objects.filter(active=True).select_related('person_a', 'person_b'))
    partnered = {person.id for rel in relationships for person in (rel.person_a, rel.person_b)}
    specs = {
        Market.Kind.NEXT: [(person.name, [person]) for person in people if person.id not in partnered],
        Market.Kind.COUPLE: [(f'{pair[0].name} & {pair[1].name}', list(pair)) for pair in combinations([p for p in people if p.id not in partnered], 2)],
        Market.Kind.BREAKUP: [(f'{rel.person_a.name} & {rel.person_b.name}', [rel.person_a, rel.person_b]) for rel in relationships],
    }
    titles = {
        Market.Kind.NEXT: 'Current: next person to enter a relationship',
        Market.Kind.COUPLE: 'Current: next couple to enter a relationship',
        Market.Kind.BREAKUP: 'Current: next couple to break up',
    }
    for kind, options in specs.items():
        desired = {frozenset(person.id for person in people) for _, people in options}
        market = Market.objects.filter(kind=kind, mode=Market.Mode.NEXT, status=Market.Status.OPEN,
                                       title=titles[kind]).prefetch_related('outcomes__people').first()
        current = {frozenset(person.id for person in outcome.people.all()) for outcome in (market.outcomes.all() if market else [])}
        if market and current == desired:
            continue
        Market.objects.filter(kind=kind, mode=Market.Mode.NEXT, status=Market.Status.OPEN,
                              title=titles[kind]).update(status=Market.Status.CLOSED)
        market = Market.objects.create(title=titles[kind], kind=kind, mode=Market.Mode.NEXT,
                                       description='Current valid outcomes.',
                                       closes_at=timezone.now() + timedelta(days=3650))
        for order, (label, outcome_people) in enumerate(options):
            outcome = Outcome.objects.create(market=market, label=label, order=order)
            outcome.people.set(outcome_people)
