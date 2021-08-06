from .models import Category

#in this class, it returns dictionaries (including category links) to be merged into a
# template context.
def menu_links(request):
    links = Category.objects.all() #grab all categories list and store them
    return dict(links=links)