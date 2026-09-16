"""الأقسام والمدن والأحياء — قراءة مفتوحة للزائر، وكتابة للإدارة."""

from django.db.models import Count, Prefetch, Q
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.core.permissions import IsStaffRole

from .models import Category, City, Neighborhood
from .queries import CATEGORY_ORDER, category_tree_queryset
from .serializers import (
    CategorySerializer,
    CategoryWriteSerializer,
    CityWriteSerializer,
    CitySerializer,
    NeighborhoodSerializer,
    NeighborhoodWriteSerializer,
)


@extend_schema(summary="الأقسام مع أقسامها الفرعية وعدد الإعلانات")
@api_view(["GET"])
@permission_classes([AllowAny])
def category_tree(request):
    """
    رد واحد يكفي شاشتَي «الرئيسية» و«الأقسام» معًا.
    التطبيق يخزّنه محليًا ويعيد استخدامه بلا إنترنت.
    """
    roots = category_tree_queryset()
    return Response(CategorySerializer(roots, many=True, context={"request": request}).data)


@extend_schema(summary="المدن مع أحيائها")
@api_view(["GET"])
@permission_classes([AllowAny])
def city_tree(request):
    cities = City.objects.filter(is_active=True).prefetch_related(
        Prefetch("neighborhoods", queryset=Neighborhood.objects.filter(is_active=True))
    )
    return Response(CitySerializer(cities, many=True, context={"request": request}).data)


@extend_schema(summary="أحياء مدينة")
@api_view(["GET"])
@permission_classes([AllowAny])
def neighborhoods(request):
    queryset = Neighborhood.objects.filter(is_active=True).select_related("city")
    city = request.GET.get("city")
    if city:
        queryset = queryset.filter(Q(city__slug=city) | Q(city_id=city if city.isdigit() else None))
    return Response(
        NeighborhoodSerializer(queryset, many=True, context={"request": request}).data
    )


# ---------------------------------------------------------------- الإدارة

class AdminCategoryViewSet(viewsets.ModelViewSet):
    """إدارة الأقسام: تعديل الأسماء بثلاث لغات · إضافة أقسام · إخفاء · ترتيب."""

    serializer_class = CategoryWriteSerializer
    permission_classes = [IsStaffRole]
    pagination_class = None

    def get_queryset(self):
        # العدّادان يقرّران ما يُسمح بحذفه — فنحسبهما مع القائمة لا بطلب لكل صف
        return (
            Category.objects.annotate(
                listings_count=Count("listings", filter=~Q(listings__status="deleted")),
                children_count=Count("children", distinct=True),
            )
            .order_by(*CATEGORY_ORDER)
        )

    def perform_destroy(self, instance):
        """
        الحذف ممنوع متى كان هدّامًا.

        الإعلانات مرتبطة بالقسم بـ PROTECT، فحذف قسم مستعمل كان يسقط الطلب
        بخطأ 500 غامض. نمنعه هنا برسالة تقول للأدمن ما البديل: الإخفاء يزيل
        القسم من التطبيق ويُبقي إعلاناته سليمة.
        """
        used = instance.listings.exclude(status="deleted").count()
        if used:
            raise ValidationError({
                "detail": f"لا يمكن حذف القسم — فيه {used} إعلانًا. "
                          "أخفِه بدل ذلك فيختفي من التطبيق وتبقى إعلاناته سليمة."
            })
        if instance.children.exists():
            raise ValidationError({
                "detail": "احذف الأقسام الفرعية أولًا."
            })
        instance.delete()


class AdminCityViewSet(viewsets.ModelViewSet):
    queryset = City.objects.all().order_by("sort_order", "name_ar")
    serializer_class = CityWriteSerializer
    permission_classes = [IsStaffRole]
    pagination_class = None


class AdminNeighborhoodViewSet(viewsets.ModelViewSet):
    queryset = Neighborhood.objects.select_related("city").order_by("sort_order", "name_ar")
    serializer_class = NeighborhoodWriteSerializer
    permission_classes = [IsStaffRole]
    pagination_class = None
    filterset_fields = ["city"]
