from django.urls import path

from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('auctions/', views.auction_list, name='auction_list'),
    path('auctions/create/', views.auction_create, name='auction_create'),
    path('auctions/<int:pk>/', views.auction_detail, name='auction_detail'),
    path('auctions/<int:pk>/bid/', views.place_bid_view, name='place_bid'),
    path('auctions/<int:pk>/watchlist/', views.toggle_watchlist_view, name='toggle_watchlist'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('watchlist/', views.watchlist, name='watchlist'),
    path('wins/', views.my_wins, name='my_wins'),
    path('notifications/read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('api/auctions/', views.api_auctions, name='api_auctions'),
    path('api/auctions/<int:pk>/', views.api_auction_detail, name='api_auction_detail'),
    path('api/auctions/<int:pk>/bid/', views.api_place_bid, name='api_place_bid'),
    path('api/users/me/watchlist/', views.api_watchlist, name='api_watchlist'),
    path('api/users/me/won/', views.api_won_auctions, name='api_won_auctions'),
    path('api/categories/', views.api_categories, name='api_categories'),
]
