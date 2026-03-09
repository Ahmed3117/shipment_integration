from rest_framework.pagination import PageNumberPagination

class CustomPageNumberPagination(PageNumberPagination):
    page_size = 100 # Default page size
    page_size_query_param = 'per_page'  # Query parameter for custom page size
    max_page_size = 100000  # Maximum allowed page size

    def get_page_size(self, request):
        page_size = request.query_params.get(self.page_size_query_param)
        if page_size is None:
            page_size = request.query_params.get('page_size')
        if page_size is None:
            return self.page_size
        try:
            page_size = int(page_size)
        except (TypeError, ValueError):
            return self.page_size

        if page_size <= 0:
            return self.page_size

        if self.max_page_size:
            return min(page_size, self.max_page_size)

        return page_size