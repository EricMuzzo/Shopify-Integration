from app.models import *
from requests.auth import HTTPBasicAuth
from urllib.parse import quote
from dotenv import load_dotenv
import os
import json
import requests

load_dotenv()
authorization = HTTPBasicAuth(os.getenv("spire_user"), os.getenv("spire_pswd"))
headers = {
        "accept": "application/json",
        "content-type": "application/json"
}

def generate_inventory_payload(line_items: list[LineItem]) -> list:
    """Generates a list of line items to send as a payload to Spire"""
    
    spire_item_list = []
    for line in line_items:
        
        #-----------------------------------Grab part number data from Spire---------------------------------
        
        encoded_filter = quote(json.dumps({"partNo":line.sku,"whse":"00"}))
        response = requests.get(f"https://red-wave-8362.spirelan.com:10880/api/v2/companies/{os.getenv("company")}/inventory/items/?filter={encoded_filter}", auth=authorization, headers=headers)
        
        content = response.json()
        count = content["count"]
        if count == 1:
            
            #Don't have a use for this yet until reqs open to API
            
            #Grab part number endpoint
            found_part = content["records"][0]
            available_qty = float(found_part["availableQty"])
            #onPurchase_qty = float(found_part["onPurchaseQty"])    Requisitions not yet available to API
            #reg_price = float(found_part["pricing"]["sellPrice"][0])
            
        item_dict = {
            "whse": "00",
            "partNo": line.sku.replace("_(100%off)", ""),
            "orderQty": str(line.order_qty),
            "retailPrice": line.price,
            "discountPct": line.discount_percent
        }
        
        spire_item_list.append(item_dict)
        
    return spire_item_list


def getTaxCode(taxLine) -> int:
    """Get the correct Spire sales tax code"""
    
    #Figure out which tax we're looking for
    tax_title = taxLine["title"]
    rate = float(taxLine["rate"]) * 100
    
    try:
        response = requests.get(f"https://red-wave-8362.spirelan.com:10880/api/v2/companies/{os.getenv("company")}/sales_taxes", auth=authorization, headers=headers)
        spire_sales_taxes = response.json()["records"]
        
        for spire_tax in spire_sales_taxes:
            tax_rate = float(spire_tax["rate"])
            
            if rate == tax_rate:
                return int(spire_tax["code"])
        
        print("No tax rates matched, defaulting to HST 13 (Code 3)")
    except Exception as e:
        print("Tax match error: ", e)
    
    return 3


def calculateTotalDiscount(discountApplications: list, subtotal: float) -> float:
    """Calculates the total discount percentage to apply to the order. Does not include line level discounts"""
    
    discount_pct = 0.0
    
    for application in discountApplications:
        if application["allocation_method"] != "one" and application["target_type"] == "line_item":
            if application["value_type"] == "percentage":
                discount_pct += float(application["value"])
            else:
                discount_pct += float((application["value"] / subtotal) * 100)
                
    return discount_pct

def getSpireNoteId(shopify_order_no):
    """Gets the id of the spire note for a given shopify sales order"""
    
    filter = {
        "linkTable":"SORD",
        "linkNo":{"$like":f"WEB{shopify_order_no}%"},
        "groupType":"CUS-NOTES"
    }
    encoded_filter = quote(json.dumps(filter))
    response = requests.get(f"https://red-wave-8362.spirelan.com:10880/api/v2/companies/{os.getenv("company")}/crm/notes/?filter={encoded_filter}", auth=authorization, headers=headers)
    # print(response.status_code)
    # print(response.json())
    
    records = response.json()["records"]
    if len(records) == 0 or len(records) != 1:
        return None
    
    notes_id = records[0]["id"]
    
    return notes_id

def getSpireOrderId(shopify_order_no):
    """Gets the id of the spire order for a given shopify sales order"""
    
    filter = {
        "orderNo":{
            "$like": f"WEB{shopify_order_no}%"
        }
    }
    encoded_filter = quote(json.dumps(filter))
    response = requests.get(f"https://red-wave-8362.spirelan.com:10880/api/v2/companies/{os.getenv("company")}/sales/orders/?filter={encoded_filter}", auth=authorization, headers=headers)
    
    records = response.json()["records"]
    if len(records) == 0 or len(records) != 1:
        return None
    
    order_id = records[0]["id"]
    
    return order_id