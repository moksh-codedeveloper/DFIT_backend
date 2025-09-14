from django.db import models

class Membership(models.Model):
    # Foreign key to Prisma User
    user_id = models.UUIDField()   # stores Prisma User.id (UUID)
    
    plan = models.CharField(max_length=50, choices=[
        ("free", "Free"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ], default="free")
    
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user_id} - {self.plan}"
