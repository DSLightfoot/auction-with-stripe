from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from sqlite3 import OperationalError


import stripe
from django.conf import settings
from .utils import sync_to_stripe_if_applicable
stripe.api_key = settings.STRIPE_SECRET_KEY

import uuid

from .models import User, Listings, Bids, Comments, Watchlist


def index(request):
    user = request.user.get_username()
    number_of_watched_items = number_watched_items(user)

    return render(request, "auctions/index.html", {
        "auctions": Listings.objects.all(),
        "watchlist": Watchlist.objects.all(),
        "number_of_watched_items": number_of_watched_items
    })


def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "auctions/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "auctions/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        if not email:
            return render(request, "auctions/register.html", {
                "message": "Must Attatch an Email Account"
            })

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "auctions/register.html", {
                "message": "Passwords must match."
            })
        
        if not password:
            return render(request, "auctions/register.html", {
                "message": "Must Input a Password"
            })
        

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "auctions/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "auctions/register.html")

def newListing(request):
    if request.method == "POST":
        title = request.POST["title"]
        description = request.POST["description"]
        url = request.POST["url"]
        category = request.POST["category"]
        starting_bid = request.POST["starting_bid"]

        unique_id = uuid.uuid1()
        print(unique_id)

        user = request.user.get_username()
        user = User.objects.get(username=user)
        number_of_watched_items = number_watched_items(user)

        if not title:
            return render(request, "auctions/newListing.html", {
        "message": "Title Needed",
        "number_of_watched_items": number_of_watched_items
        })

        if not description:
            return render(request, "auctions/newListing.html", {
        "message": "Description Needed",
        "number_of_watched_items": number_of_watched_items
        })

        if not url and not category:
            return render(request, "auctions/newListing.html", {
        "message": "Url and/or Category Needed",
        "number_of_watched_items": number_of_watched_items
        })

        if not starting_bid:
            return render(request, "auctions/newListing.html", {
        "message": "Starting Bids Needed",
        "number_of_watched_items": number_of_watched_items
        })


        if category and url:
            new_listing = Listings(lister=user, listings_id=unique_id, title=title, description=description, photo=url, category=category, starting_bid=starting_bid, number_of_bids=0)
            new_listing.save()
        
        if not url:
            new_listing = Listings(lister=user, listings_id=unique_id, title=title, description=description, category=category, starting_bid=starting_bid, number_of_bids=0)
            new_listing.save()
        
        if not category:
            new_listing = Listings(lister=user, listings_id=unique_id, title=title, description=description, photo=url, starting_bid=starting_bid, number_of_bids=0)
            new_listing.save()

        
        return HttpResponseRedirect(reverse("index"))
    
    else:
        user = request.user.get_username()
        number_of_watched_items = number_watched_items(user)

        return render(request, "auctions/newListing.html", {
            "number_of_watched_items": number_of_watched_items
        })
    

def listing(request, listing_id):
    user = request.user.get_username()

    try:
        user_object = User.objects.get(username=user)
    except User.DoesNotExist:
        user_object = None


    number_of_watched_items = number_watched_items(user)
    listing = Listings.objects.get(listing_id=listing_id)
    print(listing)
    end_auction = False

    if user_object == listing.lister:
        end_auction = True
        
    try:
        watchers_list = Watchlist.objects.get(listing=listing)
        number_of_watchers = watchers_list.watcher.count()
    except ObjectDoesNotExist:
        number_of_watchers = 0

    try: 
        bids_info = Bids.objects.filter(listing=listing).latest('id')
    except ObjectDoesNotExist:
        bids_info = None
    
    comments_info = Comments.objects.filter(listing=listing)

    #Returns all of the info of the listings model. Title, Description, Photo Url, Category, and Starting Bids
    return render(request, "auctions/auctions.html", {
        "listing_info": Listings.objects.get(listing_id=listing_id),
        "bid_info": bids_info,
        "comment_info": comments_info,
        "number_of_watchers": number_of_watchers,
        "number_of_watched_items": number_of_watched_items,
        "end_auction": end_auction,
        "winner": listing.winner,
        "STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY,
    })

def end_auction(request, listing_id):
    auction = Listings.objects.get(listing_id=listing_id)
    auction.active = False
    auction.save()
    sync_to_stripe_if_applicable(auction)

    user = request.user.get_username()
    number_of_watched_items = number_watched_items(user)
    comments_info = Comments.objects.filter(listing=auction)

    try:
        watchers_list = Watchlist.objects.get(listing=auction)
        number_of_watchers = watchers_list.watcher.count()
    except ObjectDoesNotExist:
        number_of_watchers = 0

    try: 
        bids_info = Bids.objects.filter(listing=auction).latest('id')
    except ObjectDoesNotExist:
        bids_info = None

    try:
        user_object = User.objects.get(username=user)
    except User.DoesNotExist:
        user_object = None

    try:
        listing.winner = Bids.objects.filter(listing=auction).latest('id').bidder
    except ObjectDoesNotExist:
        listing.winner = None
    

    return render(request, "auctions/end_auction.html", {
        "end_message": "Congratulations! Your auction has successfully ended!",
        "win_message": "Congratulations! You have won this item!",
        "listing_info": auction,
        "bid_info": bids_info,
        "comment_info": comments_info,
        "number_of_watchers": number_of_watchers,
        "number_of_watched_items": number_of_watched_items,
        "user": user_object
    })

def new_bid(request):
    user = request.user.get_username()
    number_of_watched_items = number_watched_items(user)

    if request.method == "POST":
        try:
            #Get User objects
            user_object = User.objects.get(username=user)
        
        except User.DoesNotExist:
            return render(request, "auctions/login.html", {
                "message": "Must be Logged in to Place Bidss"
            })
        
        
        listing_id = request.POST["listing_id"]
        new_bid = request.POST["bid"]
        listing = Listings.objects.get(listing_id=listing_id)


        # We need to make the new bids into a float (originally a string)
        new_bid = float(new_bid)

        if user_object == listing.lister:
            try:
                return render(request, "auctions/auctions.html",{
                    "listing_info": Listings.objects.get(listing_id=listing_id),
                    "bid_info": Bids.objects.filter(listing=listing).latest('id'),
                    "message": "Cannot bids on your own listingss",
                    "number_of_watched_items": number_of_watched_items
                })
            except ObjectDoesNotExist:
                return render(request, "auctions/auctions.html",{
                    "listing_info": Listings.objects.get(listing_id=listing_id),
                    "bid_info": None,
                    "message": "Cannot bids on your own listingss",
                    "number_of_watched_items": number_of_watched_items
                })

        # We then need to compare the new bids passed to the current bids
        # If the new bids is greater update if not error
        if new_bid <= listing.starting_bid:
            return render(request, "auctions/auctions.html", {
                "listing_info": Listings.objects.get(listing_id=listing_id),
                "bid_info": Bids.objects.filter(listing=listing).latest('id'),
                "message": "New Bids MUST be larger than current bids",
                "number_of_watched_items": number_of_watched_items
            })

        #Now that all of the bids info has been gotten, make a bids object then save it
        bids_object = Bids(bidder=user_object, bids_amount=new_bid, listings=listing)
        bids_object.save()

        #TODO Make User info model work

        # Increase number of bidss
        listing.number_of_bids = listing.number_of_bids + 1
        listing.save()

        #Assign and save new bids
        listing.starting_bid = new_bid
        listing.save()

        
        return render(request, "auctions/auctions.html", {
            "listing_info": Listings.objects.get(listing_id=listing_id),
            "bid_info": Bids.objects.filter(listing=listing).latest('id'),
            "comment_info": Comments.objects.filter(listing=listing),
            "number_of_watched_items": number_of_watched_items
            })
    
    
    return render(request, "auctions/auctions.html", {
        "listing_info": Listings.objects.get(listing_id=listing_id),
        "bid_info": Bids.objects.filter(listing=listing).latest('id'),
        "comment_info": Comments.objects.filter(listing=listing),
        "number_of_watched_items": number_of_watched_items
    })


def category_view(request):
    # Make a new list of all of the non repeating categories
    category_list = []
    for objects in Listings.objects.all():
        # if object in category_list:
        if objects.category not in category_list:
            category_list.append(objects.category)

    user = request.user.get_username()
    number_of_watched_items = number_watched_items(user)

    return render(request, "auctions/category_list.html", {
        "info": category_list,
        "number_of_watched_items": number_of_watched_items
    })

def watchlist(request):
    #What we should do is see if the we get a post request
    #If we do check if the user already watches the item, if they do delete it
    #If they dont create a new object with their credentials
    
    #If it is a get request, go filter the objects that have the users username and display
    try: 
        user = request.user.get_username()
        user_object = User.objects.get(username=user)
    except User.DoesNotExist:
        return render(request, "auctions/login.html", {
            "message": "Cannot Watch an Item Without Being Logged In"
        })

    if request.method == "POST":
        listing_id = request.POST["listing_id"]
        listing = Listings.objects.get(listing_id=listing_id)
        Watchlist.objects.filter(listing=listing).filter(watcher=user_object.id)

        if not Watchlist.objects.filter(listing=listing):
            obj = Watchlist(listing=listing, addRemove=True)
            obj.save()

        if not Watchlist.objects.filter(listing=listing).filter(watcher=user_object.id):
            watchlist_object = Watchlist.objects.get(listing=listing)
            watchlist_object.watcher.add(user_object)
            

        else:
            for objects in Watchlist.objects.filter(listing=listing).filter(watcher=user_object.id):
                obj = Watchlist.objects.get(listing=listing)
                obj.watcher.remove(user_object.id)

    number_of_watched_items = number_watched_items(user)

    try:
        return render(request, "auctions/watchlist.html", {
            "watchlist_items": Watchlist.objects.filter(watcher=user_object),
            "number_of_watched_items": number_of_watched_items
        })
        
    except OperationalError:
        return render(request, "auctions/watchlist.html", {
            "watchlist_items": None,
            "number_of_watched_items": number_of_watched_items
        })
    
def category_listings(request, category):
    user = request.user.get_username()
    number_of_watched_items = number_watched_items(user)

    return render(request, "auctions/category.html", {
        "listing": Listings.objects.filter(category=category),
        "category": category,
        "number_of_watched_items": number_of_watched_items
    })

def search(request):
    user = request.user.get_username()
    number_of_watched_items = number_watched_items(user)

    if request.method == "POST":
        query = request.POST["query"]
        objects = Listings.objects.all()

        titles = []

        for listings in objects:
            if query.lower() in listings.title.lower():
                titles.append(listings)
            

        return render(request, "auctions/search.html", {
            "query": titles,
            "number_of_watched_items": number_of_watched_items
        })
    
    else:
        return render(request, "auctions/index.html", {
            "number_of_watched_items": number_of_watched_items
        })
    
def user_profile(request, user):
    user_info = User.objects.get(username=user)
    user = request.user.get_username()
    
    signed_in_user = request.user.get_username()
    number_of_watched_items = number_watched_items(signed_in_user)
    listings = Listings.objects.filter(lister=user_info.id)
    active_listings = []
    ended_listings = []
    won_listings = []

    for listing in listings:
        if listing.active == True:
            active_listings.append(listing)
        else:
            ended_listings.append(listing)

    for listing in Listings.objects.all():
        if listing.number_of_bids > 0:
            bids_info = Bids.objects.filter(listing=listing).latest('id')
            if bids_info.bidder == user_info:
                won_listings.append(listing)


    return render(request, "auctions/user_profile.html", {
        "active_listings": active_listings,
        "ended_listings": ended_listings,
        "won_listings": won_listings,
        "user_info": user_info,
        "current_user": user,
        "number_of_watched_items": number_of_watched_items
    })


def new_comment(request):
    user = request.user.get_username()

    if request.method == "POST":
        try: 
            user_object = User.objects.get(username=user)
        except User.DoesNotExist:
            return render(request, "auctions/login.html", {
                "message": "Cannot Comments on an Item Without Being Logged In"
            })

        comment_content = request.POST["comment_content"]
        listing_id = request.POST["listing_id"]
        listing = Listings.objects.get(listing_id=listing_id)
        number_of_watched_items = number_watched_items(user)
        
        if comment_content == "":
            return render(request, "auctions/auctions.html", {
                "listing_info": Listings.objects.get(listing_id=listing_id),
                "bid_info": Bids.objects.filter(listing=listing).latest('id'),
                "comment_info": Comments.objects.filter(listing=listing),
                "comment_message": "A Comments MUST be Longer than 0 Characters",
                "number_of_watched_items": number_of_watched_items
            })
        
        new_comment = Comments(commenter=user_object, comment=comment_content, listings=listing)
        new_comment.save()

        return render(request, "auctions/auctions.html", {
            "listing_info": Listings.objects.get(listing_id=listing_id),
            "bid_info": Bids.objects.filter(listing=listing).latest('id'),
            "comment_info": Comments.objects.filter(listing=listing),
            "number_of_watched_items": number_of_watched_items,
        })

    return HttpResponseRedirect(reverse("index"))

################################################
##########      HELPER FUNCTIONS      ##########
################################################

def number_watched_items(user):
    number_of_watched_items = 0
    try:
        user = User.objects.get(username=user)
        watchlist_object = Watchlist.objects.filter(watcher=user)
        number_of_watched_items = watchlist_object.count()
    except User.DoesNotExist:
        number_of_watched_items = 0

    return number_of_watched_items


def pay_for_listing(request, listing_id):
    listing = get_object_or_404(Listings, pk=listing_id)

    if listing.active or listing.number_of_bids == 0 or listing.paid:
        return JsonResponse({'error': 'This listings cannot be paid for.'}, status=400)

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': listing.title,
                        'description': listing.description,
                        'images': [listing.photo],  # Use listings photo URL
                    },
                    'unit_amount': int(listing.starting_bid * 100),  # Convert to cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"http://127.0.0.1:8000/payment-success/{listing.listing_id}/",
            cancel_url=f"http://127.0.0.1:8000/payment-cancel/{listing.listing_id}/",
        )
        return JsonResponse({'id': checkout_session.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
# Success View
def payment_success(request, listing_id):
    listings = get_object_or_404(Listings, pk=listing_id)
    if not listings.paid:  # Ensure idempotency
        listings.paid = True
        listings.save()
    return render(request, "auctions/payment_success.html", {"listing": listings})

# Cancel View
def payment_cancel(request, listing_id):
    listings = get_object_or_404(Listings, pk=listing_id)
    return render(request, "auctions/payment_cancel.html", {"listing": listings})