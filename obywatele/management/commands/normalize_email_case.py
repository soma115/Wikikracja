from collections import defaultdict

from allauth.account import app_settings as allauth_app_settings
from allauth.account.models import EmailAddress, EmailConfirmation
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction


class Command(BaseCommand):
    help = "Audit or lowercase e-mail addresses in User and allauth EmailAddress records."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write lowercase addresses; otherwise only report the proposed changes.")
        parser.add_argument("--confirm", action="store_true", help="Required with --apply to guard against accidental production changes.")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        if options["confirm"] and not apply_changes:
            raise CommandError("--confirm can only be used together with --apply.")
        if apply_changes and not options["confirm"]:
            raise CommandError("Use both --apply and --confirm to modify e-mail data.")

        user_model = get_user_model()
        email_field = allauth_app_settings.USER_MODEL_EMAIL_FIELD
        if not email_field:
            raise CommandError("The configured user model has no e-mail field.")

        try:
            if apply_changes:
                with transaction.atomic():
                    user_changes, address_changes, address_deletes, conflicts = self._collect_changes(user_model, email_field)
                    self._report_conflicts(conflicts)
                    self._apply_changes(user_model, email_field, user_changes, address_changes, address_deletes)
            else:
                user_changes, address_changes, address_deletes, conflicts = self._collect_changes(user_model, email_field)
                self._report_conflicts(conflicts)
        except IntegrityError as exc:
            raise CommandError("Database constraint failed; this instance's transaction was rolled back.") from exc

        unverified_changes = sum(not verified for _, _, _, verified in address_changes) + len(address_deletes)
        if unverified_changes:
            self.stdout.write(self.style.WARNING(f"{unverified_changes} unverified address records will be changed or merged; outstanding confirmation links may need to be resent."))

        if apply_changes:
            self.stdout.write(self.style.SUCCESS(f"Updated {len(user_changes)} user e-mails and {len(address_changes)} EmailAddress records; merged {len(address_deletes)} duplicate EmailAddress records."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: would lowercase {len(user_changes)} user e-mails and {len(address_changes)} EmailAddress records, "
                    f"and merge {len(address_deletes)} duplicate EmailAddress records. No data changed."
                )
            )

    def _collect_changes(self, user_model, email_field):
        user_changes = []
        address_changes = []
        address_deletes = []
        conflicts = []
        owners_by_email = defaultdict(set)
        address_rows_by_user_email = defaultdict(list)

        for user_id, email in user_model._default_manager.values_list("pk", email_field).iterator():
            if not email:
                continue
            normalized = email.lower()
            owners_by_email[normalized].add(user_id)
            if email != normalized:
                user_changes.append((user_id, email, normalized))

        addresses = EmailAddress.objects.values_list("pk", "user_id", "email", "verified", "primary")
        for address_id, user_id, email, verified, primary in addresses.iterator():
            if not email:
                continue
            normalized = email.lower()
            owners_by_email[normalized].add(user_id)
            address_rows_by_user_email[user_id, normalized].append((address_id, email, verified, primary))

        for email, user_ids in owners_by_email.items():
            if len(user_ids) > 1:
                conflicts.append(f"{email}: multiple accounts {sorted(user_ids)}")

        merge_ids = set()
        duplicate_groups = {(user_id, email): rows for (user_id, email), rows in address_rows_by_user_email.items() if len(rows) > 1}
        duplicate_ids = [row[0] for rows in duplicate_groups.values() for row in rows]
        pending_ids = set(EmailConfirmation.objects.filter(email_address_id__in=duplicate_ids).values_list("email_address_id", flat=True))

        for (user_id, email), rows in duplicate_groups.items():
            verified_primary = [row for row in rows if row[2] and row[3]]
            redundant = [row for row in rows if not row[2] and not row[3]]
            row_ids = {row[0] for row in rows}
            if len(verified_primary) == 1 and len(redundant) == len(rows) - 1 and not row_ids.intersection(pending_ids):
                for address_id, old_email, _, _ in redundant:
                    address_deletes.append((address_id, user_id, old_email))
                    merge_ids.add(address_id)
            else:
                conflicts.append(f"{email}: duplicate EmailAddress rows for account {user_id}: {sorted(row_ids)}")

        for rows in address_rows_by_user_email.values():
            for address_id, email, verified, _ in rows:
                if address_id not in merge_ids and email != email.lower():
                    address_changes.append((address_id, email, email.lower(), verified))

        return user_changes, address_changes, address_deletes, conflicts

    def _report_conflicts(self, conflicts):
        if conflicts:
            for conflict in conflicts:
                self.stderr.write(self.style.ERROR(f"Conflict: {conflict}"))
            raise CommandError("Resolve e-mail conflicts before normalizing; no changes were made.")

    def _apply_changes(self, user_model, email_field, user_changes, address_changes, address_deletes):
        for address_id, user_id, _email in address_deletes:
            deleted, _ = EmailAddress.objects.filter(pk=address_id, user_id=user_id).delete()
            if deleted != 1:
                raise CommandError(f"EmailAddress {address_id} changed during merge; transaction was rolled back.")

        for user_id, old_email, normalized in user_changes:
            updated = user_model._default_manager.filter(pk=user_id, **{email_field: old_email}).update(**{email_field: normalized})
            if updated != 1:
                raise CommandError(f"User {user_id} changed during normalization; transaction was rolled back.")

        for address_id, old_email, normalized, _verified in address_changes:
            updated = EmailAddress.objects.filter(pk=address_id, email=old_email).update(email=normalized)
            if updated != 1:
                raise CommandError(f"EmailAddress {address_id} changed during normalization; transaction was rolled back.")
