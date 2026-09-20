from django.urls import path

from . import views

urlpatterns = [
    path("", views.order_search, name="order_search"),
    path("demo-login/", views.demo_login, name="demo_login"),
    path("new/", views.order_create, name="order_create"),
    path("import/", views.excel_import_view, name="excel_import"),
    path("export/pdf/", views.order_export_pdf, name="order_export_pdf"),
    path("<int:pk>/", views.order_detail, name="order_detail"),
    path("<int:pk>/edit/", views.order_edit, name="order_edit"),
    path("<int:pk>/delete/", views.order_delete, name="order_delete"),
]

