# Copyright 2020 Florent de Labarre
# Copyright 2022-2023 Therp BV <https://therp.nl>.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import json
import logging
import re
from datetime import datetime, timedelta
from operator import itemgetter

import pytz

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class OnlineBankStatementProvider(models.Model):
    _inherit = "online.bank.statement.provider"

    akahu_last_identifier = fields.Char(readonly=True)
    akahu_date_field = fields.Selection(
        [
            ("execution_date", "Execution Date"),
            ("value_date", "Value Date"),
        ],
        default="execution_date",
        help="Select the Akahu date field that will be used for "
        "the Odoo bank statement line date.",
    )

    @api.model
    def _get_available_services(self):
        """Each provider model must register its service."""
        return super()._get_available_services() + [
            ("akahu", "MyAkahu.com"),
        ]

    def _pull(self, date_since, date_until):
        """For Akahu the pulling of data will not be grouped by statement.

        Instead we will pull data from the last available backwards.

        For a scheduled pull we will continue until we get to data
        already retrieved or there is no more data available.

        For a wizard pull we will discard data after date_until and
        stop retrieving when either we get before date_since or there is
        no more data available.
        """
        # pylint: disable=missing-return
        akahu_providers = self.filtered(lambda provider: provider.service == "akahu")
        debug = self.env.context.get("account_statement_online_import_debug")
        debug_data = []
        data = super(OnlineBankStatementProvider, self - akahu_providers)._pull(
            date_since, date_until
        )
        if debug:
            debug_data += data
        for provider in akahu_providers:
            data = provider._akahu_pull(date_since, date_until)
            if debug:
                debug_data += data
        return debug_data

    def _akahu_pull(self, date_since, date_until):
        """Translate information from Akahu to Odoo bank statement lines."""
        self.ensure_one()
        is_scheduled = self.env.context.get("scheduled", False)
        if is_scheduled:
            _logger.debug(
                _(
                    "Akahu obtain statement data for journal %(journal)s"
                    " from %(date_since)s to %(date_until)s"
                ),
                dict(
                    journal=self.journal_id.name,
                    date_since=date_since,
                    date_until=date_until,
                ),
            )
        else:
            _logger.debug(
                _("Akahu obtain all new statement data for journal %s"),
                self.journal_id.name,
            )
        lines = self._akahu_retrieve_data(date_since, date_until)
        if not lines:
            _logger.info(_("No lines were retrieved from Akahu"))
        else:
            # For scheduled runs, store latest identifier.
            if is_scheduled:
                self.akahu_last_identifier = lines[0].get("id")
            self._akahu_store_lines(lines)
        return lines

    def _akahu_retrieve_data(self, date_since, date_until):
        """Fill buffer with data from Akahu.

        We will retrieve data from the latest transactions present in Akahu
        backwards, until we find data that has an execution date before date_since,
        or until we get to a transaction that we already have.

        Note: when reading data they are likely to be in descending order of
        execution_date (not seen a guarantee for this in Akahu API). When using
        value date, they may well be out of order. So we cannot simply stop
        when we have found a transaction date before the date_since.

        We will not read transactions more then a week before before date_since.
        """
        date_stop = date_since - timedelta(days=7)
        is_scheduled = self.env.context.get("scheduled", False)
        lines = []
        interface_model = self.env["akahu.interface"]
        access_data = interface_model._login(self.username, self.password)
        interface_model._set_access_account(access_data, self.account_number)
        latest_identifier = False
        transactions = interface_model._get_transactions(access_data, latest_identifier)
        while transactions:
            for line in transactions:
                identifier = line.get("id")
                transaction_datetime = self._akahu_get_transaction_datetime(line)
                if is_scheduled:
                    # Handle all stop conditions for scheduled runs.
                    if identifier == self.akahu_last_identifier or (
                        not self.akahu_last_identifier
                        and transaction_datetime < date_stop
                    ):
                        return lines
                else:
                    # Handle stop conditions for non scheduled runs.
                    if transaction_datetime < date_stop:
                        return lines
                    if (
                        transaction_datetime < date_since
                        or transaction_datetime > date_until
                    ):
                        continue
                line["transaction_datetime"] = transaction_datetime
                lines.append(line)
            latest_identifier = transactions[-1].get("id")
            transactions = interface_model._get_transactions(
                access_data, latest_identifier
            )
        # We get here if we found no transactions before date_since,
        # or not equal to stored last identifier.
        return lines

    def _akahu_store_lines(self, lines):
        """Store transactions retrieved from Akahu in statements."""
        lines = sorted(lines, key=itemgetter("transaction_datetime"))

        # Group statement lines by date per period (date range)
        grouped_periods = {}
        for line in lines:
            date_since = line["transaction_datetime"]
            statement_date_since = self._get_statement_date_since(date_since)
            statement_date_until = (
                statement_date_since + self._get_statement_date_step()
            )
            if (statement_date_since, statement_date_until) not in grouped_periods:
                grouped_periods[(statement_date_since, statement_date_until)] = []

            line.pop("transaction_datetime")
            vals_line = self._akahu_get_transaction_vals(line)
            grouped_periods[(statement_date_since, statement_date_until)].append(
                vals_line
            )

        # For each period, create or update statement lines
        for period, statement_lines in grouped_periods.items():
            (date_since, date_until) = period
            self._create_or_update_statement(
                (statement_lines, {}), date_since, date_until
            )

    def _akahu_get_transaction_vals(self, transaction):
        """Translate information from Akahu to statement line vals."""
        attributes = transaction.get("attributes", {})
        ref_list = [
            attributes.get(x)
            for x in {
                "description",
                "counterpartName",
                "counterpartReference",
            }
            if attributes.get(x)
        ]
        ref = " ".join(ref_list)
        date = self._akahu_get_transaction_datetime(transaction)
        vals_line = {
            "sequence": 1,  # Sequence is not meaningfull for Akahu.
            "date": date,
            "ref": re.sub(" +", " ", ref) or "/",
            "payment_ref": attributes.get("remittanceInformation", ref),
            "unique_import_id": transaction["id"],
            "amount": attributes["amount"],
            "raw_data": json.dumps(transaction),
        }
        if attributes.get("counterpartReference"):
            vals_line["account_number"] = attributes["counterpartReference"]
        if attributes.get("counterpartName"):
            vals_line["partner_name"] = attributes["counterpartName"]
        return vals_line

    def _akahu_get_transaction_datetime(self, transaction):
        """Get execution datetime for a transaction.

        Odoo often names variables containing date and time just xxx_date or
        date_xxx. We try to avoid this misleading naming by using datetime as
        much for variables and fields of type datetime.
        """
        attributes = transaction.get("attributes", {})
        if self.akahu_date_field == "value_date":
            datetime_str = attributes.get("valueDate")
        else:
            datetime_str = attributes.get("executionDate")
        return self._akahu_datetime_from_string(datetime_str)

    def _akahu_datetime_from_string(self, datetime_str):
        """Dates in Akahu are expressed in UTC, so we need to convert them
        to supplied tz for proper classification.
        """
        dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        dt = dt.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(self.tz or "utc"))
        return dt.replace(tzinfo=None)
