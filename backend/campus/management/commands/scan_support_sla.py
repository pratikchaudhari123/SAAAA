from django.core.management.base import BaseCommand
from campus.escalations import scan
class Command(BaseCommand):
    help='Persist unique overdue support SLA alerts; schedule using the approved host scheduler.'
    def handle(self,*args,**options):
        self.stdout.write('New SLA alerts: '+str(scan()))
