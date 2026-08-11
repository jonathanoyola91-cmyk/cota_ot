from django.urls import path
from . import views

app_name = "item_oil_gas"

urlpatterns = [

    # =========================
    # ITEMS OIL & GAS
    # =========================

    path(
        "",
        views.ItemListView.as_view(),
        name="item_list"
    ),

    path(
        "nuevo/",
        views.ItemCreateView.as_view(),
        name="item_create"
    ),

    path(
        "<int:pk>/",
        views.ItemDetailView.as_view(),
        name="item_detail"
    ),

    path(
        "<int:pk>/editar/",
        views.ItemUpdateView.as_view(),
        name="item_update"
    ),

    path(
        "<int:pk>/eliminar/",
        views.ItemDeleteView.as_view(),
        name="item_delete"
    ),

    path(
        "importar/",
        views.import_items,
        name="item_import"
    ),

    path(
        "plantilla/",
        views.download_template,
        name="item_template"
    ),


    # =========================
    # ITEMS IMPETUS
    # =========================

    path(
        "impetus/",
        views.ItemImpetusListView.as_view(),
        name="item_impetus_list"
    ),

    path(
        "impetus/importar/",
        views.import_items_impetus,
        name="item_impetus_import"
    ),

    path(
        "impetus/plantilla/",
        views.download_template_impetus,
        name="item_impetus_template"
    ),
]