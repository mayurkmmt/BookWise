from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    is_active = models.BooleanField(
        _("Is active"),
        default=True,
        help_text=_(
            "Designates whether this field should be treated as active. Unselect to inactive a field"
        ),
    )
    is_delete = models.BooleanField(
        _("Is delete"), null=True, blank=True, default=False
    )
    created_at = models.DateTimeField(
        _("Created at"), auto_now_add=True, null=True, blank=True
    )
    modified_at = models.DateTimeField(_("Updated at"), auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_created_by",
        null=True,
        blank=True,
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_modified_by",
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        self.is_delete = True
        self.save(update_fields=["is_delete"])
