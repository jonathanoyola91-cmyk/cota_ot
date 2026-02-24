from django.views.generic import ListView
from historial.models import Historial


class WorkOrdersBaseHistorialListView(ListView):
    template_name = "historial/workorders_base/list.html"
    context_object_name = "items"
    paginate_by = 50

    def get_queryset(self):
        # Solo lo que venga de WorkOrders
        return (
            Historial.objects
            .filter(area="WORKORDERS")
            .select_related("content_type")
            .order_by("-closed_at")
        )