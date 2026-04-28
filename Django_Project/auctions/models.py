from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


MONEY_STEP = Decimal('0.01')


def normalize_money(value):
    return Decimal(value).quantize(MONEY_STEP)


def compute_bid_increment(amount):
    amount = Decimal(amount)
    if amount < Decimal('100'):
        return Decimal('5.00')
    if amount < Decimal('500'):
        return Decimal('10.00')
    if amount < Decimal('1000'):
        return Decimal('25.00')
    return Decimal('50.00')


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children',
    )
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['parent__name', 'ordering', 'name']
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_descendant_ids(self):
        descendants = [self.pk]
        for child in self.children.all():
            descendants.extend(child.get_descendant_ids())
        return descendants


class Auction(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        LIVE = 'live', 'Live'
        SOLD = 'sold', 'Sold'
        ENDED = 'ended', 'Ended'
        RESERVE_NOT_MET = 'reserve_not_met', 'Reserve Not Met'

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='selling_auctions',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='auctions',
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    image_url = models.URLField(blank=True)
    starting_price = models.DecimalField(max_digits=10, decimal_places=2)
    reserve_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='won_auctions',
    )
    shipping_details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError('End time must be after the start time.')
        if self.reserve_price and self.reserve_price < self.starting_price:
            raise ValidationError('Reserve price must be equal to or higher than the starting price.')

    def save(self, *args, **kwargs):
        if not self.current_price:
            self.current_price = self.starting_price
        if self.status == self.Status.SCHEDULED and self.start_time <= timezone.now() < self.end_time:
            self.status = self.Status.LIVE
        super().save(*args, **kwargs)

    @property
    def has_started(self):
        return self.start_time <= timezone.now()

    @property
    def has_ended(self):
        return timezone.now() >= self.end_time

    @property
    def leading_bid(self):
        return self.bids.select_related('bidder').order_by('-amount', '-created_at').first()

    @property
    def minimum_next_bid(self):
        if not self.bids.exists():
            return normalize_money(self.starting_price)
        return normalize_money(self.current_price + compute_bid_increment(self.current_price))

    @property
    def reserve_met(self):
        if self.reserve_price is None:
            return True
        return self.current_price >= self.reserve_price

    @property
    def watchers_count(self):
        return self.watchers.count()


class Bid(models.Model):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='bids')
    bidder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bids',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_auto_bid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.bidder} on {self.auction}: {self.amount}'


class WatchlistEntry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='watchlist_entries')
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='watchers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'auction'], name='unique_watchlist_entry'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} watches {self.auction}'


class AutoBid(models.Model):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='auto_bids')
    bidder = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='auto_bids')
    max_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['auction', 'bidder'], name='unique_auto_bid_profile'),
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.bidder} auto-bids on {self.auction}'


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    auction = models.ForeignKey(
        Auction,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Notification for {self.user}'
