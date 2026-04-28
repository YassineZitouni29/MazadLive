from datetime import timedelta

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Auction, Category


INPUT_CLASS = 'form-control'
SELECT_CLASS = 'form-select'
TEXTAREA_CLASS = 'form-control form-control-textarea'


class SignupForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT_CLASS


class AuctionForm(forms.ModelForm):
    start_time = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': INPUT_CLASS}),
    )
    end_time = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': INPUT_CLASS}),
    )

    class Meta:
        model = Auction
        fields = [
            'title',
            'category',
            'description',
            'image_url',
            'starting_price',
            'reserve_price',
            'start_time',
            'end_time',
            'shipping_details',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Vintage chair, signed artwork, console, ...'}),
            'category': forms.Select(attrs={'class': SELECT_CLASS}),
            'description': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 6}),
            'image_url': forms.URLInput(attrs={'class': INPUT_CLASS, 'placeholder': 'https://...'}),
            'starting_price': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01', 'min': '0'}),
            'reserve_price': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01', 'min': '0'}),
            'shipping_details': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.select_related('parent').order_by('parent__name', 'ordering', 'name')
        if not self.is_bound:
            now = timezone.localtime().replace(second=0, microsecond=0)
            self.initial.setdefault('start_time', now)
            self.initial.setdefault('end_time', now + timedelta(days=3))


class BidPlacementForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01', 'min': '0'}),
    )
    auto_bid_max = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        widget=forms.NumberInput(
            attrs={
                'class': INPUT_CLASS,
                'step': '0.01',
                'min': '0',
                'placeholder': 'Optional ceiling for auto-bidding',
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        auto_bid_max = cleaned_data.get('auto_bid_max')
        if amount and auto_bid_max and auto_bid_max < amount:
            self.add_error('auto_bid_max', 'Auto-bid max must be equal to or higher than your bid.')
        return cleaned_data


class AuctionFilterForm(forms.Form):
    STATUS_CHOICES = [
        ('', 'All statuses'),
        (Auction.Status.LIVE, 'Live'),
        (Auction.Status.SCHEDULED, 'Scheduled'),
        (Auction.Status.SOLD, 'Sold'),
        (Auction.Status.ENDED, 'Ended'),
        (Auction.Status.RESERVE_NOT_MET, 'Reserve Not Met'),
    ]
    SORT_CHOICES = [
        ('ending', 'Ending soon'),
        ('newest', 'Newest first'),
        ('price_asc', 'Price: low to high'),
        ('price_desc', 'Price: high to low'),
        ('popular', 'Most watched'),
    ]

    query = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Search auctions'}))
    category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        required=False,
        empty_label='All categories',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    min_price = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01', 'min': '0'}),
    )
    max_price = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01', 'min': '0'}),
    )
    status = forms.ChoiceField(required=False, choices=STATUS_CHOICES, widget=forms.Select(attrs={'class': SELECT_CLASS}))
    sort = forms.ChoiceField(required=False, choices=SORT_CHOICES, widget=forms.Select(attrs={'class': SELECT_CLASS}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.select_related('parent').order_by('parent__name', 'ordering', 'name')
        if not self.is_bound:
            self.initial['sort'] = 'ending'
