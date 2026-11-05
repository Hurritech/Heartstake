from django.urls import path
from . import views

urlpatterns = [
    path('auth/register/', views.register),
    path('auth/login/', views.login),
    path('auth/logout/', views.logout),
    path('me/', views.me),
    path('me/monthly-credit/', views.monthly_credit),
    path('markets/', views.markets),
    path('markets/<int:market_id>/', views.market_detail),
    path('markets/<int:market_id>/settle/', views.settle),
    path('bets/', views.bet),
    path('admin/people/', views.admin_people),
    path('admin/users/', views.admin_users),
    path('admin/users/<int:user_id>/', views.admin_user_detail),
    path('admin/people/<int:person_id>/', views.admin_person_detail),
    path('admin/relationships/', views.admin_relationships),
    path('admin/relationships/<int:relationship_id>/breakup/', views.admin_breakup),
]
