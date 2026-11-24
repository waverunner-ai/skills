# Worked examples

Both inputs are the examples Waverunner's guide and its calculator start with. They show how the script reads two
numbers; they are not what a shop usually sees. Each output below is trimmed to the ratio and the first three
programmes; the full output also holds MATCH, the Visa acquirer levels, the provider rules, the facts and the
questions for the provider.

Run from the skill folder, or call the script by its full path from anywhere.

## 1. The guide's example: 1,500 chargebacks over 98,000 transactions

```bash
python scripts/chargeback_check.py --chargebacks 1500 --transactions 98000
```

```json
{
  "chargebacks": 1500,
  "transactions": 98000,
  "display": {
    "percent": "1.53%",
    "bps": "153.1 bps",
    "counted": "1,500 chargebacks over 98,000 transactions"
  },
  "programmes": [
    {
      "id": "mastercard-ecm",
      "threshold": "At least 150 bps AND at least 100 chargebacks in the month",
      "onYourNumbers": {
        "conditions": [
          { "condition": "150 bps (1.5%) or more", "yours": "153.1 bps", "meets": true },
          { "condition": "at least 100 chargebacks in the month", "yours": "1,500 chargebacks", "meets": true }
        ],
        "inWords": "The numbers meet both conditions as the guide states them: the ratio and the minimum count."
      }
    },
    {
      "id": "mastercard-hecm",
      "threshold": "At least 300 bps AND at least 300 chargebacks in the month",
      "onYourNumbers": {
        "conditions": [
          { "condition": "300 bps (3%) or more", "yours": "153.1 bps", "meets": false },
          { "condition": "at least 300 chargebacks in the month", "yours": "1,500 chargebacks", "meets": true }
        ],
        "inWords": "The numbers meet the minimum count and not the ratio condition, as the guide states them."
      }
    },
    {
      "id": "visa-vamp-merchant",
      "threshold": "At least 150 bps AND at least 1,500 fraud reports and disputes a month",
      "onYourNumbers": {
        "computed": false,
        "why": "Visa's ratio adds card-not-present fraud reports to disputes and divides by settled transactions, so chargebacks over last month's transactions is not Visa's figure."
      }
    }
  ]
}
```

The guide says the same of this example: about 153 bps and 1,500 chargebacks meet both ECM conditions.

## 2. The calculator's starting numbers: 90 chargebacks over 6,000 transactions

```bash
python scripts/chargeback_check.py --chargebacks 90 --transactions 6000
```

```json
{
  "display": { "percent": "1.50%", "bps": "150 bps", "counted": "90 chargebacks over 6,000 transactions" },
  "programmes": [
    {
      "id": "mastercard-ecm",
      "onYourNumbers": {
        "conditions": [
          { "condition": "150 bps (1.5%) or more", "yours": "150 bps", "meets": true },
          { "condition": "at least 100 chargebacks in the month", "yours": "90 chargebacks", "meets": false }
        ],
        "inWords": "The numbers meet the ratio condition and not the minimum count, as the guide states them."
      }
    }
  ]
}
```

The ratio sits exactly on ECM's ratio line and the count is under ECM's minimum of 100, so the numbers meet one of
the two ECM conditions. That is why an answer always gives both parts of a line.
