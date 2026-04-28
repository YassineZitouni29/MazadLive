from .services import sync_due_auctions


class AuctionLifecycleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith('/static/'):
            sync_due_auctions()
        return self.get_response(request)
