import stripe
import config

customers_cached = {}

def retrieveCustomer(id):
  if isinstance(id, str):
    if id in customers_cached:
      return customers_cached[id]
    cus = stripe.Customer.retrieve(id)
    customers_cached[cus.id] = cus
    # Enzo write stripe Customer
    f = open("out/stripe/customer_{}.txt".format(id), "w")
    f.write(str(cus))
    f.close()
    print("write customer {} done".format(id))
    # Enzo End
    return cus
  elif isinstance(id, stripe.Customer):
    customers_cached[id.id] = id
    return id
  else:
    raise "Unexpected retrieveCustomer() argument: {}".format(id)

def getCustomerName(customer):
  if customer.get("deleted", False):
    return customer.id
  if customer.description is not None:
    return customer.description
  else:
    return customer.name

tax_ids_cached = {}

def getCustomerTaxId(customer):
  if customer.id in tax_ids_cached:
    return tax_ids_cached[customer.id]
  ids = stripe.Customer.list_tax_ids(customer.id, limit=10).data
  tax_id = ids[0].value if len(ids) > 0 else None
  tax_ids_cached[customer.id] = tax_id
  return tax_id

def getCustomerDetails(customer):
  record = {
    "id": customer.id
  }
  if "deleted" in customer and customer.deleted:
    record["name"] = customer.id
  else:
    record["name"] = getCustomerName(customer)
    if customer.address is not None:
      record["country"] = customer.address.country
    elif customer.shipping is not None:
      record["country"] = customer.shipping.address.country
    if record["country"] in country_codes_eu:
      tax_id = getCustomerTaxId(customer)
      record["vat_id"] = tax_id
    if customer.tax_exempt:
      record["tax_exempt"] = customer.tax_exempt
  return record

country_codes_eu = [
  "AT",
  "BE",
  "BG",
  "CY",
  "CZ",
  "DK",
  "EE",
  "FI",
  "FR",
  "DE",
  "GR",
  "HU",
  "IE",
  "IT",
  "LV",
  "LT",
  "LU",
  "MT",
  "NL",
  "PL",
  "PT",
  "RO",
  "SK",
  "SI",
  "ES",
  "SE",
]

def getAccountingProps(customer, invoice=None, checkout_session=None):
  props = {
    "customer_account": config.customer_account,
    "vat_region": "World",
  }
  if customer is None:
    return props

  country = customer.get("country", None)

  invoice_tax = None
  if invoice is not None:
    invoice_tax = invoice.get("tax", None)
  elif checkout_session is not None:
    invoice_tax = checkout_session.get("total_details", {}).get("amount_tax", None)

  # use tax status at time of invoice creation
  if invoice is not None and "customer_tax_exempt" in invoice:
    tax_exempt = invoice["customer_tax_exempt"]
  else:
    tax_exempt = customer.get("tax_exempt", None)

  vat_id = customer.get("vat_id", None)

  props = dict(props, **{
    "country": country,
    "vat_id": vat_id,
    "tax_exempt": tax_exempt,
    "invoice_tax": invoice_tax,
    "datev_tax_key": "",
  })

  if country == config.home_country:
    if invoice is not None and invoice_tax is None:
      print("Warning: no tax in {} invoice".format(config.home_country), invoice["id"])
    if tax_exempt != "none":
      print("Warning: {} customer tax status is".format(config.home_country), tax_exempt, customer["id"])
    props["revenue_account"] = config.revenue_account
    # props["datev_tax_key"] = "9"
    props["vat_region"] = config.home_country
    return props

  if country in country_codes_eu:
    props["vat_region"] = "EU"

  if tax_exempt == "reverse" or tax_exempt == "exempt" or invoice_tax is None or invoice_tax == 0:
    if tax_exempt == "exempt":
      print("Warning: tax exempt customer, treating like 'reverse'", customer["id"])
      props["tax_exempt"] = "reverse"
    if tax_exempt == "none":
      print("Warning: taxable customer without tax on invoice, treating like 'reverse'", customer["id"], invoice.get("id", "n/a") if invoice is not None else "n/a")
      props["tax_exempt"] = "reverse"
    if not (invoice_tax is None or invoice_tax == 0):
      print("Warning: tax on invoice of reverse charge customer", invoice.get("id", "n/a") if invoice is not None else "n/a")
    if country in country_codes_eu and vat_id is None:
      print("Warning: EU reverse charge customer without VAT ID", customer["id"])

    if country in country_codes_eu and vat_id is not None:
      props["revenue_account"] = config.revenue_account_reverse_charge
    else:
      props["revenue_account"] = config.revenue_account_world

    # props["datev_tax_key"] = "94"
    return props

  elif tax_exempt == "none":
    # print("Warning: configure taxation for", country, "customer", customer["id"])
    # Unter Bagtellgrenze MOSS
    pass

  else:
    print("Warning: unknown tax status for customer", customer["id"])

  props["revenue_account"] = config.revenue_account
  return props

def getRevenueAccount(customer, invoice=None, checkout_session=None):
  return getAccountingProps(customer, invoice=invoice, checkout_session=checkout_session)["revenue_account"]

def getCustomerAccount(customer, invoice=None, checkout_session=None):
  return getAccountingProps(customer, invoice=invoice, checkout_session=checkout_session)["customer_account"]

def getDatevTaxKey(customer, invoice=None, checkout_session=None):
  return getAccountingProps(customer, invoice=invoice, checkout_session=checkout_session)["datev_tax_key"]

def all_customers():
  starting_after = None
  while True:
    response = stripe.Customer.list(
      starting_after=starting_after,
      limit=10
    )
    # print("Fetched {} customers".format(len(response.data)))
    if len(response.data) == 0:
      break
    starting_after = response.data[-1].id
    for item in response.data:
      yield item

def validate_customers():
  for customer in all_customers():
    # print(customer)
    if not customer.address:
      print("Warning: customer without address", customer.id)
      continue

    country = customer.address.country
    tax_exempt = customer.tax_exempt
    vat_id = customer.tax_info.tax_id if customer.tax_info is not None else None

    if country == config.home_country:
      if tax_exempt != "none":
        print("Warning: {} customer tax status is".format(config.home_country), tax_exempt, customer.id)

    elif tax_exempt == "reverse":
      if country in ["ES", "IT", "GB"] and vat_id is None:  #warum nur für ES, IT und GB. sollte doch die ganze EU sein!!
        print("Warning: EU reverse charge customer without VAT ID", customer.id)

    # elif tax_exempt == "none":
    #   print("Warning: configure taxation for", country, "customer", customer.id)

    elif tax_exempt == "exempt":
      print("Warning: exempt customer", customer.id)
