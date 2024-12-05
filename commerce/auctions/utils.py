import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

def sync_to_stripe_if_applicable(listing):
    if not listing.active and listing.number_of_bids > 0 and not listing.synced_to_stripe:
        try:
            stripe_product = stripe.Product.create(
                name=listing.title,
                description=listing.description,
                images=[listing.photo],  # Include the photo if available
            )
            stripe_price = stripe.Price.create(
                product=stripe_product['id'],
                unit_amount=int(listing.starting_bid * 100),  # Convert to cents
                currency="usd",
            )
            listing.synced_to_stripe = True
            listing.save()
        except Exception as e:
            print(f"Error syncing to Stripe: {e}")
