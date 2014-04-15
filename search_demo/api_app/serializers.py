from django.forms import widgets
from rest_framework import serializers
from rest_framework.pagination import PaginationSerializer


#serializer/source=
#can we use a function?

# refs: http://www.django-rest-framework.org/tutorial/1-serialization
class ItemSerializer(serializers.Serializer):
    item_id = serializers.Field()
    item_name = serializers.SerializerMethodField("get_item_name")
    #item_name = serializers.CharField(required=True, max_length=256)
    price = serializers.FloatField(required=True)
    market_price = serializers.FloatField(required=False)
    #image_link = serializers.CharField(required=False, max_length=1024)
    image_link = serializers.Field()
    item_link  = serializers.CharField(required=True, max_length=1024)
    categories = serializers.Field()
    available = serializers.Field()

    def get_item_name(self, obj):
        _highlight = getattr(obj, "_highlight", None)
        if _highlight:
            item_names = _highlight.get("item_name_standard_analyzed", None)
            if item_names:
                return item_names[0]
        return obj.item_name_standard_analyzed
    #def restore_object(self, attrs, instance=None):
    #    pass



class PaginatedItemSerializer(PaginationSerializer):
    class Meta:
        object_serializer_class = ItemSerializer
