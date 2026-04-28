from django.contrib import admin

from .models import Auction, AutoBid, Bid, Category, Notification, WatchlistEntry


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'ordering')
    list_filter = ('parent',)
    search_fields = ('name', 'slug')
    ordering = ('parent__name', 'ordering', 'name')


class BidInline(admin.TabularInline):
    model = Bid
    extra = 0
    readonly_fields = ('bidder', 'amount', 'is_auto_bid', 'created_at')
    can_delete = False


@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'category', 'status', 'current_price', 'end_time', 'winner')
    list_filter = ('status', 'category')
    search_fields = ('title', 'description', 'seller__username')
    autocomplete_fields = ('seller', 'winner', 'category')
    inlines = [BidInline]


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ('auction', 'bidder', 'amount', 'is_auto_bid', 'created_at')
    list_filter = ('is_auto_bid',)
    search_fields = ('auction__title', 'bidder__username')
    autocomplete_fields = ('auction', 'bidder')


@admin.register(WatchlistEntry)
class WatchlistEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'auction', 'created_at')
    search_fields = ('user__username', 'auction__title')
    autocomplete_fields = ('user', 'auction')


@admin.register(AutoBid)
class AutoBidAdmin(admin.ModelAdmin):
    list_display = ('bidder', 'auction', 'max_amount', 'updated_at')
    search_fields = ('bidder__username', 'auction__title')
    autocomplete_fields = ('bidder', 'auction')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'auction', 'message', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('user__username', 'message', 'auction__title')
    autocomplete_fields = ('user', 'auction')
