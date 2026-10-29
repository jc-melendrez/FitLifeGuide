from django import template
from django.utils.timesince import timesince

register = template.Library()

@register.filter
def class_name(obj):
    return obj.__class__.__name__.lower()


@register.filter
def short_timesince(value):
    return timesince(value, depth=1)