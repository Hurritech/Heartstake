from django.contrib import admin
from .models import Bet, LedgerEntry, Market, Outcome, Person, Profile, Relationship


class OutcomeInline(admin.TabularInline):
    model = Outcome
    extra = 2


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'mode', 'status', 'closes_at', 'resolves_at')
    list_filter = ('kind', 'mode', 'status')
    inlines = [OutcomeInline]


admin.site.register([Person, Relationship, Bet, Profile, LedgerEntry])
