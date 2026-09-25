from django import template
from pricing.access import user_can_access_costos

register = template.Library()

@register.simple_tag
def costos_access(user):
    return user_can_access_costos(user)
