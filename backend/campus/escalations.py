from django.db import transaction
from django.utils import timezone
from .models import SupportTicket,SupportEscalation
def scan(institution=None):
    now=timezone.now();q=SupportTicket.objects.filter(status__in=['open','assigned'])
    if institution is not None:q=q.filter(institution=institution)
    created=0
    for kind in ('response','resolution'):
        field='responded_at' if kind=='response' else 'resolved_at'
        rows=q.filter(**{field+'__isnull':True,kind+'_due__lt':now}).values_list('pk',flat=True)
        for pk in rows.iterator():
            with transaction.atomic():
                t=SupportTicket.objects.select_for_update().get(pk=pk)
                if getattr(t,field) is None and getattr(t,kind+'_due')<now and t.status in ('open','assigned'):
                    _,new=SupportEscalation.objects.get_or_create(ticket=t,kind=kind);created+=int(new)
    return created
