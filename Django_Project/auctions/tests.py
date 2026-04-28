import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Auction, Category, Notification, WatchlistEntry
from .services import close_auction, place_bid


class AuctionFlowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Electronics Test')
        self.seller = User.objects.create_user(username='seller', password='testpass123')
        self.bidder = User.objects.create_user(username='bidder', password='testpass123')
        self.rival = User.objects.create_user(username='rival', password='testpass123')
        self.auction = Auction.objects.create(
            seller=self.seller,
            category=self.category,
            title='Retro Console',
            description='Clean condition and fully functional.',
            starting_price=Decimal('100.00'),
            reserve_price=Decimal('120.00'),
            current_price=Decimal('100.00'),
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            status=Auction.Status.LIVE,
        )

    def test_manual_bid_updates_current_price(self):
        leading_bid = place_bid(self.auction, self.bidder, Decimal('130.00'))

        self.auction.refresh_from_db()

        self.assertEqual(leading_bid.bidder, self.bidder)
        self.assertEqual(self.auction.current_price, Decimal('130.00'))
        self.assertEqual(self.auction.leading_bid.bidder, self.bidder)

    def test_seller_cannot_bid_on_own_auction(self):
        with self.assertRaises(ValidationError):
            place_bid(self.auction, self.seller, Decimal('130.00'))

    def test_auto_bid_counters_manual_bid(self):
        place_bid(self.auction, self.bidder, Decimal('110.00'), Decimal('200.00'))
        leading_bid = place_bid(self.auction, self.rival, Decimal('120.00'))

        self.auction.refresh_from_db()

        self.assertEqual(leading_bid.bidder, self.bidder)
        self.assertEqual(self.auction.current_price, Decimal('130.00'))
        self.assertTrue(self.auction.bids.filter(bidder=self.bidder, is_auto_bid=True).exists())
        self.assertTrue(self.auction.bids.filter(bidder=self.rival, amount=Decimal('120.00')).exists())

    def test_closing_auction_marks_winner(self):
        place_bid(self.auction, self.bidder, Decimal('150.00'))
        self.auction.end_time = timezone.now() - timedelta(minutes=1)
        self.auction.save(update_fields=['end_time'])

        close_auction(self.auction)
        self.auction.refresh_from_db()

        self.assertEqual(self.auction.status, Auction.Status.SOLD)
        self.assertEqual(self.auction.winner, self.bidder)
        self.assertTrue(Notification.objects.filter(user=self.bidder, message__icontains='won').exists())


class AuctionApiTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Collectibles Test')
        self.seller = User.objects.create_user(username='seller', password='testpass123')
        self.viewer = User.objects.create_user(username='viewer', password='testpass123')
        self.live_auction = Auction.objects.create(
            seller=self.seller,
            category=self.category,
            title='Rare Card',
            description='Tournament legal and graded.',
            starting_price=Decimal('50.00'),
            current_price=Decimal('50.00'),
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
            status=Auction.Status.LIVE,
        )
        self.scheduled_auction = Auction.objects.create(
            seller=self.seller,
            category=self.category,
            title='Upcoming Print',
            description='Signed limited edition print.',
            starting_price=Decimal('80.00'),
            current_price=Decimal('80.00'),
            start_time=timezone.now() + timedelta(hours=2),
            end_time=timezone.now() + timedelta(days=1),
            status=Auction.Status.SCHEDULED,
        )

    def test_api_lists_live_auctions_by_default(self):
        response = self.client.get(reverse('api_auctions'))
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload['results']), 1)
        self.assertEqual(payload['results'][0]['title'], self.live_auction.title)

    def test_api_returns_watchlist_for_authenticated_user(self):
        WatchlistEntry.objects.create(user=self.viewer, auction=self.live_auction)
        self.client.force_login(self.viewer)

        response = self.client.get(reverse('api_watchlist'))
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload['results']), 1)
        self.assertEqual(payload['results'][0]['id'], self.live_auction.id)

    def test_api_can_create_auction(self):
        self.client.force_login(self.seller)
        payload = {
            'title': 'Studio Lamp',
            'category': self.category.id,
            'description': 'Warm light and adjustable neck.',
            'image_url': 'https://example.com/lamp.jpg',
            'starting_price': '120.00',
            'reserve_price': '160.00',
            'start_time': (timezone.now() + timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M'),
            'end_time': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            'shipping_details': 'Ships nationwide.',
        }

        response = self.client.post(
            reverse('api_auctions'),
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(Auction.objects.filter(title='Studio Lamp', seller=self.seller).exists())

    def test_html_pages_render(self):
        home_response = self.client.get(reverse('home'))
        detail_response = self.client.get(reverse('auction_detail', args=[self.live_auction.pk]))
        browse_response = self.client.get(reverse('auction_list'))

        self.assertEqual(home_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(browse_response.status_code, 200)
