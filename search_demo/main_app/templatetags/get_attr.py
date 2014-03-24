from django.template import Library


register = Library()


@register.filter(name='dict_get')
def dict_get(d, k):
    return d.get(k, None)


@register.filter(name="obj_get")
def obj_get(obj, k):
    return getattr(obj, k, None)


@register.filter(name="list_get")
def list_get(obj, idx):
    return obj[idx]
