from ast import Dict
from urllib.request import HTTPBasicAuthHandler
from flask import Flask, Response, jsonify, request
import json
from urllib.parse import quote
from myModules.models import *
from dotenv import load_dotenv
import os
from requests.auth import HTTPBasicAuth
from datetime import datetime
from myModules.helpers import *

load_dotenv()

PORT = os.getenv('PORT')

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "message": "Welcome to the API"
    })
    
def createOrderPayload(order):
    """Creates the spire API order payload and note payload as dictionaries when given the .json object of the incoming Shopify request"""
    
    #--------------------------------------------Variable extraction------------------------------------------------------------
    order_id = order["id"]
    confirmation_no = order["confirmation_number"]
    order_number = order["order_number"]
    order_date = order["created_at"]
    order_status_url = order["order_status_url"]
    
    
    tags: list = order["tags"].split(", ")
    
    #Contact & Method Of Delivery Details
    contact_email = order["contact_email"]
    phone = order["phone"]
    
    shipping_line_json = order["shipping_lines"][0] #Shipping lines is an array but I've only seen one array element ever
    shipping = Shipping(shipping_line_json["code"], shipping_line_json["title"], shipping_line_json["source"], shipping_line_json["discounted_price"],
                        shipping_line_json["discount_allocations"])
    
    
    billing_address_json = order["billing_address"]
    billing_address = Address(billing_address_json["first_name"], billing_address_json["last_name"], billing_address_json["address1"], billing_address_json["address2"],
                              billing_address_json["city"], billing_address_json["province"], billing_address_json["province_code"],
                              billing_address_json["zip"], billing_address_json["country"], billing_address_json["country_code"], billing_address_json["company"],
                              billing_address_json["phone"])
    
    shipping_address_json = order["shipping_address"]
    if shipping_address_json is not None:
        shipping_address = Address(shipping_address_json["first_name"], shipping_address_json["last_name"], shipping_address_json["address1"], shipping_address_json["address2"],
                                shipping_address_json["city"], shipping_address_json["province"], shipping_address_json["province_code"], shipping_address_json["zip"],
                                shipping_address_json["country"], shipping_address_json["country_code"], shipping_address_json["company"], shipping_address_json["phone"])
    else:
        shipping_address = Address()
    
    #Customer Details
    customerJson = order["customer"]
    customer = Customer(customerJson["id"], customerJson["email"], customerJson["first_name"], customerJson["last_name"], customerJson["phone"], customerJson["note"])
    
    #Pricing Details
    subtotal = float(order["subtotal_price"])
    tax_line = order["tax_lines"][0]
    spire_tax_code = getTaxCode(tax_line)
    discount_applications = order["discount_applications"]
    order_discount = calculateTotalDiscount(discount_applications, subtotal)
    
    #Line Items
    line_items_json = order["line_items"]
    line_items = []
    for line_item in line_items_json:
        item = LineItem(line_item["id"], line_item["title"], line_item["name"], line_item["grams"], line_item["price"], line_item["product_id"], line_item["quantity"],
                        line_item["sku"], line_item["total_discount"])
        line_items.append(item)
        
    #Additional Details
    note = order["note"]
        
    #-------------------------------------------------------Customer Check-------------------------------------------------
    
    if customer.spireCustomerNo is not None:
        
        print(customer.spireCustomerNo, "\n\n")
        #Search for customer by customer no in Spire
        encoded_filter = quote(json.dumps({"customerNo":customer.spireCustomerNo}))
        response = requests.get(f"https://red-wave-8362.spirelan.com:10880/api/v2/companies/{os.getenv("company")}/customers/?filter={encoded_filter}", auth=authorization, headers=headers)
        
        print(response.status_code)
        content = response.json()
        count = content["count"]
        
        if count == 0:
            customer.spireCustomerNo = "SHOPIFY"
    else:
        customer.spireCustomerNo = "SHOPIFY"
            
    #-------------------------------------------------Inventory Payload Generation-----------------------------------------------
        
    
    #--------------------------------------------------------Spire Payload Generation--------------------------------------------
    
    orderPayload = {
        "orderNo": f"WEB{order_number}-0",
        "customer": {
            "customerNo": customer.spireCustomerNo
        },
        "status": "O",
        "type": "O",
        "orderDate": datetime.fromisoformat(order_date.replace("Z", "+00:00")).strftime("%Y-%m-%d"),
        "address": {
            "country": "CAN",                       #Spire only accepts CAN, hard coded while website active in Canada only
            "city": billing_address.city,
            "postalCode": billing_address.postal_code,
            "provState": billing_address.province_code,
            "line1": billing_address.address1,
            "line2": billing_address.address2,
            "phone": {
                "number": billing_address.phone if billing_address.phone is not None else (phone if phone is not None else customer.phone),
                "format": 1
            },
            "email": contact_email if contact_email is not None else customer.email,
            "contacts": [
                {
                    "contact_type": {
                        "id": 2
                    },
                    "phone": {
                        "number": billing_address.phone if billing_address.phone is not None else (phone if phone is not None else customer.phone),
                        "format": 1
                    },
                    "name": billing_address.full_name,
                    "email": contact_email if contact_email is not None else customer.email
                }
            ],
            "website": order_status_url,
            "name": billing_address.company if billing_address.company is not None else (billing_address.full_name)
        },
        # "contact": {
        #     "name": customer.full_name,
        #     "email": customer.email,
        #     "phone": {
        #         "number": customer.phone if customer.phone is not None else (phone if phone is not None else billing_address.phone),
        #         "format": 1
        #     },
        #     "contact_type": {
        #         "id": 2
        #     }
        # },
        "udf": {
            "shopid": order_id,
            "confirmation_no": confirmation_no,
            "pre-order": True if "pre-order" in tags else False
        },
        "items": generate_inventory_payload(line_items=line_items),
        "discount": str(order_discount),
        "freight": str(shipping.net_freight)
    }
    
    if shipping_address_json is not None:
        orderPayload["shippingAddress"] = {
            "country": "CAN",
            "city": shipping_address.city,      #Spire only accepts CAN, hard coded while website active in Canada only
            "postalCode": shipping_address.postal_code,
            "provState": shipping_address.province_code,
            "line1": shipping_address.address1,
            "line2": shipping_address.address2,
            "phone": {
                "number": shipping_address.phone,
                "format": 1
            },
            "email": contact_email if contact_email is not None else customer.email,
            "website": order_status_url,
            "name": shipping_address.company if shipping_address.company is not None else shipping_address.full_name,
            "contacts": [
                {
                    "contact_type": {
                        "id": 2
                    },
                    "phone": {
                        "number": shipping_address.phone if shipping_address.phone is not None else (phone if phone is not None else customer.phone),
                        "format": 1
                    },
                    "name": shipping_address.full_name,
                    "email": contact_email if contact_email is not None else customer.email
                }
            ],
            "salesperson": {
                "code": "WEB",
                "name": "Website Sale"
            },
            "shipCode": shipping.spire_shipVia_code,
            "salesTaxes": [
                {
                    "code": spire_tax_code
                }
            ]
        }
    else:       #It's a pickup
        orderPayload["shippingAddress"] = {
            "salesperson": {
                "code": "WEB",
                "name": "Website Sale"
            },
            "shipCode": shipping.spire_shipVia_code
        }
        
    if note is not None:
        notes_payload = {
            "groupType": "CUS-NOTES",
            "subject": "Order Notes",
            "body": note,
            "attention": "A",
            "print": True
        }
    else:
        notes_payload = None
    
    return orderPayload, notes_payload
    
    
@app.route("/order-created", methods=["POST"])
def create_order():
    
    order = request.json
    
    orderPayload, notesPayload = createOrderPayload(order)
    
    orderPost_response = requests.post(f"https://red-wave-8362.spirelan.com:10880/api/v2/companies/{os.getenv("company")}/sales/orders/", json=orderPayload, 
                                       auth=authorization, headers=headers)
    
    if orderPost_response.status_code == 201:
        print(f"Order {orderPayload["orderNo"]} created successfully")
        created_order_endpoint = orderPost_response.headers["Location"]
    else:
        print(f"Order {orderPayload["orderNo"]} failed to create:")
        print(orderPost_response.json())
        return "Failed to create", 500
    
    
    #-----------------------------------------------------------Notes Payload----------------------------------------------------
    
    if notesPayload is not None:
        notes_endpoint = created_order_endpoint + "/notes/"
        
        note_response = requests.post(notes_endpoint, json=notesPayload, auth=authorization, headers=headers)
        
        if note_response.status_code == 201:
            print(f"Note created successfully on order {orderPayload["orderNo"]}")
        else:
            print(f"Failed to create note on order {orderPayload["orderNo"]}")
            print(orderPost_response.json())
    
    return jsonify(orderPayload), 201


@app.route("/order-updated", methods=["POST"])
def orderUpdated():
    
    order = request.json
    order_no = order["order_number"]
    
    #First find the spire sales order and sales order note info
    spire_order_id = getSpireOrderId(order_no)
    
    if spire_order_id is None:
        print(f"Could not find spire order WEB{order_no}")
        return Response(status=404)
    
    orderPayload, notesPayload = createOrderPayload(order)
    
    orderPut_response = requests.put(f"https://red-wave-8362.spirelan.com:10880/api/v2/companies/{os.getenv("company")}/sales/orders/{spire_order_id}", json=orderPayload, 
                                       auth=authorization, headers=headers)
    
    if orderPut_response.status_code != 200:
        print(f"{orderPut_response.status_code}: Error updating spire order WEB{order_no}")
        if orderPut_response.status_code == 423:
            return "Record locked by another user", 423
        return "Error with spire API calls", 500
    
    print(f"Order WEB{order_no} ({spire_order_id}) updated")
    return f"Order WEB{order_no} ({spire_order_id}) updated", 200


@app.route("/order-cancelled", methods=["POST"])
def orderCancelled():
    #Need to fix this to check cancellation validation
    
    order = request.json
    #print(json.dumps(order, indent=2))
    order_no = order["order_number"]
    
    if order["cancelled_at"] is not None and order["cancel_reason"] is not None:
    
        spire_order_id = getSpireOrderId(order_no)
        
        orderDelete_response = requests.delete(f"https://red-wave-8362.spirelan.com:10880/api/v2/companies/{os.getenv("company")}/sales/orders/{spire_order_id}",
                                        auth=authorization, headers=headers)
        
        status = orderDelete_response.status_code
        
        if status != 204:
            print(f"{status}: Error deleting spire order WEB{order_no}")
            return f"{status}: Error deleting spire order WEB{order_no}", status
        
        print(f"{status}: Deleted spire order WEB{order_no}")
        return f"{status}: Deleted spire order WEB{order_no}", 204
    
    else:
        print("Error in cancellation control logic. Order not deleted from Spire")
        return "Error in cancellation control logic. Order not deleted from Spire", 500


if __name__ == "__main__":
    print(f"App running on port {PORT}")
    app.run(port=PORT, host="0.0.0.0", debug=True)