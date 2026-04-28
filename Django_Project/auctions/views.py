import json

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods

from .forms import AuctionFilterForm, AuctionForm, BidPlacementForm, SignupForm
from .models import Auction, AutoBid, Bid, Category, Notification, WatchlistEntry
from .services import place_bid, toggle_watchlist


def auction_base_queryset():
    return Auction.objects.select_related('seller', 'category', 'winner').annotate(
        watchers_total=Count('watchers', distinct=True),
        bids_total=Count('bids', distinct=True),
    )


def serialize_bid(bid):
    return {
        'id': bid.id,
        'bidder': bid.bidder.username,
        'amount': str(bid.amount),
        'is_auto_bid': bid.is_auto_bid,
        'created_at': bid.created_at.isoformat(),
    }


def serialize_auction(auction, include_bids=False):
    payload = {
        'id': auction.id,
        'title': auction.title,
        'description': auction.description,
        'status': auction.status,
        'status_label': auction.get_status_display(),
        'image_url': auction.image_url,
        'starting_price': str(auction.starting_price),
        'current_price': str(auction.current_price),
        'reserve_price': str(auction.reserve_price) if auction.reserve_price else None,
        'minimum_next_bid': str(auction.minimum_next_bid),
        'start_time': auction.start_time.isoformat(),
        'end_time': auction.end_time.isoformat(),
        'time_remaining_seconds': max(int((auction.end_time - timezone.now()).total_seconds()), 0),
        'seller': auction.seller.username,
        'winner': auction.winner.username if auction.winner else None,
        'category': {
            'id': auction.category_id,
            'name': auction.category.name,
            'slug': auction.category.slug,
        },
        'watchers': getattr(auction, 'watchers_total', auction.watchers.count()),
        'bids_count': getattr(auction, 'bids_total', auction.bids.count()),
    }
    if include_bids:
        payload['bids'] = [serialize_bid(bid) for bid in auction.bids.select_related('bidder')[:10]]
    return payload


def serialize_category_tree(category):
    return {
        'id': category.id,
        'name': category.name,
        'slug': category.slug,
        'children': [serialize_category_tree(child) for child in category.children.all().order_by('ordering', 'name')],
    }


def parse_request_data(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode() or '{}')
        except json.JSONDecodeError:
            return None
    return request.POST


def home(request):
    featured_live = auction_base_queryset().filter(status=Auction.Status.LIVE).order_by('end_time')[:6]
    upcoming = auction_base_queryset().filter(status=Auction.Status.SCHEDULED).order_by('start_time')[:3]
    recent_sales = auction_base_queryset().filter(status=Auction.Status.SOLD).order_by('-updated_at')[:3]
    top_categories = Category.objects.filter(parent__isnull=True).prefetch_related('children')[:4]

    context = {
        'featured_live': featured_live,
        'upcoming': upcoming,
        'recent_sales': recent_sales,
        'top_categories': top_categories,
        'live_count': Auction.objects.filter(status=Auction.Status.LIVE).count(),
        'seller_count': Auction.objects.values('seller_id').distinct().count(),
        'bid_count': Bid.objects.count(),
    }
    return render(request, 'auctions/home.html', context)


def auction_list(request):
    queryset = auction_base_queryset()
    form = AuctionFilterForm(request.GET or None)
    sort = 'ending'

    if form.is_valid():
        cleaned = form.cleaned_data
        query = cleaned.get('query')
        category = cleaned.get('category')
        min_price = cleaned.get('min_price')
        max_price = cleaned.get('max_price')
        status = cleaned.get('status')
        sort = cleaned.get('sort') or sort

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(seller__username__icontains=query)
            )
        if category:
            queryset = queryset.filter(category_id__in=category.get_descendant_ids())
        if min_price is not None:
            queryset = queryset.filter(current_price__gte=min_price)
        if max_price is not None:
            queryset = queryset.filter(current_price__lte=max_price)
        if status:
            queryset = queryset.filter(status=status)
    else:
        cleaned = {}

    if sort == 'newest':
        queryset = queryset.order_by('-created_at')
    elif sort == 'price_asc':
        queryset = queryset.order_by('current_price', 'end_time')
    elif sort == 'price_desc':
        queryset = queryset.order_by('-current_price', 'end_time')
    elif sort == 'popular':
        queryset = queryset.order_by('-watchers_total', 'end_time')
    else:
        queryset = queryset.order_by('end_time')

    paginator = Paginator(queryset, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(
        request,
        'auctions/auction_list.html',
        {
            'form': form,
            'page_obj': page_obj,
            'active_filters': cleaned,
            'querystring': query_params.urlencode(),
        },
    )


def auction_detail(request, pk):
    auction = get_object_or_404(auction_base_queryset(), pk=pk)
    recent_bids = auction.bids.select_related('bidder')[:10]
    related_auctions = auction_base_queryset().filter(category=auction.category).exclude(pk=auction.pk)[:3]
    watchlisted = False
    user_auto_bid = None

    if request.user.is_authenticated:
        watchlisted = WatchlistEntry.objects.filter(user=request.user, auction=auction).exists()
        user_auto_bid = AutoBid.objects.filter(bidder=request.user, auction=auction).first()

    bid_form = BidPlacementForm(initial={'amount': auction.minimum_next_bid})

    return render(
        request,
        'auctions/auction_detail.html',
        {
            'auction': auction,
            'recent_bids': recent_bids,
            'related_auctions': related_auctions,
            'watchlisted': watchlisted,
            'user_auto_bid': user_auto_bid,
            'bid_form': bid_form,
        },
    )


@login_required
def auction_create(request):
    if request.method == 'POST':
        form = AuctionForm(request.POST)
        if form.is_valid():
            auction = form.save(commit=False)
            auction.seller = request.user
            auction.current_price = auction.starting_price
            now = timezone.now()
            if auction.start_time <= now < auction.end_time:
                auction.status = Auction.Status.LIVE
            else:
                auction.status = Auction.Status.SCHEDULED
            auction.save()
            messages.success(request, 'Auction created successfully.')
            return redirect('auction_detail', pk=auction.pk)
    else:
        form = AuctionForm()

    return render(request, 'auctions/auction_form.html', {'form': form})


@login_required
@require_http_methods(['POST'])
def place_bid_view(request, pk):
    auction = get_object_or_404(Auction, pk=pk)
    form = BidPlacementForm(request.POST)

    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect('auction_detail', pk=pk)

    try:
        leading_bid = place_bid(
            auction,
            request.user,
            form.cleaned_data['amount'],
            form.cleaned_data['auto_bid_max'],
        )
    except ValidationError as exc:
        messages.error(request, exc.message)
    else:
        if leading_bid.bidder_id == request.user.id:
            messages.success(request, 'Your bid is in front.')
        else:
            messages.info(request, 'Bid placed. Another bidder still leads.')

    return redirect('auction_detail', pk=pk)


@login_required
@require_http_methods(['POST'])
def toggle_watchlist_view(request, pk):
    auction = get_object_or_404(Auction, pk=pk)
    added = toggle_watchlist(request.user, auction)
    if added:
        messages.success(request, 'Auction added to your watchlist.')
    else:
        messages.info(request, 'Auction removed from your watchlist.')
    return redirect('auction_detail', pk=pk)


@login_required
def dashboard(request):
    my_auctions = auction_base_queryset().filter(seller=request.user).order_by('status', '-created_at')
    active_auctions = my_auctions.filter(status__in=[Auction.Status.LIVE, Auction.Status.SCHEDULED])
    sold_auctions = my_auctions.filter(status=Auction.Status.SOLD)
    notifications = Notification.objects.filter(user=request.user).select_related('auction')[:8]
    recent_bid_activity = Bid.objects.filter(auction__seller=request.user).select_related('auction', 'bidder')[:8]

    context = {
        'my_auctions': my_auctions[:8],
        'notifications': notifications,
        'recent_bid_activity': recent_bid_activity,
        'stats': {
            'active_count': active_auctions.count(),
            'sold_count': sold_auctions.count(),
            'watchers_count': WatchlistEntry.objects.filter(auction__seller=request.user).count(),
            'revenue': sold_auctions.aggregate(total=Sum('current_price'))['total'] or 0,
        },
    }
    return render(request, 'auctions/dashboard.html', context)


@login_required
def watchlist(request):
    entries = WatchlistEntry.objects.filter(user=request.user).select_related(
        'auction__seller',
        'auction__category',
        'auction__winner',
    )
    auctions = [entry.auction for entry in entries]
    return render(request, 'auctions/watchlist.html', {'auctions': auctions})


@login_required
def my_wins(request):
    won_auctions = auction_base_queryset().filter(winner=request.user, status=Auction.Status.SOLD)
    return render(request, 'auctions/my_wins.html', {'auctions': won_auctions})


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    redirect_to = request.POST.get('next') or request.GET.get('next')
    if redirect_to and not url_has_allowed_host_and_scheme(
        url=redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        redirect_to = None

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Welcome to MazaLive.')
            return redirect(redirect_to or 'dashboard')
    else:
        form = SignupForm()

    return render(request, 'registration/signup.html', {'form': form, 'next': redirect_to})


@login_required
@require_http_methods(['POST'])
def mark_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'Notifications marked as read.')
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


@require_http_methods(['GET', 'POST'])
def api_auctions(request):
    if request.method == 'GET':
        status = request.GET.get('status', Auction.Status.LIVE)
        queryset = auction_base_queryset().filter(status=status).order_by('end_time')
        return JsonResponse({'results': [serialize_auction(auction) for auction in queryset]}, status=200)

    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=401)

    payload = parse_request_data(request)
    if payload is None:
        return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

    form = AuctionForm(payload)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors}, status=400)

    auction = form.save(commit=False)
    auction.seller = request.user
    auction.current_price = auction.starting_price
    now = timezone.now()
    auction.status = Auction.Status.LIVE if auction.start_time <= now < auction.end_time else Auction.Status.SCHEDULED
    auction.save()
    return JsonResponse({'auction': serialize_auction(auction, include_bids=True)}, status=201)


@require_GET
def api_auction_detail(request, pk):
    auction = get_object_or_404(auction_base_queryset(), pk=pk)
    return JsonResponse({'auction': serialize_auction(auction, include_bids=True)}, status=200)


@require_http_methods(['POST'])
def api_place_bid(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=401)

    payload = parse_request_data(request)
    if payload is None:
        return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

    form = BidPlacementForm(payload)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors}, status=400)

    auction = get_object_or_404(Auction, pk=pk)
    try:
        leading_bid = place_bid(
            auction,
            request.user,
            form.cleaned_data['amount'],
            form.cleaned_data['auto_bid_max'],
        )
    except ValidationError as exc:
        return JsonResponse({'detail': exc.message}, status=400)

    refreshed_auction = get_object_or_404(auction_base_queryset(), pk=pk)
    return JsonResponse(
        {
            'detail': 'Bid placed.',
            'leading_bid': serialize_bid(leading_bid),
            'auction': serialize_auction(refreshed_auction, include_bids=True),
        },
        status=201,
    )


@require_GET
def api_watchlist(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=401)

    auctions = auction_base_queryset().filter(watchers__user=request.user)
    return JsonResponse({'results': [serialize_auction(auction) for auction in auctions]}, status=200)


@require_GET
def api_won_auctions(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=401)

    auctions = auction_base_queryset().filter(winner=request.user, status=Auction.Status.SOLD)
    return JsonResponse({'results': [serialize_auction(auction) for auction in auctions]}, status=200)


@require_GET
def api_categories(request):
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('children__children').order_by('ordering', 'name')
    return JsonResponse({'results': [serialize_category_tree(category) for category in categories]}, status=200)
