"""Synthetic fixtures used across the test suite.

All identifiers, names, and amounts are invented for testing. Any resemblance
to a real QuickBooks Online realm is coincidental — this file must never gain
real-world identifiers, customer names, vendor names, or account numbers.
"""

from __future__ import annotations

# A deliberately unrealistic realm ID so it's obvious if it ever leaks
# into a real API call by accident.
SANDBOX_REALM_ID = "9999999999990001"

SAMPLE_TOKEN_RESPONSE = {
    "access_token": "test-access-token-please-do-not-use-in-production",
    "refresh_token": "test-refresh-token-rotated-on-each-call",
    "expires_in": 3600,
    "x_refresh_token_expires_in": 8726400,
    "token_type": "Bearer",
}

# ---- customers --------------------------------------------------------

SAMPLE_CUSTOMER = {
    "Id": "1001",
    "DisplayName": "Acme Corp",
    "CompanyName": "Acme Corp",
    "PrimaryEmailAddr": {"Address": "ap@acme.example"},
    "Balance": 1250.00,
    "Active": True,
}

SAMPLE_CUSTOMER_QUERY_PAGE = {
    "QueryResponse": {
        "Customer": [
            SAMPLE_CUSTOMER,
            {
                "Id": "1002",
                "DisplayName": "Acme Logistics",
                "CompanyName": "Acme Logistics LLC",
                "Balance": 0.00,
                "Active": True,
            },
        ],
        "startPosition": 1,
        "maxResults": 100,
        "totalCount": 2,
    },
    "time": "2026-04-26T12:00:00.000-07:00",
}

SAMPLE_CUSTOMER_GET = {"Customer": SAMPLE_CUSTOMER, "time": "2026-04-26T12:00:00.000-07:00"}

# ---- vendors ----------------------------------------------------------

SAMPLE_VENDOR = {
    "Id": "2001",
    "DisplayName": "WidgetCo",
    "CompanyName": "WidgetCo Manufacturing",
    "PrimaryEmailAddr": {"Address": "ar@widgetco.example"},
    "Balance": 0.00,
    "Active": True,
}

SAMPLE_VENDOR_QUERY_PAGE = {
    "QueryResponse": {
        "Vendor": [
            SAMPLE_VENDOR,
            {
                "Id": "2002",
                "DisplayName": "WidgetCo Freight",
                "CompanyName": "WidgetCo Freight Services",
                "Balance": 312.45,
                "Active": True,
            },
        ],
        "startPosition": 1,
        "maxResults": 100,
        "totalCount": 2,
    },
    "time": "2026-04-26T12:00:00.000-07:00",
}

SAMPLE_VENDOR_GET = {"Vendor": SAMPLE_VENDOR, "time": "2026-04-26T12:00:00.000-07:00"}

# ---- invoices ---------------------------------------------------------

SAMPLE_INVOICE = {
    "Id": "5001",
    "DocNumber": "TEST-INV-5001",
    "TxnDate": "2026-04-25",
    "DueDate": "2026-05-25",
    "TotalAmt": 4200.00,
    "Balance": 4200.00,
    "CustomerRef": {"value": "1001", "name": "Acme Corp"},
    "Line": [
        {
            "Id": "1",
            "DetailType": "SalesItemLineDetail",
            "Amount": 4200.00,
            "Description": "Lorem service, Q2 retainer",
        }
    ],
}

SAMPLE_INVOICE_QUERY_PAGE_1 = {
    "QueryResponse": {
        "Invoice": [
            SAMPLE_INVOICE,
            {
                "Id": "5002",
                "DocNumber": "TEST-INV-5002",
                "TxnDate": "2026-04-25",
                "TotalAmt": 199.00,
                "Balance": 0.00,
                "CustomerRef": {"value": "1002", "name": "Acme Logistics"},
                "Line": [],
            },
        ],
        "startPosition": 1,
        "maxResults": 2,
    },
    "time": "2026-04-26T12:00:00.000-07:00",
}

SAMPLE_INVOICE_QUERY_PAGE_2 = {
    "QueryResponse": {
        "Invoice": [
            {
                "Id": "5003",
                "DocNumber": "TEST-INV-5003",
                "TxnDate": "2026-04-26",
                "TotalAmt": 750.00,
                "Balance": 750.00,
                "CustomerRef": {"value": "1001", "name": "Acme Corp"},
                "Line": [],
            }
        ],
        "startPosition": 3,
        "maxResults": 2,
    },
    "time": "2026-04-26T12:00:00.000-07:00",
}

SAMPLE_INVOICE_GET = {
    "Invoice": SAMPLE_INVOICE,
    "time": "2026-04-26T12:00:00.000-07:00",
}

# ---- bills ------------------------------------------------------------

SAMPLE_BILL = {
    "Id": "6001",
    "DocNumber": "TEST-BILL-6001",
    "TxnDate": "2026-04-20",
    "DueDate": "2026-05-20",
    "TotalAmt": 875.50,
    "Balance": 875.50,
    "VendorRef": {"value": "2001", "name": "WidgetCo"},
    "Line": [
        {
            "Id": "1",
            "DetailType": "AccountBasedExpenseLineDetail",
            "Amount": 875.50,
            "Description": "Lorem inventory, lot TEST-A",
        }
    ],
}

SAMPLE_BILL_QUERY_PAGE = {
    "QueryResponse": {
        "Bill": [
            SAMPLE_BILL,
            {
                "Id": "6002",
                "DocNumber": "TEST-BILL-6002",
                "TxnDate": "2026-04-21",
                "TotalAmt": 312.45,
                "Balance": 0.00,
                "VendorRef": {"value": "2002", "name": "WidgetCo Freight"},
                "Line": [],
            },
        ],
        "startPosition": 1,
        "maxResults": 100,
    },
    "time": "2026-04-26T12:00:00.000-07:00",
}

SAMPLE_BILL_GET = {"Bill": SAMPLE_BILL, "time": "2026-04-26T12:00:00.000-07:00"}

# ---- chart of accounts -----------------------------------------------

SAMPLE_ACCOUNTS = [
    {
        "Id": "1001",
        "Name": "Sandbox Operating Cash",
        "AccountType": "Bank",
        "AccountSubType": "Checking",
        "Classification": "Asset",
        "CurrentBalance": 50000.00,
        "Active": True,
    },
    {
        "Id": "1002",
        "Name": "Sandbox Inventory Asset",
        "AccountType": "Other Current Asset",
        "AccountSubType": "Inventory",
        "Classification": "Asset",
        "CurrentBalance": 12500.00,
        "Active": True,
    },
    {
        "Id": "1003",
        "Name": "Sandbox Sales Income",
        "AccountType": "Income",
        "AccountSubType": "SalesOfProductIncome",
        "Classification": "Revenue",
        "CurrentBalance": 0.00,
        "Active": True,
    },
]

SAMPLE_ACCOUNTS_QUERY_PAGE = {
    "QueryResponse": {
        "Account": SAMPLE_ACCOUNTS,
        "startPosition": 1,
        "maxResults": 1000,
    },
    "time": "2026-04-26T12:00:00.000-07:00",
}
