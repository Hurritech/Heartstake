from datetime import datetime, time, timedelta
from itertools import combinations

from django.core.management.base import BaseCommand
from django.utils import timezone

from market.models import Market, Outcome, Person, Relationship


class Command(BaseCommand):
    help = 'Create demo people and relationship markets'

    def handle(self, *args, **options):
        people_data = [
            ('Max', 'MX', '#35f2d0'), ('Karo', 'KA', '#ff4d8d'),
            ('Fabian', 'FA', '#8a72c7'), ('Nalani', 'NA', '#69f59c'),
            ('Michel', 'MI', '#ffb347'), ('Kathrin', 'KT', '#4ca6ff'),
            ('Fouad', 'FO', '#df6cff'), ('Henrik', 'HE', '#48d7a4'),
            ('Zoé', 'ZO', '#ff729f'), ('Erick', 'ER', '#e7db63'),
        ]
        people = {name: Person.objects.get_or_create(name=name, defaults={'initials': initials, 'color': color})[0]
                  for name, initials, color in people_data}
        existing_couples = [
            ('Max & Karo', ['Max', 'Karo']),
            ('Fabian & Nalani', ['Fabian', 'Nalani']),
        ]
        for _, names in existing_couples:
            first, second = people[names[0]], people[names[1]]
            if not Relationship.objects.filter(active=True).filter(
                person_a__in=[first, second], person_b__in=[first, second]
            ).exists():
                Relationship.objects.create(person_a=first, person_b=second)
        existing_sets = {frozenset(names) for _, names in existing_couples}
        partnered_names = {name for pair in existing_sets for name in pair}
        single_names = [name for name in people if name not in partnered_names]
        candidate_couples = [
            (f'{first} & {second}', [first, second])
            for first, second in combinations(single_names, 2)
        ]
        specs = [
            ('Current: next person to enter a relationship', 'NEXT', 'NEXT_EVENT', 'Choose the person who will be next to confirm a relationship.', 3650,
             [(name, [name]) for name in single_names]),
            ('Current: next couple to enter a relationship', 'COUPLE', 'NEXT_EVENT', 'Choose from every unique pairing except existing couples.', 3650, candidate_couples),
            ('Current: next couple to break up', 'BREAKUP', 'NEXT_EVENT', 'Choose which existing couple will break up next.', 3650, existing_couples),
        ]
        for name, person_names in [(name, [name]) for name in single_names]:
            specs.append((
                f'Current: {name} enters a relationship within this quarter', 'NEXT', 'TIMEFRAME',
                f'Bet for or against {name} entering a relationship within this quarter.', 90,
                [('FOR', person_names), ('AGAINST', person_names)],
            ))
        for label, names in candidate_couples:
            specs.append((
                f'Current: {label} enter a relationship within this quarter', 'COUPLE', 'TIMEFRAME',
                f'Bet for or against {label} confirming a relationship within this quarter.', 90,
                [('FOR', names), ('AGAINST', names)],
            ))
        for label, names in existing_couples:
            specs.append((
                f'Current: {label} break up within this quarter', 'BREAKUP', 'TIMEFRAME',
                f'Bet for or against {label} breaking up within this quarter.', 90,
                [('FOR', names), ('AGAINST', names)],
            ))
        now = timezone.now()
        quarter = (now.month - 1) // 3
        next_quarter = datetime(now.year + (quarter == 3), (quarter + 1) % 4 * 3 + 1, 1)
        quarter_end = next_quarter.date() - timedelta(days=1)
        first_month_end = datetime(now.year, quarter * 3 + 2, 1).date() - timedelta(days=1)
        trading_end_time = timezone.make_aware(datetime.combine(first_month_end, time.max))
        quarter_end_time = timezone.make_aware(datetime.combine(quarter_end, time.max))

        for title, kind, mode, description, days, outcomes in specs:
            closing_time = trading_end_time if mode == 'TIMEFRAME' else now + timedelta(days=days)
            resolution_time = quarter_end_time if mode == 'TIMEFRAME' else None
            market, created = Market.objects.get_or_create(title=title, defaults={
                'kind': kind, 'mode': mode, 'description': description,
                'closes_at': closing_time, 'resolves_at': resolution_time,
            })
            if not created:
                market.mode = mode
                if mode == 'TIMEFRAME':
                    market.closes_at = closing_time
                    market.resolves_at = resolution_time
                    market.save(update_fields=['mode', 'closes_at', 'resolves_at'])
                else:
                    market.save(update_fields=['mode'])
            if created:
                for order, (label, names) in enumerate(outcomes):
                    outcome = Outcome.objects.create(market=market, label=label, order=order)
                    outcome.people.set([people[n] for n in names])
        self.stdout.write(self.style.SUCCESS('Demo markets are ready.'))
