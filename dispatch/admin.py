from django.contrib import admin

from .models import Driver, EmergencyRequest, EmergencyRequestCandidate, Hospital, PatientProfile, User

admin.site.register(User)
admin.site.register(PatientProfile)
admin.site.register(Hospital)
admin.site.register(Driver)
admin.site.register(EmergencyRequest)
admin.site.register(EmergencyRequestCandidate)

# Register your models here.
