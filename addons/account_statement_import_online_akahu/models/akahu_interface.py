# Copyright 2020 Florent de Labarre
# Copyright 2022 Therp BV <https://therp.nl>.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import json
import logging

import requests
from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.base.models.res_bank import sanitize_account_number

_logger = logging.getLogger(__name__)

AKAHU_ENDPOINT = "https://api.myakahu.com"


class AkahuInterface(models.AbstractModel):
    _name = "akahu.interface"
    _description = "Interface to all interactions with Akahu API"

    def _login(self, username, password):
        """Akahu login returns an access dictionary for further requests."""
        url = AKAHU_ENDPOINT + "/oauth2/token"
        if not (username and password):
            raise UserError(_("Please fill login and key."))
        login = ":".join([username, password])
        login = base64.b64encode(login.encode("UTF-8")).decode("UTF-8")
        login_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Authorization": f"Basic {login}",
        }
        _logger.debug(_("POST request on %(url)s"), dict(url=url))
        response = requests.post(
            url,
            params={"grant_type": "client_credentials"},
            headers=login_headers,
            timeout=60,
        )
        data = self._get_response_data(response)
        access_token = data.get("access_token", False)
        if not access_token:
            raise UserError(_("Akahu : no token"))
        token_expiration = fields.Datetime.now() + relativedelta(
            seconds=data.get("expires_in", False)
        )
        return {
            "username": username,
            "password": password,
            "access_token": access_token,
            "token_expiration": token_expiration,
        }

    def _get_request_headers(self, access_data):
        """Get headers with authorization for further akahu requests."""
        if access_data["token_expiration"] <= fields.Datetime.now():
            updated_data = self._login(access_data["username"], access_data["password"])
            access_data.update(updated_data)
        return {
            "Accept": "application/json",
            "Authorization": "Bearer {access_token}".format(
                access_token=access_data["access_token"]
            ),
        }

    def _set_access_account(self, access_data, account_number):
        """Set akahu account for bank account in access_data."""
        url = AKAHU_ENDPOINT + "/accounts"
        _logger.debug(_("GET request on %(url)s"), dict(url=url))
        response = requests.get(
            url,
            params={"limit": 100},
            headers=self._get_request_headers(access_data),
            timeout=60,
        )
        data = self._get_response_data(response)
        for akahu_account in data.get("data", []):
            akahu_iban = sanitize_account_number(
                akahu_account.get("attributes", {}).get("reference", "")
            )
            if akahu_iban == account_number:
                access_data["akahu_account"] = akahu_account.get("id")
                return
        # If we get here, we did not find Akahu account for bank account.
        raise UserError(
            _(
                "Akahu : wrong configuration, account {account} not found in {data}"
            ).format(account=account_number, data=data)
        )

    def _get_transactions(self, access_data, last_identifier):
        """Get transactions from akahu, using last_identifier as pointer.

        Note that Akahu has the transactions in descending order. The first
        transaction, retrieved by not passing an identifier, is the latest
        present in Akahu. If you read transactions 'after' a certain identifier
        (Akahu id), you will get transactions with an earlier date.
        """
        url = (
            AKAHU_ENDPOINT
            + "/accounts/"
            + access_data["akahu_account"]
            + "/transactions"
        )
        params = {"limit": 100}
        if last_identifier:
            params["after"] = last_identifier
        data = self._get_request(access_data, url, params)
        transactions = self._get_transactions_from_data(data)
        return transactions

    def _get_transactions_from_data(self, data):
        """Get all transactions that are in the akahu response data."""
        transactions = data.get("data", [])
        if not transactions:
            _logger.debug(
                _("No transactions where found in data %(data)s"),
                dict(data=data),
            )
        else:
            _logger.debug(
                _("%d transactions present in response data"),
                len(transactions),
            )
        return transactions

    def _get_request(self, access_data, url, params):
        """Interact with Akahu to get next page of data."""
        headers = self._get_request_headers(access_data)
        _logger.debug(
            _("GET request to %(url)s with headers %(headers)s and params %(params)s"),
            dict(
                url=url,
                headers=headers,
                params=params,
            ),
        )
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=(60, 300),
        )
        return self._get_response_data(response)

    def _get_response_data(self, response):
        """Get response data for GET or POST request."""
        _logger.debug(
            _("HTTP answer code %(response_code)s from Akahu"),
            dict(response_code=response.status_code),
        )
        if response.status_code not in (200, 201):
            raise UserError(
                _(
                    "Server returned status code {response_code}: {response_text}"
                ).format(
                    response_code=response.status_code,
                    response_text=response.text,
                )
            )
        return json.loads(response.text)
