import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .auth import api_auth
from .models import Bet, LedgerEntry, Market, Notification, Outcome, Person, Profile, Relationship
from .services import current_quarter_window, place_bet, resolve_market, resolve_relationship_markets, sync_next_event_markets


def body(request):
    try:
        return json.loads(request.body or '{}')
    except json.JSONDecodeError:
        raise ValueError('Invalid JSON.')


def user_json(user):
    return {'username': user.username, 'balance': str(user.profile.balance), 'is_admin': user.is_staff}


def market_json(market, user=None):
    closes_at, resolves_at = current_quarter_window() if market.mode == Market.Mode.TIMEFRAME and market.resolves_at else (market.closes_at, market.resolves_at)
    pool = sum((o.pool or Decimal('0')) for o in market.outcomes.all())
    outcomes = []
    for outcome in market.outcomes.all():
        outcome_pool = outcome.pool or Decimal('0')
        # With no bets there is no market-implied probability yet.
        probability = float(outcome_pool / pool * 100) if pool else None
        outcomes.append({
            'id': outcome.id, 'label': outcome.label, 'pool': str(outcome_pool),
            'probability': round(probability, 1) if probability is not None else None,
            'people': [{'name': p.name, 'initials': p.initials, 'color': p.color} for p in outcome.people.all()],
        })
    return {
        'id': market.id, 'title': market.title, 'description': market.description,
        'kind': market.kind, 'mode': market.mode, 'status': market.status, 'closes_at': closes_at.isoformat(),
        'resolves_at': resolves_at.isoformat() if resolves_at else None,
        'pool': str(pool), 'outcomes': outcomes,
        'winning_outcome_id': market.winning_outcome_id,
    }


@csrf_exempt
@require_POST
def register(request):
    try:
        data = body(request)
        username = data.get('username', '').strip()
        password = data.get('password', '')
        if len(username) < 3 or len(password) < 8:
            raise ValueError('Use a username of 3+ characters and password of 8+ characters.')
        with transaction.atomic():
            is_first_user = not User.objects.exists()
            user = User.objects.create_user(username=username, password=password, is_staff=is_first_user, is_superuser=is_first_user)
        return JsonResponse({'token': user.api_token.key, 'user': user_json(user)}, status=201)
    except (ValueError, IntegrityError) as exc:
        message = 'Username is already taken.' if isinstance(exc, IntegrityError) else str(exc)
        return JsonResponse({'error': message}, status=400)


@csrf_exempt
@require_POST
def login(request):
    try:
        data = body(request)
        user = authenticate(username=data.get('username'), password=data.get('password'))
        if not user:
            raise ValueError('Incorrect username or password.')
        return JsonResponse({'token': user.api_token.key, 'user': user_json(user)})
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@csrf_exempt
@require_POST
@api_auth
def logout(request):
    token = request.user.api_token
    token.key = __import__('secrets').token_hex(32)
    token.save(update_fields=['key'])
    return JsonResponse({'ok': True})


@require_GET
def markets(request):
    sync_next_event_markets()
    qs = Market.objects.filter(status=Market.Status.OPEN).annotate_outcome_pools()
    return JsonResponse({'markets': [market_json(m) for m in qs]})


@require_GET
def market_detail(request, market_id):
    qs = Market.objects.annotate_outcome_pools()
    try:
        return JsonResponse({'market': market_json(qs.get(pk=market_id))})
    except Market.DoesNotExist:
        return JsonResponse({'error': 'Market not found.'}, status=404)


@require_GET
@api_auth
def me(request):
    bets = Bet.objects.filter(user=request.user).select_related('outcome__market').order_by('-created_at')[:20]
    ledger = LedgerEntry.objects.filter(user=request.user)[:20]
    notifications = list(Notification.objects.filter(user=request.user, read_at__isnull=True).values('id', 'message', 'created_at'))
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
    return JsonResponse({
        'user': user_json(request.user),
        'notifications': notifications,
        'bets': [{'id': b.id, 'market': b.outcome.market.title, 'outcome': b.outcome.label,
                  'amount': str(b.amount), 'payout': str(b.payout), 'created_at': b.created_at.isoformat()} for b in bets],
        'ledger': [{'amount': str(e.amount), 'reason': e.reason, 'created_at': e.created_at.isoformat()} for e in ledger],
    })


@csrf_exempt
@require_POST
@api_auth
def bet(request):
    try:
        data = body(request)
        outcome = Outcome.objects.select_related('market').get(pk=data.get('outcome_id'))
        placed = place_bet(request.user, outcome, data.get('amount'))
        request.user.profile.refresh_from_db()
        return JsonResponse({'bet_id': placed.id, 'balance': str(request.user.profile.balance)}, status=201)
    except (ValueError, Outcome.DoesNotExist, TypeError) as exc:
        return JsonResponse({'error': str(exc) if not isinstance(exc, Outcome.DoesNotExist) else 'Outcome not found.'}, status=400)


@csrf_exempt
@require_POST
@api_auth
def monthly_credit(request):
    today = date.today()
    with transaction.atomic():
        profile = Profile.objects.select_for_update().get(user=request.user)
        last = profile.last_monthly_credit
        if (last.year, last.month) == (today.year, today.month):
            return JsonResponse({'error': 'Monthly credits already claimed.'}, status=400)
        profile.balance += Decimal('250.00')
        profile.last_monthly_credit = today
        profile.save(update_fields=['balance', 'last_monthly_credit'])
        LedgerEntry.objects.create(user=request.user, amount=250, reason='Monthly credit grant')
    return JsonResponse({'balance': str(profile.balance)})


@csrf_exempt
@require_POST
@api_auth
def settle(request, market_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Staff only.'}, status=403)
    try:
        data = body(request)
        market = Market.objects.get(pk=market_id)
        outcome = Outcome.objects.get(pk=data.get('outcome_id'))
        resolve_market(market, outcome)
        return JsonResponse({'ok': True})
    except (Market.DoesNotExist, Outcome.DoesNotExist, ValueError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)


def admin_required(view):
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            return JsonResponse({'error': 'Administrator access required.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


@csrf_exempt
@api_auth
@admin_required
def admin_people(request):
    if request.method == 'GET':
        people = Person.objects.filter(active=True).order_by('name')
        relationships = Relationship.objects.filter(active=True).select_related('person_a', 'person_b')
        return JsonResponse({
            'people': [{'id': person.id, 'name': person.name, 'initials': person.initials, 'color': person.color} for person in people],
            'relationships': [{'id': rel.id, 'person_a': {'id': rel.person_a_id, 'name': rel.person_a.name},
                               'person_b': {'id': rel.person_b_id, 'name': rel.person_b.name},
                               'started_at': rel.started_at.isoformat()} for rel in relationships],
        })
    if request.method == 'POST':
        try:
            data = body(request)
            name = data.get('name', '').strip()
            if not name:
                raise ValueError('Name is required.')
            initials = ''.join(part[0] for part in name.split())[:3].upper()
            person, created = Person.objects.get_or_create(name=name, defaults={'initials': initials or name[:2].upper(), 'color': '#35f2d0'})
            if not created:
                person.active = True
                person.save(update_fields=['active'])
            return JsonResponse({'id': person.id, 'name': person.name}, status=201)
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)
    return JsonResponse({'error': 'Method not allowed.'}, status=405)


@csrf_exempt
@api_auth
@admin_required
def admin_users(request):
    if request.method == 'GET':
        users = User.objects.all().order_by('username')
        return JsonResponse({'users': [
            {'id': user.id, 'username': user.username, 'is_admin': user.is_staff, 'is_active': user.is_active,
             'person_id': user.profile.person_id,
             'balance': str(user.profile.balance),
             'date_joined': user.date_joined.isoformat()}
            for user in users
        ]})
    return JsonResponse({'error': 'Method not allowed.'}, status=405)


@csrf_exempt
@api_auth
@admin_required
def admin_user_detail(request, user_id):
    try:
        target = User.objects.get(pk=user_id)
        if request.method == 'DELETE':
            if target == request.user:
                return JsonResponse({'error': 'You cannot remove your own admin account.'}, status=400)
            target.delete()
            return JsonResponse({'ok': True})
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed.'}, status=405)
        data = body(request)
        if 'person_id' in data:
            person_id = data['person_id'] or None
            if person_id is not None:
                person = Person.objects.get(pk=person_id, active=True)
                if Profile.objects.filter(person=person).exclude(user=target).exists():
                    raise ValueError('That person is already connected to another account.')
            target.profile.person_id = person_id
            target.profile.save(update_fields=['person'])
        if target == request.user and set(data) - {'person_id', 'balance'}:
            raise ValueError('You cannot change your own admin account.')
        if 'is_active' in data:
            target.is_active = bool(data['is_active'])
        if 'is_admin' in data:
            target.is_staff = bool(data['is_admin'])
            target.is_superuser = False
        if 'balance' in data:
            try:
                new_balance = Decimal(str(data['balance']))
            except Exception as exc:
                raise ValueError('Credits must be a valid number.') from exc
            if new_balance < 0:
                raise ValueError('Credits cannot be negative.')
            profile = Profile.objects.select_for_update().get(user=target)
            difference = new_balance - profile.balance
            profile.balance = new_balance
            profile.save(update_fields=['balance'])
            if difference:
                LedgerEntry.objects.create(user=target, amount=difference, reason='Admin credit adjustment')
        if not target.is_active and target.is_staff:
            target.is_staff = False
            target.is_superuser = False
        target.save(update_fields=['is_active', 'is_staff', 'is_superuser'])
        return JsonResponse({'ok': True})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found.'}, status=404)
    except Person.DoesNotExist:
        return JsonResponse({'error': 'Person not found.'}, status=404)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@csrf_exempt
@api_auth
@admin_required
def admin_person_detail(request, person_id):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    try:
        with transaction.atomic():
            person = Person.objects.select_for_update().get(pk=person_id, active=True)
            Relationship.objects.filter(active=True).filter(
                Q(person_a=person) | Q(person_b=person)
            ).update(active=False, ended_at=timezone.now())
            person.active = False
            person.save(update_fields=['active'])
        return JsonResponse({'ok': True})
    except Person.DoesNotExist:
        return JsonResponse({'error': 'Person not found.'}, status=404)


@csrf_exempt
@require_POST
@api_auth
@admin_required
def admin_relationships(request):
    try:
        data = body(request)
        first = Person.objects.get(pk=data.get('person_a_id'), active=True)
        second = Person.objects.get(pk=data.get('person_b_id'), active=True)
        if first.id == second.id:
            raise ValueError('Choose two different people.')
        occupied = Relationship.objects.filter(active=True).filter(
            Q(person_a__in=[first, second]) | Q(person_b__in=[first, second])
        ).exists()
        if occupied:
            raise ValueError('One of these people is already in an active relationship.')
        rel = Relationship.objects.create(person_a=first, person_b=second)
        for person in (first, second):
            resolve_relationship_markets([person], Market.Kind.NEXT)
        resolve_relationship_markets([first, second], Market.Kind.COUPLE)
        return JsonResponse({'id': rel.id}, status=201)
    except Person.DoesNotExist:
        return JsonResponse({'error': 'Person not found.'}, status=404)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@csrf_exempt
@require_POST
@api_auth
@admin_required
def admin_breakup(request, relationship_id):
    try:
        rel = Relationship.objects.get(pk=relationship_id, active=True)
        rel.active = False
        rel.ended_at = timezone.now()
        rel.save(update_fields=['active', 'ended_at'])
        resolve_relationship_markets([rel.person_a, rel.person_b], Market.Kind.BREAKUP)
        return JsonResponse({'ok': True})
    except Relationship.DoesNotExist:
        return JsonResponse({'error': 'Active relationship not found.'}, status=404)
