# pylint: disable=missing-module-docstring
from datetime import date, datetime, timedelta

import requests
from dateutil.parser import parse as parse_dt

from .base import Base, CurrencyMismatch


class Prices(Base):
    """Class for fetching Nord Pool Elsbas prices."""

    HOURLY = 194
    API_URL = "https://www.nordpoolgroup.com/api/marketdata/page/%i"

    def _parse_json(self, data, columns, areas):  # pylint: disable=too-many-branches
        """
        Parse json response from fetcher.
        Returns dictionary with
            - update time
            - currency
            - dictionary of areas, based on selection
                - list of values (dictionary with start and endtime and value)
                - possible other values, such as min, max, average for hourly
        """

        # If areas or columns aren't lists, make them one
        if not isinstance(areas, list):
            areas = list(areas)
        if not isinstance(columns, list):
            columns = list(columns)
        # Update currency from data
        currency = data["currency"]

        # Ensure that the provided currency match the requested one
        if currency != self.currency:
            raise CurrencyMismatch

        # All relevant data is in data['data']
        data = data["data"]
        # start_time = self._parse_dt(data['DataStartdate'])
        # end_time = self._parse_dt(data['DataEnddate'])
        updated = self._parse_dt(data["DateUpdated"])
        areas_data = {}
        areas_data[areas[0]] = {}
        # Loop through response rows
        for r in data["Rows"]:
            # Loop through columns
            if r["Name"] is None:
                continue
            name = " ".join(r["Name"].split("-")).split(" ")
            # Picks only "PH" product (hourly)
            if not name[0] == "PH":
                continue
            row_start_time = self._parse_dt(
                "-".join([name[1], format(int(name[2]) - 1, "02")])
            )
            # End time is generated by adding 1 hour to start time
            row_end_time = row_start_time + timedelta(hours=1)
            for c in r["Columns"]:
                name = c["Name"]
                # If column name is defined and name isn't in columns, skip column
                if columns and name not in columns:
                    continue
                # If name isn't in areas_data, initialize dictionary
                if name not in areas_data[areas[0]].keys():
                    areas_data[areas[0]].update(
                        {
                            name: [],
                        }
                    )
                # Skip extra rows, nothing special here
                if r["IsExtraRow"]:
                    continue
                # Add Product value is string
                if name == "Product":
                    # Append dictionary to value list
                    areas_data[areas[0]][name].append(
                        {
                            "start": row_start_time,
                            "end": row_end_time,
                            "value": c["Value"],
                        }
                    )
                else:
                    # Append dictionary to value list
                    areas_data[areas[0]][name].append(
                        {
                            "start": row_start_time,
                            "end": row_end_time,
                            "value": self._conv_to_float(c["Value"]),
                        }
                    )
        return {"updated": updated, "currency": currency, "areas": areas_data}

    def _fetch_json(self, data_type, areas, end_date=None):
        """Fetch JSON from API"""
        # If end_date isn't set, default to tomorrow
        if end_date is None:
            end_date = date.today() - timedelta(days=1)
        # If end_date isn't a date or datetime object, try to parse a string
        if not isinstance(end_date, date) and not isinstance(end_date, datetime):
            end_date = parse_dt(end_date)
        # Create request to API
        r = requests.get(
            self.API_URL % data_type,
            params={
                "currency": self.currency,
                "endDate": end_date.strftime("%d-%m-%Y"),
                "entityName": "".join(areas),
            },
            timeout=self.timeout,
        )
        # Return JSON response
        return r.json()

    def fetch(self, data_type, columns, end_date=None, areas=None):
        """
        Fetch data from API.
        Inputs:
            - data_type
                API page id, one of Prices.HOURLY
            - end_date
                datetime to end the data fetching
                defaults to yesterday
            - areas
                list (lengt of one) of areas to fetch, such as ['FI']
                defaults to all areas

        Returns dictionary with
            - update time
            - currency
            - dictionary of areas, based on selection
                - list of values (dictionary with start and endtime and value)
                - possible other values, such as min, max, average for hourly
        """
        return self._parse_json(
            self._fetch_json(data_type, areas, end_date), columns, areas
        )

    def hourly(
        self,
        end_date=None,
        areas=None,
        columns=None,
    ):
        """Helper to fetch hourly data, see Prices.fetch()"""
        if columns is None:
            columns = ["Product", "High", "Low", "Last", "Avg", "Volume"]
        return self.fetch(self.HOURLY, columns, end_date, areas)
