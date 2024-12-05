from django.contrib import admin

from .models import User, Listings, Bids, Comments, Watchlist

from .utils import sync_to_stripe_if_applicable

@admin.action(description="Sync selected auctions to Stripe")
def sync_auctions_to_stripe(modeladmin, request, queryset):
    for listing in queryset:
        sync_to_stripe_if_applicable(listing)

@admin.register(Listings)
class ListingsAdmin(admin.ModelAdmin):
    list_display = ("title", "active", "number_of_bids", "synced_to_stripe")
    actions = [sync_auctions_to_stripe]

# Register your models here.
admin.site.register(User)
admin.site.register(Bids)
admin.site.register(Comments)
admin.site.register(Watchlist)