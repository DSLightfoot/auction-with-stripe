import stripe
from django.core.management.base import BaseCommand
from auctions.models import Listings

stripe.api_key = "sk_test_51QS8wMFChGDc4VLV296hGbtiaphTckhmnpjtMHhWwnxHrUisI7SUUGiZ8f9bnSNfhPGVyCMBPdNcuSSNuB9LisfW00JmcEyxAx"

class Command(BaseCommand):
    help = "Sync ended auctions with bids to Stripe as products"

    def handle(self, *args, **kwargs):
        # Query all eligible listings
        listings_to_sync = Listings.objects.filter(
            active=False,  # Auction has ended
            number_of_bids__gt=0,  # At least one bid
            synced_to_stripe=False  # Not yet synced to Stripe
        )

        for listing in listings_to_sync:
            try:
                # Create Stripe product
                stripe_product = stripe.Product.create(
                    name=listing.title,
                    description=listing.description
                )

                # Create Stripe price
                stripe_price = stripe.Price.create(
                    product=stripe_product['id'],
                    unit_amount=int(listing.starting_bid * 100),  # Convert to cents
                    currency="usd"
                )

                # Mark listing as synced
                listing.synced_to_stripe = True
                listing.save()

                self.stdout.write(
                    self.style.SUCCESS(f"Successfully synced listing: {listing.title}")
                )

            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Error syncing listing {listing.title}: {e}")
                )
