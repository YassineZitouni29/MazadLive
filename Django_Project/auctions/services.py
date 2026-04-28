from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Auction, AutoBid, Bid, Notification, WatchlistEntry, compute_bid_increment, normalize_money


@dataclass
class Commitment:
    user_id: int
    max_amount: Decimal
    committed_at: timezone.datetime


def create_notification(user, auction, message):
    Notification.objects.create(user=user, auction=auction, message=message)


def sync_due_auctions(now=None):
    now = now or timezone.now()
    Auction.objects.filter(
        status=Auction.Status.SCHEDULED,
        start_time__lte=now,
        end_time__gt=now,
    ).update(status=Auction.Status.LIVE)

    due_to_close = Auction.objects.filter(
        status__in=[Auction.Status.SCHEDULED, Auction.Status.LIVE],
        end_time__lte=now,
    )
    for auction in due_to_close:
        close_auction(auction, now=now)


@transaction.atomic
def close_auction(auction, now=None):
    now = now or timezone.now()
    auction = Auction.objects.select_for_update().select_related('seller', 'winner').get(pk=auction.pk)

    if auction.status not in [Auction.Status.SCHEDULED, Auction.Status.LIVE]:
        return auction

    leading_bid = auction.leading_bid
    auction.winner = None

    if leading_bid and (auction.reserve_price is None or leading_bid.amount >= auction.reserve_price):
        auction.status = Auction.Status.SOLD
        auction.winner = leading_bid.bidder
        auction.current_price = leading_bid.amount
        create_notification(leading_bid.bidder, auction, f'You won "{auction.title}" for {leading_bid.amount} MAD.')
        if auction.seller_id != leading_bid.bidder_id:
            create_notification(auction.seller, auction, f'"{auction.title}" sold to {leading_bid.bidder.username}.')
    elif leading_bid and auction.reserve_price:
        auction.status = Auction.Status.RESERVE_NOT_MET
        auction.current_price = leading_bid.amount
        create_notification(auction.seller, auction, f'"{auction.title}" ended without reaching the reserve price.')
    else:
        auction.status = Auction.Status.ENDED
        auction.current_price = auction.starting_price
        create_notification(auction.seller, auction, f'"{auction.title}" ended without bids.')

    auction.save(update_fields=['status', 'winner', 'current_price', 'updated_at'])
    return auction


def toggle_watchlist(user, auction):
    entry, created = WatchlistEntry.objects.get_or_create(user=user, auction=auction)
    if not created:
        entry.delete()
        return False
    return True


def _normalize_optional(value):
    if value in [None, '', False]:
        return None
    return normalize_money(value)


def _build_commitments(auction):
    visible_maximums = {}
    for bid in auction.bids.order_by('created_at').values('bidder_id', 'amount', 'created_at'):
        bidder_snapshot = visible_maximums.get(bid['bidder_id'])
        if bidder_snapshot is None or bid['amount'] > bidder_snapshot['amount']:
            visible_maximums[bid['bidder_id']] = {'amount': bid['amount'], 'time': bid['created_at']}

    auto_profiles = {profile.bidder_id: profile for profile in auction.auto_bids.all()}
    commitments = []

    for bidder_id in set(visible_maximums) | set(auto_profiles):
        highest_visible = visible_maximums.get(bidder_id)
        auto_profile = auto_profiles.get(bidder_id)

        visible_amount = highest_visible['amount'] if highest_visible else Decimal('0.00')
        auto_amount = auto_profile.max_amount if auto_profile else Decimal('0.00')
        max_amount = max(visible_amount, auto_amount)

        times = []
        if highest_visible and visible_amount == max_amount:
            times.append(highest_visible['time'])
        if auto_profile and auto_amount == max_amount:
            times.append(auto_profile.updated_at)

        commitments.append(
            Commitment(
                user_id=bidder_id,
                max_amount=max_amount,
                committed_at=min(times),
            )
        )

    return sorted(commitments, key=lambda item: (-item.max_amount, item.committed_at, item.user_id))


def _resolve_leading_bid(auction):
    ranking = _build_commitments(auction)
    current_leader = auction.leading_bid
    if not ranking:
        return current_leader

    winner = ranking[0]
    visible_floor = current_leader.amount if current_leader else auction.starting_price

    if len(ranking) == 1:
        final_price = normalize_money(visible_floor)
    else:
        runner_up = ranking[1]
        proxy_price = min(
            winner.max_amount,
            normalize_money(runner_up.max_amount + compute_bid_increment(runner_up.max_amount)),
        )
        final_price = max(normalize_money(visible_floor), normalize_money(proxy_price))

    if (
        current_leader is None
        or current_leader.bidder_id != winner.user_id
        or current_leader.amount < final_price
    ):
        current_leader = Bid.objects.create(
            auction=auction,
            bidder_id=winner.user_id,
            amount=final_price,
            is_auto_bid=True,
        )

    if auction.current_price != current_leader.amount:
        auction.current_price = current_leader.amount
        auction.save(update_fields=['current_price', 'updated_at'])

    return current_leader


@transaction.atomic
def place_bid(auction, bidder, amount, auto_bid_max=None):
    amount = normalize_money(amount)
    auto_bid_max = _normalize_optional(auto_bid_max)
    now = timezone.now()

    auction = Auction.objects.select_for_update().select_related('seller', 'category').get(pk=auction.pk)

    if auction.end_time <= now:
        close_auction(auction, now=now)
        raise ValidationError('This auction has already ended.')

    if auction.start_time > now:
        raise ValidationError('This auction has not started yet.')

    if auction.status == Auction.Status.SCHEDULED:
        auction.status = Auction.Status.LIVE
        auction.save(update_fields=['status', 'updated_at'])

    if auction.seller_id == bidder.id:
        raise ValidationError("You can't bid on your own auction.")

    minimum_bid = auction.minimum_next_bid
    if amount < minimum_bid:
        raise ValidationError(f'The next valid bid is {minimum_bid} MAD or higher.')

    if auto_bid_max and auto_bid_max < amount:
        raise ValidationError('Auto-bid max must be equal to or higher than your bid.')

    previous_leader = auction.leading_bid.bidder if auction.leading_bid else None

    if auto_bid_max:
        auto_profile, created = AutoBid.objects.get_or_create(
            auction=auction,
            bidder=bidder,
            defaults={'max_amount': auto_bid_max},
        )
        auto_profile.max_amount = auto_bid_max if created else max(auto_profile.max_amount, auto_bid_max)
        auto_profile.save()

    Bid.objects.create(auction=auction, bidder=bidder, amount=amount, is_auto_bid=False)
    leading_bid = _resolve_leading_bid(auction)

    if previous_leader and leading_bid and previous_leader != leading_bid.bidder:
        create_notification(previous_leader, auction, f'You were outbid on "{auction.title}".')

    return leading_bid
